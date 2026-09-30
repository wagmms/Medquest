import { test, expect } from '@playwright/test';
import { mockAnalysis } from './fixtures/learning-analysis';

test('optional comparison uses first responses and retains the selected institution', async ({ page }) => {
  await mockAnalysis(page);
  await page.goto('/analise');
  await expect(page.getByRole('heading', { name: 'Suas próximas prioridades' })).toBeVisible();
  await page.getByLabel('Banca', { exact: true }).selectOption('USP-SP');
  await page.getByText('Detalhes e comparação por banca', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Radar Comparativo de Bancas' })).toBeVisible();
  await expect(page.getByLabel('Selecionar banca alvo')).toHaveValue('USP-SP');
  await expect(page.getByLabel('Selecionar banca alvo')).toBeDisabled();
  await expect(page.getByText('Amostra em estágio inicial (12 questões distintas)')).toBeVisible();
  await page.getByLabel('Selecionar banca para comparação').selectOption('UNICAMP');
  await page.getByRole('button', { name: 'Visualização em tabela acessível' }).click();
  const table = page.getByRole('table', { name: /Desempenho comparativo/ });
  await expect(table).toBeVisible();
  await expect(table.getByRole('columnheader', { name: 'UNICAMP' })).toBeVisible();
  await expect(table.getByText('[39% – 86%]')).toBeVisible();
  await expect(page.getByText('Ações Imediatas para Fechar Lacunas', { exact: false })).toHaveCount(0);
});
