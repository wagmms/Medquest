import { test, expect } from '@playwright/test';
import { mockAnalysis } from './fixtures/learning-analysis';
test('inspect accessible controls', async ({page})=>{
 await mockAnalysis(page); await page.goto('/analise');
 await expect(page.getByRole('heading',{name:'Suas próximas prioridades'})).toBeVisible();
 console.log('labels',await page.getByLabel('Banca',{exact:true}).count());
 console.log('roles',await page.getByRole('combobox',{name:'Banca',exact:true}).count());
 console.log('controls',await page.locator('select').evaluateAll(els=>els.map(e=>e.outerHTML.slice(0,350))));
 console.log('regions',await page.locator('section').evaluateAll(els=>els.map(e=>e.outerHTML.slice(0,260))));
 console.log('namedRegion',await page.getByRole('region',{name:'Suas próximas prioridades'}).count());
});
