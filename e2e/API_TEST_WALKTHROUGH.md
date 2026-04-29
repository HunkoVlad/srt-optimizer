# API Test Walkthrough

This file explains how the sample API test in `e2e/api-example.spec.ts` works step by step.

## What makes an API test different

UI tests drive a browser with `page`.

API tests usually do not need a browser at all. Instead, Playwright sends HTTP requests directly and inspects the responses. That means:

- The tests are usually faster than UI tests
- There is no browser window to watch
- You validate request and response behavior instead of buttons and screens

In this repo, the API sample still uses Playwright, but it uses the `request` fixture instead of the `page` fixture.

## What this sample is testing

The sample models a tiny subtitle optimization API with three routes:

- `GET /health`
- `POST /api/subtitles/preview`
- `GET /api/subtitles/jobs/:jobId`

The goal is to show the pattern for testing a REST API, not to build a production server.

## Step-by-step flow

### 1. Define request and response types

At the top of `e2e/api-example.spec.ts`, the test defines TypeScript types for:

- The preview request body
- The preview response body
- The saved job status response

This makes the test easier to read and helps catch shape mismatches early.

### 2. Create sample input data

The `sampleSubtitle` constant is a small SRT payload that the test sends to the API.

This is useful because:

- The test does not depend on local files
- The request body is always the same
- Assertions stay deterministic

### 3. Build small helper functions

The test includes a few small helpers:

- `countCueBlocks()` counts subtitle cue blocks
- `getAppliedRules()` turns enabled options into a list of applied rule names
- `buildPreviewResponse()` creates the mock API response
- `readJsonBody()` reads and parses incoming JSON
- `sendJson()` sends JSON responses back to the client

These helpers keep the server logic easy to follow.

### 4. Start a local in-memory API server

The function `createSubtitleApiServer()` creates a tiny Node HTTP server inside the test file.

This is an important teaching pattern:

- We want real HTTP calls
- We do not want a dependency on an external environment
- We want the example to run anywhere the repo runs

The server stores created jobs in an in-memory `Map`, so the tests can create a preview first and then fetch its saved status later.

### 5. Register the API routes

Inside the server callback, the sample handles three routes:

1. `GET /health`
   Returns `{ "status": "ok" }`
2. `POST /api/subtitles/preview`
   Reads the request body, calculates a preview, stores a job, and returns the preview response
3. `GET /api/subtitles/jobs/:jobId`
   Looks up the saved job in memory and returns it

Anything else returns a `404` JSON response.

### 6. Start the server once before the tests

Inside `test.beforeAll()`:

- The local server starts
- Node picks an open random port
- The test stores the resulting `baseUrl`

This keeps each test simple because they all reuse the same local API base URL.

### 7. Stop the server after the suite

Inside `test.afterAll()`, the server is closed.

That cleanup step matters because it prevents open handles and flaky behavior when running multiple test files.

### 8. Use Playwright's `request` fixture

Each test receives Playwright's built-in `request` fixture:

```ts
test('returns a health response', async ({ request }) => {
  // ...
});
```

This fixture is an HTTP client provided by Playwright. It can send:

- `request.get(...)`
- `request.post(...)`
- `request.put(...)`
- `request.delete(...)`

and more.

### 9. Send requests and assert responses

The helper `expectOkJson<T>()` does two things:

- Verifies the HTTP response is OK
- Parses the JSON body

That keeps the actual test bodies focused on behavior.

Example:

```ts
const health = await expectOkJson<{ status: string }>(
  request.get(`${baseUrl}/health`)
);
```

After that, the test uses normal Playwright assertions:

```ts
expect(health).toEqual({ status: 'ok' });
```

### 10. Test both stateless and stateful behavior

The sample includes two kinds of API testing:

- Stateless check:
  `GET /health` returns a known payload
- Stateful flow:
  `POST /api/subtitles/preview` creates data, then `GET /api/subtitles/jobs/:jobId` reads it back

That second pattern is especially common in real REST API testing.

## Why there is no browser window

This is expected for API tests.

The tests do not use `page`, so Playwright does not need to open a browser. It behaves more like a test runner plus HTTP client in this case.

## How to run the sample

Run only the API example:

```powershell
npm.cmd run test:experiments:api
```

If you want a detailed report after the run, Playwright's HTML reporter will still be generated.

## How this pattern maps to a real project

When we switch from a demo API to a real backend, the structure is similar:

1. Replace the local in-memory server with the real base URL
2. Keep typed request and response models
3. Use helpers for repeated request/response handling
4. Assert status codes, response bodies, and state transitions
5. Add auth headers, setup data, and cleanup where needed

## Good next steps

If you want to grow this sample, useful next additions would be:

- A negative test for invalid request bodies
- A `404` test for missing job IDs
- A shared API client helper module for subtitle endpoints
- Environment-based base URL configuration for a real service
