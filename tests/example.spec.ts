import { expect, test, type Locator, type Page } from '@playwright/test';
import { renderSrtOptimizerDemo, sampleJobs } from './fixtures/srtOptimizerDemo';

type DemoRuleLabel =
  | 'Merge short lines'
  | 'Strip music tags'
  | 'Normalize punctuation';

class SrtOptimizerDemoPage {
  constructor(private readonly page: Page) {}

  async open(): Promise<void> {
    await this.page.setContent(renderSrtOptimizerDemo(sampleJobs));
  }

  rowForEpisode(episode: string): Locator {
    return this.page.locator('tbody tr').filter({ hasText: episode });
  }

  episodeCheckbox(episode: string): Locator {
    return this.rowForEpisode(episode).getByRole('checkbox');
  }

  ruleCheckbox(rule: DemoRuleLabel): Locator {
    return this.page.getByRole('checkbox', { name: rule });
  }

  get previewButton(): Locator {
    return this.page.getByRole('button', { name: 'Preview batch' });
  }

  get runButton(): Locator {
    return this.page.getByRole('button', { name: 'Run optimization' });
  }

  get exportButton(): Locator {
    return this.page.getByRole('button', { name: 'Export report' });
  }

  get batchStatus(): Locator {
    return this.page.locator('#batch-status');
  }

  get selectedFiles(): Locator {
    return this.page.getByTestId('selected-files');
  }

  get projectedCues(): Locator {
    return this.page.getByTestId('projected-cues');
  }

  get projectedTime(): Locator {
    return this.page.getByTestId('projected-time');
  }

  rowStatus(episode: string): Locator {
    return this.rowForEpisode(episode).getByTestId('status');
  }

  rowAppliedRules(episode: string): Locator {
    return this.rowForEpisode(episode).getByTestId('applied-rules');
  }

  async selectEpisodes(...episodes: string[]): Promise<void> {
    for (const episode of episodes) {
      await this.episodeCheckbox(episode).check();
    }
  }

  async enableRules(...rules: DemoRuleLabel[]): Promise<void> {
    for (const rule of rules) {
      await this.ruleCheckbox(rule).check();
    }
  }

  async setReadingSpeed(wordsPerMinute: number): Promise<void> {
    await this.page.getByTestId('wpm-slider').evaluate((node, value) => {
      const input = node as HTMLInputElement;
      input.value = String(value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }, wordsPerMinute);
  }
}

async function openDemo(page: Page): Promise<SrtOptimizerDemoPage> {
  const demoPage = new SrtOptimizerDemoPage(page);
  await demoPage.open();
  return demoPage;
}

test.describe('SRT optimizer demo flow', () => {
  test('previews savings for a selected subtitle batch', async ({ page }) => {
    const demoPage = await openDemo(page);

    await demoPage.selectEpisodes('Episode 01', 'Episode 02');
    await demoPage.enableRules('Merge short lines', 'Strip music tags');
    await demoPage.setReadingSpeed(180);
    await demoPage.previewButton.click();

    await expect(demoPage.selectedFiles).toHaveText('2');
    await expect(demoPage.projectedCues).toHaveText('22');
    await expect(demoPage.projectedTime).toHaveText('1m 50s');
    await expect(demoPage.batchStatus).toHaveText('Preview ready for 2 files.');
  });

  test('runs optimization and updates row state', async ({ page }) => {
    const demoPage = await openDemo(page);

    await demoPage.selectEpisodes('Episode 03');
    await demoPage.enableRules('Normalize punctuation');
    await expect(demoPage.runButton).toBeEnabled();

    await demoPage.runButton.click();

    await expect(demoPage.rowStatus('Episode 03')).toHaveText('Optimized');
    await expect(demoPage.rowAppliedRules('Episode 03')).toHaveText('1');
    await expect(demoPage.rowStatus('Episode 01')).toHaveText('Pending');
    await expect(demoPage.exportButton).toBeEnabled();
    await expect(demoPage.batchStatus).toHaveText('Optimization complete for 1 file.');
  });
});
