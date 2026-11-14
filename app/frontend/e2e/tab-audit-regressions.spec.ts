import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('medquest_onboarding_v1', 'done'));
});

test('analysis: failed requests hide stale data and retry the unchanged filter', async ({ page }) => {
  let readinessRequests = 0;
  let timelineRequests = 0;
  let failReadiness = false;
  let failTimeline = false;
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/stats/institution-radar')) return route.fulfill({ status: 503, json: { error: 'Unavailable' } });
    if (url.pathname.endsWith('/stats/exam-readiness')) {
      readinessRequests++;
      if (failReadiness) return route.fulfill({ status: 503, json: { error: 'Unavailable' } });
      return route.fulfill({ json: { institution: url.searchParams.get('institution'), coverage: 0.5, answered: 20, available: 40, areas: [], evidence_status: 'reliable', readiness_score: 0.68, disclaimer: 'Test' } });
    }
    if (url.pathname.endsWith('/stats/timeline')) {
      timelineRequests++;
      if (failTimeline) return route.fulfill({ status: 503, json: { error: 'Unavailable' } });
      return route.fulfill({ json: [{ day: '2026-09-27', attempts: 10, correct: 8, accuracy: 0.8 }] });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/analise');
  const readiness = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Prontidão Estimada por Edital' }) });
  const select = page.getByLabel('Selecionar edital da instituição');
  await select.selectOption('USP-SP');
  await expect(readiness.getByText('68%', { exact: true })).toBeVisible();
  failReadiness = true;
  await select.selectOption('UNICAMP');
  await expect(readiness.getByRole('alert')).toBeVisible();
  await expect(readiness.getByText('68%', { exact: true })).not.toBeVisible();
  const beforeReadinessRetry = readinessRequests;
  failReadiness = false;
  await readiness.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(readiness.getByText('68%', { exact: true })).toBeVisible();
  expect(readinessRequests).toBe(beforeReadinessRetry + 1);
  await expect(select).toHaveValue('UNICAMP');

  const timeline = page.locator('section').filter({ has: page.getByRole('button', { name: 'Ver evolução de 30 dias', exact: true }) });
  await timeline.getByRole('button', { name: 'Ver evolução de 30 dias', exact: true }).click();
  await expect(timeline.getByText('Dados exibidos: últimos 30 dias', { exact: true })).toBeVisible();
  failTimeline = true;
  await timeline.getByRole('button', { name: 'Ver evolução de 90 dias', exact: true }).click();
  await expect(timeline.getByRole('alert')).toBeVisible();
  await expect(timeline.getByText('Dados exibidos: últimos 30 dias', { exact: true })).not.toBeVisible();
  const beforeTimelineRetry = timelineRequests;
  failTimeline = false;
  await timeline.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(timeline.getByText('Dados exibidos: últimos 90 dias', { exact: true })).toBeVisible();
  expect(timelineRequests).toBe(beforeTimelineRetry + 1);
});
