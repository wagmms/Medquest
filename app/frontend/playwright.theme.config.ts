import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './e2e', testMatch: 'themeJourney.spec.ts', reporter: 'list' });
