import { test, expect } from '@playwright/test';
import { analysisFixture, mockAnalysis } from './fixtures/learning-analysis';

test('prioritizes learning evidence, preserves scope, and renders on mobile', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await mockAnalysis(page);
  await page.goto('/analise');
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
  await expect(page.getByText('Você costuma errar marcando')).toHaveCount(0);
  await expect(page.getByText('Dashboard Preditivo')).toHaveCount(0);
  await expect(page.getByText(/1 de 10 questões acompanhadas/)).toBeVisible();
  await page.getByRole('combobox', { name: 'Banca', exact: true }).selectOption('USP-SP');
  await page.getByRole('combobox', { name: 'Área', exact: true }).selectOption('Clínica Médica');
  await page.getByRole('combobox', { name: 'Tema', exact: true }).selectOption('Hipertensão Arterial Sistêmica');
  const priority = page.getByRole('region', { name: 'Suas próximas prioridades' });
  const href = await priority.getByRole('link', { name: 'Rever erros' }).getAttribute('href');
  const query = new URL(href!, 'http://localhost').searchParams;
  expect(query.get('institution')).toBe('USP-SP');
  expect(query.get('area')).toBe('Clínica Médica');
  expect(query.get('subtema')).toBe('Hipertensão Arterial Sistêmica');
  expect(query.get('status')).toBe('wrong');
  await page.screenshot({ path: testInfo.outputPath('analysis-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const priorities = await priority.boundingBox();
  const evidence = await page.getByRole('heading', { name: 'Como está sua aprendizagem?' }).boundingBox();
  expect(priorities!.y).toBeLessThan(evidence!.y);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath('analysis-mobile.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('failed requests do not display stale success, and retry recovers', async ({ page }) => {
  await mockAnalysis(page);
  await page.goto('/analise');
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
  let fail = true;
  await page.route('**/api/stats/learning-analysis?**', route => fail ? route.fulfill({ status: 503, json: { error: 'offline' } }) : route.fulfill({ json: analysisFixture() }));
  await page.getByLabel('Atualizar análise').click();
  await expect(page.getByRole('alert').filter({ hasText: 'Não foi possível carregar sua análise' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toHaveCount(0);
  await expect(page.getByText('Sua memória está em dia')).toHaveCount(0);
  fail = false;
  await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
});

test('empty account displays missing evidence without a mastery claim', async ({ page }) => {
  await mockAnalysis(page);
  const fixture = analysisFixture();
  const zero = { correct: 0, total: 0, accuracy: null };
  fixture.summary = { available: 0, answered: 0, unseen: 0, new_questions: zero, previous_new_questions: zero, delayed_reviews: zero, previous_delayed_reviews: zero, unresolved: 0, recurring: 0, corrected: 0, retained_corrections: 0, pending_checks: 0, due: 0, tracked: 0, at_risk: 0 };
  fixture.topics = []; fixture.priorities = [];
  await page.route('**/api/stats/learning-analysis?**', route => route.fulfill({ json: fixture }));
  await page.goto('/analise');
  await expect(page.getByText('Ainda não há estimativas de memória disponíveis', { exact: false })).toBeVisible();
  await expect(page.getByText('Não há questões disponíveis neste escopo.', { exact: false })).toBeVisible();
  await expect(page.getByText('50%', { exact: true })).toHaveCount(0);
});

test('only the latest filter response is shown', async ({ page }) => {
  await mockAnalysis(page);
  await page.goto('/analise');
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
  let release: (() => void) | undefined;
  await page.route('**/api/stats/learning-analysis?**', async route => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get('institution') === 'USP-SP') await new Promise<void>(resolve => { release = resolve; });
    await route.fulfill({ json: analysisFixture(params) }).catch(() => {});
  });
  await page.getByRole('combobox', { name: 'Banca', exact: true }).selectOption('USP-SP');
  await expect.poll(() => Boolean(release)).toBeTruthy();
  await page.getByRole('combobox', { name: 'Banca', exact: true }).selectOption('UNICAMP');
  const link = page.getByRole('region', { name: 'Suas próximas prioridades' }).getByRole('link', { name: 'Rever erros' });
  await expect(link).toHaveAttribute('href', /institution=UNICAMP/);
  release!();
  await expect(link).toHaveAttribute('href', /institution=UNICAMP/);
});
