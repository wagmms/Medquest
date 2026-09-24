import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

// Load the actual TypeScript modules with deterministic browser/storage doubles.
function loadModule(name, dependencies, globals = {}) {
  const source = readFileSync(new URL(`../../src/lib/${name}.ts`, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const exports = {};
  runInNewContext(outputText, {
    exports, require: id => {
      assert.ok(id in dependencies, `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    console: { log() {}, warn() {}, error() {} },
    process: { env: {} }, Headers, AbortController, TypeError,
    crypto: globalThis.crypto, setTimeout, clearTimeout,
    ...globals,
  });
  return exports;
}

test('completed requests release their caller abort listener on success and failure', async () => {
  for (const ok of [true, false]) {
    const listeners = new Set();
    const signal = {
      aborted: false,
      throwIfAborted() {},
      addEventListener: (_, listener) => listeners.add(listener),
      removeEventListener: (_, listener) => listeners.delete(listener),
    };
    const { api } = loadModule('api', { './sync': {}, './db': {} }, {
      fetch: async () => ({ ok, status: 500, json: async () => [] }),
    });
    const request = api.stats.getTimeline(14, signal);
    if (ok) await request;
    else await assert.rejects(request);
    assert.equal(listeners.size, 0);
  }
});

test('an already cancelled offline request preserves its abort error', async () => {
  let enqueued = 0;
  const { api } = loadModule('api', {
    './sync': { syncManager: { enqueue: async () => { enqueued++; } } }, './db': {},
  }, { window: {}, navigator: { onLine: false } });
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(api.stats.getTimeline(14, controller.signal), { name: 'AbortError' });
  assert.equal(enqueued, 0);
});

function syncHarness(items) {
  let owner = 'alice';
  const timers = new Map();
  let timerId = 0;
  const queue = {
    where: () => ({ equals: () => ({
      filter: predicate => ({
        toArray: async () => items.filter(predicate),
        count: async () => items.filter(predicate).length,
      }),
    }) }),
    delete: async id => { items.splice(items.findIndex(item => item.id === id), 1); },
  };
  const { syncManager } = loadModule('sync', {
    './db': { localDb: { syncQueue: queue }, getLocalOwnerId: () => owner },
  }, {
    window: { dispatchEvent() {}, addEventListener() {}, removeEventListener() {} },
    document: { addEventListener() {}, removeEventListener() {} },
    navigator: { onLine: true },
    CustomEvent: class {},
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
    fetch: async endpoint => {
      sent.push(endpoint);
      if (switchOwner) owner = 'bob';
      return { ok: true, text: async () => '{}' };
    },
  });
  const sent = [];
  let switchOwner = false;
  return { syncManager, timers, sent, switchOwner: () => { switchOwner = true; } };
}

function pending(id, created_at) {
  return { id, endpoint: id, owner_id: 'alice', created_at, status: 'pending', next_retry_at: 0 };
}

test('offline mutations replay in creation order rather than random UUID order', async () => {
  const h = syncHarness([pending('a-newer', 2), pending('z-older', 1)]);
  await h.syncManager.sync(true);
  assert.deepEqual(h.sent, ['z-older', 'a-newer']);
});

test('switching accounts stops replay of the previous account queue', async () => {
  const h = syncHarness([pending('first', 1), pending('second', 2)]);
  h.switchOwner();
  await h.syncManager.sync(true);
  assert.deepEqual(h.sent, ['first']);
});

test('overlapping schedule calls leave only one timer and cleanup removes it', async () => {
  const h = syncHarness([pending('first', 1)]);
  h.syncManager.init();
  await Promise.all([h.syncManager.scheduleNextSync(), h.syncManager.scheduleNextSync()]);
  assert.equal(h.timers.size, 1);
  h.syncManager.cleanup();
  assert.equal(h.timers.size, 0);
});

test('cleanup invalidates a pending schedule even when immediately reinitialized', async () => {
  const h = syncHarness([pending('first', 1)]);
  h.syncManager.init();
  h.syncManager.cleanup();
  h.syncManager.init();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.timers.size, 1);
  h.syncManager.cleanup();
});
