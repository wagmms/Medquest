import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
import * as jsxRuntime from 'react/jsx-runtime';

function loadDashboard(overrides = {}) {
  const stats = Object.fromEntries(['getOverview', 'getBenchmark', 'getBottlenecks', 'getDomainSummary', 'getErrorNotebookSummary'].map(key => [key, async () => ({ distinct_answered: 12 })]));
  const planner = {
    getConfig: async () => ({ start_date: '2030-01-01', exam_date: '2030-12-01' }),
    getTopicProgress: async () => ({}), getProgress: async () => ({}),
    generatePlan: async () => ({ plan: [{ week: 2, date: '2030-01-08', topics: [{ subtema: 'Test' }] }] }),
  };
  Object.assign(stats, overrides.stats);
  Object.assign(planner, overrides.planner);
  const dependencies = { 'react/jsx-runtime': jsxRuntime, '@/lib/server-api': { serverApi: { stats, planner } }, '@clerk/nextjs/server': { currentUser: async () => null }, './DashboardClient': { DashboardClient: () => null } };
  const source = readFileSync(new URL('../../src/app/page.tsx', import.meta.url), 'utf8');
  const exports = {};
  runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText, {
    exports, require: id => { assert.ok(id in dependencies, id); return dependencies[id]; }, console: { error() {} },
  });
  return exports.default;
}

test('dashboard separates a failed overview from an empty account', async () => {
  const render = loadDashboard({ stats: { getOverview: async () => { throw new Error('offline'); } } });
  const { props } = await render();
  assert.equal(props.hasOverviewError, true);
  assert.equal(props.hasPlannerError, false);
});

for (const method of ['getConfig', 'getTopicProgress', 'getProgress', 'generatePlan']) {
  test(`dashboard does not infer incomplete progress when ${method} fails`, async () => {
    const render = loadDashboard({ planner: { [method]: async () => { throw new Error('offline'); } } });
    const { props } = await render();
    assert.equal(props.hasPlannerError, true);
    assert.equal(props.suggestedPlannerTopic, null);
    assert.equal(props.isPlanCompleted, false);
  });
}

test('dashboard respects completed topic aliases after a topic moves to a different week', async () => {
  const render = loadDashboard({ planner: { getTopicProgress: async () => ({ '1:Test': true, Test: true }) } });
  const { props } = await render();
  assert.equal(props.suggestedPlannerTopic, null);
  assert.equal(props.isPlanCompleted, true);
});
