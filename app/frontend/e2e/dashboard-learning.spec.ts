import { test, expect } from '@playwright/test';
import { analysisFixture, mockAnalysis } from './fixtures/learning-analysis';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('medquest_onboarding_v1', 'done'));
  await mockAnalysis(page);
});

test('dashboard shows evidence and scoped actions on desktop and mobile', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  const priorities = page.getByRole('region', { name: 'Suas prioridades', exact: true });
  await expect(priorities).toBeVisible();
  const href = await priorities.getByRole('link', { name: 'Revisar erros', exact: true }).getAttribute('href');
  const params = new URL(href!, 'http://localhost').searchParams;
  expect(params.get('area')).toBe('Clínica Médica');
  expect(params.get('subtema')).toBe('Hipertensão Arterial Sistêmica');
  expect(params.get('status')).toBe('wrong');
  expect(params.get('limit')).toBe('10');
  await expect(page.getByText('40% · 4/10', { exact: true })).toBeVisible();
  await expect(page.getByText('1 aguarda verificação', { exact: true })).toBeVisible();
  await expect(page.getByText('Faixa Estimada de Prontidão')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const priorityBox = await priorities.boundingBox();
  const learningBox = await page.getByRole('heading', { name: 'O que os resultados mostram' }).boundingBox();
  expect(priorityBox!.y).toBeLessThan(learningBox!.y);
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile.png'), fullPage: true });
  await page.getByRole('heading', { name: 'O que os resultados mostram' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile-evidence.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('failed refresh hides stale evidence and retry recovers', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Suas prioridades', exact: true })).toBeVisible();
  let fail = true;
  await page.route('**/api/stats/learning-analysis?**', route => fail
    ? route.fulfill({ status: 503, json: { error: 'unavailable' } })
    : route.fulfill({ json: analysisFixture() }));
  await page.getByRole('button', { name: 'Atualizar evidências' }).click();
  await expect(page.getByRole('heading', { name: 'Evidências temporariamente indisponíveis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Suas prioridades', exact: true })).toHaveCount(0);
  await expect(page.getByText(/100% limpo|Sem erros pendentes nas questões disponíveis/)).toHaveCount(0);
  fail = false;
  await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Suas prioridades', exact: true })).toBeVisible();
});

test('follow-up without available questions stays visible without a fabricated action', async ({ page }) => {
  const data = analysisFixture();
  const pending = { ...data.topics[0], topic: 'Correção aguardando revisão', unresolved: 0, due: 0,
    actions: { errors: null, reviews: null, new: null }, reason: 'follow_up' as const };
  data.topics[0].pending_checks = 0;
  data.topics.push(pending);
  await page.route('**/api/stats/learning-analysis?**', route => route.fulfill({ json: data }));
  await page.goto('/');
  const card = page.getByRole('article').filter({ has: page.getByRole('heading', { name: pending.topic }) });
  await expect(card).toBeVisible();
  await expect(card.getByText(/Sem sessão disponível agora/)).toBeVisible();
  await expect(card.getByRole('link')).toHaveCount(0);
});

test('no observations are missing evidence, not a readiness score', async ({ page }) => {
  const data = analysisFixture();
  const zero = { correct: 0, total: 0, accuracy: null };
  data.summary = { ...data.summary, new_questions: zero, previous_new_questions: zero,
    delayed_reviews: zero, previous_delayed_reviews: zero, available: 0, answered: 0, unseen: 0,
    unresolved: 0, recurring: 0, pending_checks: 0, retained_corrections: 0 };
  data.priorities = []; data.topics = [];
  await page.route('**/api/stats/learning-analysis?**', route => route.fulfill({ json: data }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Nenhuma questão disponível' })).toBeVisible();
  await expect(page.getByText('Sem respostas no período', { exact: true })).toHaveCount(2);
  await expect(page.getByText('Faixa Competitiva Estimada', { exact: false })).toHaveCount(0);
});
