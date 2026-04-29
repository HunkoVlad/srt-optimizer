import { test, expect, type APIRequestContext } from '@playwright/test';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { AddressInfo } from 'node:net';

type SubtitlePreviewRequest = {
  subtitleText: string;
  options?: {
    mergeShortLines?: boolean;
    stripMusicTags?: boolean;
    normalizePunctuation?: boolean;
  };
};

type SubtitlePreviewResponse = {
  jobId: string;
  originalCueCount: number;
  projectedCueCount: number;
  projectedSavings: number;
  appliedRules: string[];
};

type SubtitleJobStatus = {
  jobId: string;
  status: 'queued' | 'completed';
  originalCueCount: number;
  projectedCueCount: number;
};

// This sample SRT payload lets the API test exercise a realistic request body
// without depending on files on disk or an external service.
const sampleSubtitle = `1
00:00:01,000 --> 00:00:03,000
[MUSIC]

2
00:00:03,500 --> 00:00:06,000
Hi.

3
00:00:06,500 --> 00:00:09,000
This is a sample subtitle line.
`;

function countCueBlocks(subtitleText: string): number {
  return subtitleText
    .split(/\r?\n\r?\n/)
    .map((block) => block.trim())
    .filter(Boolean).length;
}

function getAppliedRules(options: SubtitlePreviewRequest['options']): string[] {
  if (!options) {
    return [];
  }

  return Object.entries(options)
    .filter(([, enabled]) => enabled)
    .map(([rule]) => rule);
}

function buildPreviewResponse(requestBody: SubtitlePreviewRequest): SubtitlePreviewResponse {
  const originalCueCount = countCueBlocks(requestBody.subtitleText);
  const appliedRules = getAppliedRules(requestBody.options);
  const savings =
    (requestBody.options?.mergeShortLines ? 1 : 0) +
    (requestBody.options?.stripMusicTags ? 1 : 0) +
    (requestBody.options?.normalizePunctuation ? 1 : 0);

  return {
    jobId: 'job-preview-001',
    originalCueCount,
    projectedCueCount: Math.max(1, originalCueCount - savings),
    projectedSavings: savings,
    appliedRules,
  };
}

async function readJsonBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];

  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  const rawBody = Buffer.concat(chunks).toString('utf8');
  return rawBody ? JSON.parse(rawBody) : {};
}

function sendJson(response: ServerResponse, statusCode: number, body: unknown): void {
  response.statusCode = statusCode;
  response.setHeader('Content-Type', 'application/json');
  response.end(JSON.stringify(body));
}

async function createSubtitleApiServer() {
  const jobs = new Map<string, SubtitleJobStatus>();

  // The test spins up a tiny local API so Playwright can send real HTTP requests
  // while keeping the example deterministic and self-contained.
  const server = createServer(async (request, response) => {
    if (!request.url || !request.method) {
      sendJson(response, 400, { error: 'Invalid request' });
      return;
    }

    if (request.method === 'GET' && request.url === '/health') {
      sendJson(response, 200, { status: 'ok' });
      return;
    }

    if (request.method === 'POST' && request.url === '/api/subtitles/preview') {
      const body = (await readJsonBody(request)) as SubtitlePreviewRequest;
      const preview = buildPreviewResponse(body);

      jobs.set(preview.jobId, {
        jobId: preview.jobId,
        status: 'completed',
        originalCueCount: preview.originalCueCount,
        projectedCueCount: preview.projectedCueCount,
      });

      sendJson(response, 200, preview);
      return;
    }

    if (request.method === 'GET' && request.url.startsWith('/api/subtitles/jobs/')) {
      const jobId = request.url.split('/').pop() ?? '';
      const job = jobs.get(jobId);

      if (!job) {
        sendJson(response, 404, { error: 'Job not found' });
        return;
      }

      sendJson(response, 200, job);
      return;
    }

    sendJson(response, 404, { error: 'Route not found' });
  });

  await new Promise<void>((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve());
  });

  const address = server.address() as AddressInfo;
  const baseUrl = `http://127.0.0.1:${address.port}`;

  return {
    baseUrl,
    close: async () => {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) {
            reject(error);
            return;
          }

          resolve();
        });
      });
    },
  };
}

test.describe('subtitle optimizer REST API sample', () => {
  let baseUrl = '';
  let shutdownServer: (() => Promise<void>) | undefined;

  test.beforeAll(async () => {
    // Start the local API once for the suite and capture its random port.
    const server = await createSubtitleApiServer();
    baseUrl = server.baseUrl;
    shutdownServer = server.close;
  });

  test.afterAll(async () => {
    await shutdownServer?.();
  });

  // This helper keeps each test focused on behavior instead of repeating
  // "status is OK" and "parse the JSON body" boilerplate.
  async function expectOkJson<T>(responsePromise: Promise<Awaited<ReturnType<APIRequestContext['get']>> | Awaited<ReturnType<APIRequestContext['post']>>>): Promise<T> {
    const response = await responsePromise;
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as T;
  }

  test('returns a health response', async ({ request }) => {
    const health = await expectOkJson<{ status: string }>(request.get(`${baseUrl}/health`));

    expect(health).toEqual({ status: 'ok' });
  });

  test('previews subtitle optimization results', async ({ request }) => {
    // The Playwright "request" fixture acts like a built-in API client.
    const preview = await expectOkJson<SubtitlePreviewResponse>(
      request.post(`${baseUrl}/api/subtitles/preview`, {
        data: {
          subtitleText: sampleSubtitle,
          options: {
            mergeShortLines: true,
            stripMusicTags: true,
            normalizePunctuation: false,
          },
        } satisfies SubtitlePreviewRequest,
      }),
    );

    expect(preview.jobId).toBe('job-preview-001');
    expect(preview.originalCueCount).toBe(3);
    expect(preview.projectedCueCount).toBe(1);
    expect(preview.projectedSavings).toBe(2);
    expect(preview.appliedRules).toEqual(['mergeShortLines', 'stripMusicTags']);
  });

  test('returns saved job status after a preview request', async ({ request }) => {
    // First create state through one endpoint, then verify that another
    // endpoint can read back the saved result.
    await expectOkJson<SubtitlePreviewResponse>(
      request.post(`${baseUrl}/api/subtitles/preview`, {
        data: {
          subtitleText: sampleSubtitle,
          options: {
            mergeShortLines: true,
            stripMusicTags: false,
            normalizePunctuation: true,
          },
        } satisfies SubtitlePreviewRequest,
      }),
    );

    const job = await expectOkJson<SubtitleJobStatus>(
      request.get(`${baseUrl}/api/subtitles/jobs/job-preview-001`),
    );

    expect(job).toEqual({
      jobId: 'job-preview-001',
      status: 'completed',
      originalCueCount: 3,
      projectedCueCount: 1,
    });
  });
});
