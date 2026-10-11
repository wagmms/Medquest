import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function loadDbModule(globals = {}) {
  const source = readFileSync(new URL('../../src/lib/db.ts', import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });

  const exports = {};
  const mockDexie = class MockDexie {
    constructor(dbName) {
      this.name = dbName;
      this.versionCalled = 0;
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

  runInNewContext(outputText, {
    exports,
    require: (id) => {
      if (id === 'dexie') return { default: mockDexie };
      return {};
    },
    console: { log() {}, warn() {}, error() {} },
    process: { env: {} },
    Error: globalThis.Error,
    TypeError: globalThis.TypeError,
    crypto: globalThis.crypto,
    ...globals,
  });

  return exports;
}

test('syncQuestions retorna 0 imediatamente para coleções vazias ou inválidas', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();
  db.questions = { bulkPut: async () => {} };
  db.transaction = async () => {
    assert.fail('Transação não deve ser iniciada para array vazio');
  };

  assert.equal(await db.syncQuestions([]), 0);
  assert.equal(await db.syncQuestions(null), 0);
  assert.equal(await db.syncQuestions(undefined), 0);
});

test('syncQuestions rejeita registros com ID inválido ou nulo antes de abrir transação', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();
  db.questions = { bulkPut: async () => {} };
  let transactionStarted = false;
  db.transaction = async (mode, table, cb) => {
    transactionStarted = true;
    return cb();
  };

  const invalidBatches = [
    [{ id: null, topic: 'Cardiologia' }],
    [{ id: 0, topic: 'Pediatria' }],
    [{ id: -5, topic: 'Cirurgia' }],
    [{ id: 'invalid_id', topic: 'GO' }],
    [null],
  ];

  for (const batch of invalidBatches) {
    await assert.rejects(
      async () => {
        await db.syncQuestions(batch);
      },
      (err) => {
        assert.ok(err && typeof err.message === 'string');
        assert.ok(err.message.includes('[MedQuestDB] Questão inválida'));
        return true;
      }
    );
  }

  assert.equal(transactionStarted, false, 'Nenhuma transação deve ser executada para dados corrompidos');
});

test('syncQuestions anexa owner_id e persiste via transação rw com bulkPut', async () => {
  const { MedQuestDB } = loadDbModule({
    window: {},
    localStorage: { getItem: () => 'user_test_medquest' },
  });
  const db = new MedQuestDB();

  let capturedMode = null;
  let persistedItems = null;

  db.questions = {
    bulkPut: async (items) => {
      persistedItems = items;
    },
  };

  db.transaction = async (mode, table, callback) => {
    capturedMode = mode;
    return callback();
  };

  const validQuestions = [
    { id: 101, topic: 'Hipertensão', area: 'Clínica Médica' },
    { id: 102, topic: 'Apendicite', area: 'Cirurgia' },
  ];

  const count = await db.syncQuestions(validQuestions, 'custom_owner');

  assert.equal(count, 2);
  assert.equal(capturedMode, 'rw');
  assert.equal(persistedItems.length, 2);
  assert.equal(persistedItems[0]._owner_id, 'custom_owner');
  assert.equal(persistedItems[1]._owner_id, 'custom_owner');
});

test('syncQuestions garante rollback e propaga exceção caso ocorra falha durante bulkPut', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();

  db.questions = {
    bulkPut: async () => {
      throw new Error('Dexie QuotaExceededError simulado');
    },
  };

  db.transaction = async (mode, table, callback) => {
    // Simula rollback automático do Dexie propagando o erro
    return callback();
  };

  const questions = [{ id: 201, topic: 'DPOC', area: 'Clínica Médica' }];

  await assert.rejects(
    async () => {
      await db.syncQuestions(questions);
    },
    (err) => {
      assert.ok(err && typeof err.message === 'string');
      assert.equal(err.message, 'Dexie QuotaExceededError simulado');
      return true;
    }
  );
});

test('helper syncQuestions exportado opera defensivamente em ambiente SSR', async () => {
  // SSR: window é undefined
  const { syncQuestions } = loadDbModule();
  const count = await syncQuestions([{ id: 301, topic: 'Trauma' }]);
  assert.equal(count, 0, 'SSR deve retornar 0 sem disparar erro');
});
