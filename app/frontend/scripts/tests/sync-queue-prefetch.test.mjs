import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function loadModules(globals = {}) {
  const dbSource = readFileSync(new URL('../../src/lib/db.ts', import.meta.url), 'utf8');
  const syncQueueSource = readFileSync(new URL('../../src/lib/syncQueue.ts', import.meta.url), 'utf8');

  const { outputText: dbOutput } = ts.transpileModule(dbSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });

  const { outputText: syncQueueOutput } = ts.transpileModule(syncQueueSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });

  const dbExports = {};
  const syncQueueExports = {};

  const mockDexie = class MockDexie {
    constructor(dbName) {
      this.name = dbName;
      this.tables = {};
    }
    version() {
      return {
        stores: () => ({
          upgrade: () => {},
        }),
      };
    }
  };

  const context = {
    exports: dbExports,
    require: (id) => {
      if (id === 'dexie') return { default: mockDexie };
      return {};
    },
    console: { log() {}, info() {}, warn() {}, error() {} },
    process: { env: {} },
    Error: globalThis.Error,
    TypeError: globalThis.TypeError,
    crypto: globalThis.crypto,
    Set: globalThis.Set,
    Array: globalThis.Array,
    Object: globalThis.Object,
    ...globals,
  };

  runInNewContext(dbOutput, context);

  // Executa syncQueue no mesmo contexto com api mockada
  const syncQueueContext = {
    ...context,
    exports: syncQueueExports,
    require: (id) => {
      if (id === './db') return dbExports;
      if (id === './api') return globals.__apiMock || { api: { questions: {} } };
      return {};
    },
  };

  runInNewContext(syncQueueOutput, syncQueueContext);

  return {
    db: dbExports,
    syncQueue: syncQueueExports,
  };
}

test('getCachedQuestionIds: retorna Set vazio para coleção vazia ou fora do browser', async () => {
  const { db } = loadModules({});
  const res1 = await db.getCachedQuestionIds([]);
  const res2 = await db.getCachedQuestionIds(null);
  assert.equal(res1.size, 0);
  assert.equal(res2.size, 0);
});

test('getCachedQuestionIds: busca chaves [id, ownerId] e retorna Set com os IDs encontrados', async () => {
  let requestedKeys = null;
  const { db } = loadModules({
    window: {},
    localStorage: { getItem: () => 'user_test_medquest' },
  });

  const mockDb = new db.MedQuestDB();
  mockDb.questions = {
    bulkGet: async (keys) => {
      requestedKeys = keys;
      return [{ id: 101, stem: 'Q101' }, null];
    },
  };

  const result = await mockDb.getCachedQuestionIds([101, 102]);
  assert.equal(requestedKeys.length, 2);
  assert.equal(requestedKeys[0][0], 101);
  assert.equal(requestedKeys[0][1], 'user_test_medquest');
  assert.equal(requestedKeys[1][0], 102);
  assert.equal(requestedKeys[1][1], 'user_test_medquest');
  assert.equal(result.has(101), true);
  assert.equal(result.has(102), false);
  assert.equal(result.size, 1);
});

test('prefetchQuestionsByIds: opera defensivamente em ambiente SSR', async () => {
  const { syncQueue } = loadModules({});
  const res = await syncQueue.prefetchQuestionsByIds([1, 2, 3]);
  assert.equal(res.prefetched, 0);
  assert.equal(res.cached, 0);
  assert.equal(res.total, 0);
});

test('prefetchQuestionsByIds: sanitiza IDs inválidos, negativos e deduplica entradas', async () => {
  const { syncQueue } = loadModules({
    window: {},
    navigator: { onLine: true },
    localStorage: { getItem: () => 'user_1' },
    __apiMock: {
      api: {
        questions: {
          getBatch: async () => ({ questions: [] }),
        },
      },
    },
  });

  const res = await syncQueue.prefetchQuestionsByIds([-5, 0, null, 'abc', 42, 42]);
  assert.equal(res.total, 1);
});

test('prefetchQuestionsByIds: se todas as questões já estiverem em cache, não faz requisição de rede', async () => {
  let getBatchCalled = false;
  const { syncQueue, db } = loadModules({
    window: {},
    navigator: { onLine: true },
    localStorage: { getItem: () => 'user_1' },
    __apiMock: {
      api: {
        questions: {
          getBatch: async () => {
            getBatchCalled = true;
            return { questions: [] };
          },
        },
      },
    },
  });

  db.localDb.questions = {
    bulkGet: async (keys) => keys.map(([id]) => ({ id, stem: `Questao ${id}` })),
  };

  const res = await syncQueue.prefetchQuestionsByIds([10, 20]);
  assert.equal(getBatchCalled, false, 'getBatch não deve ser chamado quando todas já estão em cache');
  assert.equal(res.prefetched, 0);
  assert.equal(res.cached, 2);
  assert.equal(res.total, 2);
});

test('prefetchQuestionsByIds: se o dispositivo estiver offline, não aciona requisição de rede', async () => {
  let getBatchCalled = false;
  const { syncQueue, db } = loadModules({
    window: {},
    navigator: { onLine: false },
    localStorage: { getItem: () => 'user_1' },
    __apiMock: {
      api: {
        questions: {
          getBatch: async () => {
            getBatchCalled = true;
            return { questions: [] };
          },
        },
      },
    },
  });

  db.localDb.questions = {
    bulkGet: async () => [null, null],
  };

  const res = await syncQueue.prefetchQuestionsByIds([10, 20]);
  assert.equal(getBatchCalled, false);
  assert.equal(res.prefetched, 0);
  assert.equal(res.cached, 0);
  assert.equal(res.total, 2);
});

test('prefetchQuestionsByIds: busca IDs faltantes via getBatch e persiste atomicamente no Dexie com evento', async () => {
  let batchRequestedIds = null;
  let syncPersistedQuestions = null;
  let customEventDispatched = null;

  const mockQuestions = [
    { id: 30, stem: 'Questão 30 sobre HAS', area: 'Clínica Médica' },
    { id: 40, stem: 'Questão 40 sobre ICC', area: 'Clínica Médica' },
  ];

  const { syncQueue, db } = loadModules({
    window: {
      dispatchEvent: (evt) => {
        customEventDispatched = evt;
      },
    },
    navigator: { onLine: true },
    localStorage: { getItem: () => 'user_1' },
    CustomEvent: class MockCustomEvent {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    __apiMock: {
      api: {
        questions: {
          getBatch: async (ids) => {
            batchRequestedIds = ids;
            return { questions: mockQuestions };
          },
        },
      },
    },
  });

  db.localDb.questions = {
    bulkGet: async (keys) => {
      // Questão 20 já está em cache, 30 e 40 faltam
      return keys.map(([id]) => (id === 20 ? { id: 20 } : null));
    },
    bulkPut: async (qs) => {
      syncPersistedQuestions = qs;
    },
  };
  db.localDb.transaction = async (mode, table, cb) => cb();

  const res = await syncQueue.prefetchQuestionsByIds([20, 30, 40]);

  assert.equal(batchRequestedIds.length, 2, 'Apenas IDs ausentes devem ser solicitados');
  assert.equal(batchRequestedIds[0], 30);
  assert.equal(batchRequestedIds[1], 40);
  assert.equal(syncPersistedQuestions.length, 2, '2 questões devem ser salvas no Dexie');
  assert.equal(res.prefetched, 2);
  assert.equal(res.cached, 3);
  assert.equal(res.total, 3);
  assert.ok(customEventDispatched, 'Evento questions-prefetched deve ser emitido');
  assert.equal(customEventDispatched.type, 'questions-prefetched');
  assert.equal(customEventDispatched.detail.count, 2);
});

test('prefetchUpcomingQuestions: consulta getList com subtema e delega prefetch', async () => {
  let getListFilters = null;
  let getBatchIds = null;

  const { syncQueue, db } = loadModules({
    window: {},
    navigator: { onLine: true },
    localStorage: { getItem: () => 'user_1' },
    __apiMock: {
      api: {
        questions: {
          getList: async (filters) => {
            getListFilters = filters;
            return [
              { id: 101, subtema: 'HAS' },
              { id: 102, subtema: 'HAS' },
            ];
          },
          getBatch: async (ids) => {
            getBatchIds = ids;
            return {
              questions: [
                { id: 101, stem: 'Q101' },
                { id: 102, stem: 'Q102' },
              ],
            };
          },
        },
      },
    },
  });

  db.localDb.questions = {
    bulkGet: async () => [null, null],
    bulkPut: async () => {},
  };
  db.localDb.transaction = async (mode, table, cb) => cb();

  const res = await syncQueue.prefetchUpcomingQuestions('Hipertensão Arterial Sistêmica', 10);

  assert.equal(getListFilters.limit, '10');
  assert.equal(getListFilters.subtema, 'Hipertensão Arterial Sistêmica');
  assert.equal(getBatchIds.length, 2);
  assert.equal(getBatchIds[0], 101);
  assert.equal(getBatchIds[1], 102);
  assert.equal(res.prefetched, 2);
  assert.equal(res.total, 2);
});
