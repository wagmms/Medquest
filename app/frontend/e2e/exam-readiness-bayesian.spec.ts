import { test, expect } from '@playwright/test';
import { mockAnalysis } from './fixtures/learning-analysis';

test('optional area detail labels experimental weights and hides the zero-evidence prior', async ({ page }) => {
  await mockAnalysis(page);
  await page.goto('/analise');
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
  await page.getByLabel('Banca', { exact: true }).selectOption('USP-SP');
  await page.getByText('Detalhes e comparação por banca', { exact: true }).click();
  const profile = page.getByRole('region', { name: 'Perfil por área' });
  await expect(profile.getByText(/Perfil experimental/)).toBeVisible();
  await expect(profile.getByText('Ainda não avaliada')).toBeVisible();
  await expect(profile.getByText('50%', { exact: true })).toHaveCount(0);
  await expect(profile.getByRole('link', { name: 'Praticar inéditas' })).toHaveAttribute('href', /institution=USP-SP/);
  await expect(page.getByText('Detalhe histórico:', { exact: false })).toBeVisible();
});
