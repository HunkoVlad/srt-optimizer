export type SubtitleJob = {
  id: string;
  episode: string;
  durationMinutes: number;
  cueCount: number;
  shortLineCount: number;
  musicTagCount: number;
};

export const sampleJobs: SubtitleJob[] = [
  {
    id: 'ep-01',
    episode: 'Episode 01',
    durationMinutes: 24,
    cueCount: 112,
    shortLineCount: 8,
    musicTagCount: 3,
  },
  {
    id: 'ep-02',
    episode: 'Episode 02',
    durationMinutes: 22,
    cueCount: 96,
    shortLineCount: 9,
    musicTagCount: 2,
  },
  {
    id: 'ep-03',
    episode: 'Episode 03',
    durationMinutes: 26,
    cueCount: 118,
    shortLineCount: 7,
    musicTagCount: 4,
  },
];

const totalCueCount = sampleJobs.reduce((sum, job) => sum + job.cueCount, 0);

function buildRows(jobs: SubtitleJob[]): string {
  return jobs
    .map(
      (job) => `
        <tr
          data-job-id="${job.id}"
          data-short-lines="${job.shortLineCount}"
          data-music-tags="${job.musicTagCount}"
          data-cues="${job.cueCount}"
        >
          <td>
            <label class="job-selector" for="${job.id}">
              <input id="${job.id}" type="checkbox" data-job-select />
              <span>${job.episode}</span>
            </label>
          </td>
          <td>${job.durationMinutes} min</td>
          <td>${job.cueCount}</td>
          <td data-testid="status">Pending</td>
          <td data-testid="applied-rules">0</td>
        </tr>
      `,
    )
    .join('');
}

export function renderSrtOptimizerDemo(jobs: SubtitleJob[]): string {
  return `
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>SRT Optimizer Demo</title>
        <style>
          :root {
            color-scheme: light;
            font-family: "Segoe UI", sans-serif;
            background: #f4f7fb;
            color: #16324f;
          }

          body {
            margin: 0;
            background:
              radial-gradient(circle at top left, rgba(82, 145, 255, 0.18), transparent 36%),
              linear-gradient(180deg, #f8fbff 0%, #eef3f8 100%);
          }

          main {
            max-width: 980px;
            margin: 0 auto;
            padding: 32px 24px 48px;
          }

          .shell {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(22, 50, 79, 0.08);
            border-radius: 20px;
            box-shadow: 0 16px 48px rgba(22, 50, 79, 0.12);
            overflow: hidden;
          }

          .hero {
            padding: 24px;
            background: linear-gradient(135deg, #16324f 0%, #234d77 55%, #2c75b5 100%);
            color: #ffffff;
          }

          .hero h1 {
            margin: 0 0 8px;
            font-size: 2rem;
          }

          .hero p {
            margin: 0;
            max-width: 50rem;
            color: rgba(255, 255, 255, 0.86);
          }

          .content {
            padding: 24px;
            display: grid;
            gap: 20px;
          }

          .stats,
          .controls,
          .results {
            display: grid;
            gap: 16px;
          }

          .stats {
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          }

          .card,
          .panel {
            border-radius: 16px;
            background: #ffffff;
            border: 1px solid #d7e3f0;
            padding: 18px;
          }

          .card strong {
            display: block;
            font-size: 1.7rem;
            margin-top: 8px;
          }

          .controls {
            grid-template-columns: 1.5fr 1fr;
          }

          .rule-list {
            display: grid;
            gap: 12px;
          }

          .rule-list label,
          .job-selector {
            display: inline-flex;
            gap: 10px;
            align-items: center;
          }

          .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 18px;
          }

          button {
            border: 0;
            border-radius: 999px;
            padding: 12px 18px;
            font-weight: 700;
            cursor: pointer;
            background: #234d77;
            color: #ffffff;
          }

          button[disabled] {
            cursor: not-allowed;
            opacity: 0.45;
          }

          button.secondary {
            background: #d9e7f6;
            color: #16324f;
          }

          table {
            width: 100%;
            border-collapse: collapse;
          }

          th,
          td {
            text-align: left;
            padding: 14px 12px;
            border-bottom: 1px solid #e3ebf3;
          }

          th {
            color: #4c6682;
            font-size: 0.92rem;
          }

          .results {
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          }

          dl {
            margin: 0;
          }

          dd {
            margin: 8px 0 0;
            font-size: 1.5rem;
            font-weight: 700;
          }

          [role="status"] {
            margin: 0;
            padding: 14px 16px;
            border-radius: 14px;
            background: #ecf5ff;
            border: 1px solid #c7dbf0;
          }

          @media (max-width: 760px) {
            .controls {
              grid-template-columns: 1fr;
            }

            main {
              padding: 18px 14px 32px;
            }
          }
        </style>
      </head>
      <body>
        <main>
          <section class="shell">
            <div class="hero">
              <h1>SRT Optimizer Batch Console</h1>
              <p>Preview line-level cleanup, estimate review savings, and run a small subtitle batch locally.</p>
            </div>

            <div class="content">
              <section class="stats" aria-label="Portfolio summary">
                <article class="card">
                  <span>Subtitle files</span>
                  <strong data-testid="job-count">${jobs.length}</strong>
                </article>
                <article class="card">
                  <span>Total cues</span>
                  <strong data-testid="cue-count">${totalCueCount}</strong>
                </article>
                <article class="card">
                  <span>Profile</span>
                  <strong>Localization QA</strong>
                </article>
              </section>

              <section class="controls">
                <article class="panel">
                  <h2>Optimization rules</h2>
                  <div class="rule-list">
                    <label>
                      <input type="checkbox" name="rule" value="mergeShortLines" />
                      <span>Merge short lines</span>
                    </label>
                    <label>
                      <input type="checkbox" name="rule" value="stripMusicTags" />
                      <span>Strip music tags</span>
                    </label>
                    <label>
                      <input type="checkbox" name="rule" value="normalizePunctuation" />
                      <span>Normalize punctuation</span>
                    </label>
                  </div>
                </article>

                <article class="panel">
                  <h2>Review target</h2>
                  <label for="wpm-slider">Reading speed target</label>
                  <input
                    id="wpm-slider"
                    data-testid="wpm-slider"
                    type="range"
                    min="140"
                    max="200"
                    step="5"
                    value="165"
                  />
                  <p><output data-testid="wpm-output">165 WPM</output></p>
                  <div class="actions">
                    <button type="button" id="preview-button" disabled>Preview batch</button>
                    <button type="button" id="run-button" disabled>Run optimization</button>
                    <button type="button" id="export-button" class="secondary" disabled>Export report</button>
                  </div>
                </article>
              </section>

              <p id="batch-status" role="status" aria-live="polite">Select files and rules to continue.</p>

              <section class="results" aria-label="Batch preview">
                <article class="panel">
                  <dl>
                    <dt>Selected files</dt>
                    <dd data-testid="selected-files">0</dd>
                  </dl>
                </article>
                <article class="panel">
                  <dl>
                    <dt>Projected cue reductions</dt>
                    <dd data-testid="projected-cues">0</dd>
                  </dl>
                </article>
                <article class="panel">
                  <dl>
                    <dt>Estimated review time saved</dt>
                    <dd data-testid="projected-time">0m 00s</dd>
                  </dl>
                </article>
              </section>

              <section class="panel" aria-label="Subtitle jobs">
                <table>
                  <caption style="text-align: left; margin-bottom: 12px; font-weight: 700;">Queued subtitle jobs</caption>
                  <thead>
                    <tr>
                      <th scope="col">Episode</th>
                      <th scope="col">Duration</th>
                      <th scope="col">Cues</th>
                      <th scope="col">Status</th>
                      <th scope="col">Rules applied</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${buildRows(jobs)}
                  </tbody>
                </table>
              </section>
            </div>
          </section>
        </main>

        <script>
          const rows = Array.from(document.querySelectorAll('tbody tr'));
          const previewButton = document.getElementById('preview-button');
          const runButton = document.getElementById('run-button');
          const exportButton = document.getElementById('export-button');
          const status = document.getElementById('batch-status');
          const slider = document.querySelector('[data-testid="wpm-slider"]');
          const wpmOutput = document.querySelector('[data-testid="wpm-output"]');
          const selectedFiles = document.querySelector('[data-testid="selected-files"]');
          const projectedCues = document.querySelector('[data-testid="projected-cues"]');
          const projectedTime = document.querySelector('[data-testid="projected-time"]');

          function getSelectedRows() {
            return rows.filter((row) => row.querySelector('[data-job-select]').checked);
          }

          function getSelectedRules() {
            return Array.from(document.querySelectorAll('input[name="rule"]:checked')).map((input) => input.value);
          }

          function cueSavingsForRow(row, rules) {
            let savings = 0;

            if (rules.includes('mergeShortLines')) {
              savings += Number(row.dataset.shortLines);
            }

            if (rules.includes('stripMusicTags')) {
              savings += Number(row.dataset.musicTags);
            }

            if (rules.includes('normalizePunctuation')) {
              savings += Math.ceil(Number(row.dataset.cues) * 0.05);
            }

            return savings;
          }

          function formatTime(seconds) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            return minutes + 'm ' + String(remainingSeconds).padStart(2, '0') + 's';
          }

          function refreshButtons() {
            const hasSelection = getSelectedRows().length > 0;
            const hasRules = getSelectedRules().length > 0;
            const isEnabled = hasSelection && hasRules;

            previewButton.disabled = !isEnabled;
            runButton.disabled = !isEnabled;
          }

          function previewBatch() {
            const files = getSelectedRows();
            const rules = getSelectedRules();
            const reviewSpeed = Number(slider.value);
            const secondsPerCue = reviewSpeed >= 175 ? 5 : 6;
            const totalSavings = files.reduce((sum, row) => sum + cueSavingsForRow(row, rules), 0);

            selectedFiles.textContent = String(files.length);
            projectedCues.textContent = String(totalSavings);
            projectedTime.textContent = formatTime(totalSavings * secondsPerCue);
            status.textContent = 'Preview ready for ' + files.length + ' file' + (files.length === 1 ? '' : 's') + '.';
          }

          function runBatch() {
            const files = getSelectedRows();
            const rules = getSelectedRules();

            if (files.length === 0 || rules.length === 0) {
              status.textContent = 'Select at least one file and one rule.';
              return;
            }

            files.forEach((row) => {
              row.querySelector('[data-testid="status"]').textContent = 'Optimized';
              row.querySelector('[data-testid="applied-rules"]').textContent = String(rules.length);
            });

            exportButton.disabled = false;
            status.textContent = 'Optimization complete for ' + files.length + ' file' + (files.length === 1 ? '' : 's') + '.';
          }

          document.addEventListener('change', (event) => {
            if (event.target instanceof HTMLInputElement && (event.target.name === 'rule' || event.target.hasAttribute('data-job-select'))) {
              refreshButtons();
            }
          });

          slider.addEventListener('input', () => {
            wpmOutput.textContent = slider.value + ' WPM';
          });

          previewButton.addEventListener('click', previewBatch);
          runButton.addEventListener('click', runBatch);
          refreshButtons();
        </script>
      </body>
    </html>
  `;
}
