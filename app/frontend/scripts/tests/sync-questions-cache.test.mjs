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
    console: { log() {}, info() {}, warn() {}, error() {} },
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

test('isQuotaExceededError detecta acuradamente erros de cota e ignora outros erros', () => {
  const { isQuotaExceededError } = loadDbModule({ window: {} });

  // DOMException
  const domErr = { name: 'QuotaExceededError', code: 22 };
  assert.equal(isQuotaExceededError(domErr), true);

  // Erro com nome QuotaExceededError
  const namedErr = new Error('Storage full');
  namedErr.name = 'QuotaExceededError';
  assert.equal(isQuotaExceededError(namedErr), true);

  // Mensagem contendo regex de quota
  const msgErr = new Error('The quota has been exceeded on disk');
  assert.equal(isQuotaExceededError(msgErr), true);

  // Erro encapsulado (inner error)
  const wrappedErr = { inner: { name: 'QuotaExceededError' } };
  assert.equal(isQuotaExceededError(wrappedErr), true);

  // Falha em lote com failures
  const bulkErr = { failures: [{ name: 'QuotaExceededError' }] };
  assert.equal(isQuotaExceededError(bulkErr), true);

  // Erros comuns não relacionados a quota
  assert.equal(isQuotaExceededError(new Error('Network disconnected')), false);
  assert.equal(isQuotaExceededError(new TypeError('Invalid argument')), false);
  assert.equal(isQuotaExceededError(null), false);
  assert.equal(isQuotaExceededError(undefined), false);
});

test('purgeExpiredSimuladoPackages expurga atomicamente pacotes vencidos e preserva pacotes válidos', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();

  const now = 1700000000000;
  const packagesList = [
    { id: 'pkg-expired-status', status: 'expired', expires_at: now + 10000 },
    { id: 'pkg-expired-time', status: 'ready', expires_at: now - 5000 },
    { id: 'pkg-valid-ready', status: 'ready', expires_at: now + 50000 },
    { id: 'pkg-valid-downloading', status: 'downloading', expires_at: now + 20000 },
  ];

  let deletedIds = null;
  let transactionTable = null;

  db.simuladoPackages = {
    toArray: async () => [...packagesList],
    bulkDelete: async (ids) => {
      deletedIds = ids;
    },
  };

  db.transaction = async (mode, table, callback) => {
    assert.equal(mode, 'rw');
    transactionTable = table;
    return callback();
  };

  const purgedCount = await db.purgeExpiredSimuladoPackages(now);

  assert.equal(purgedCount, 2, 'Deve expurgar exatamente os 2 pacotes vencidos');
  assert.deepEqual(Array.from(deletedIds), ['pkg-expired-status', 'pkg-expired-time']);
  assert.equal(transactionTable, db.simuladoPackages);
});

test('syncQuestions detecta QuotaExceededError, executa evicção e retenta com sucesso quando espaço é liberado', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();

  let attemptCount = 0;
  const savedBatches = [];

  db.questions = {
    bulkPut: async (items) => {
      attemptCount++;
      if (attemptCount === 1) {
        const quotaErr = new Error('The quota has been exceeded');
        quotaErr.name = 'QuotaExceededError';
        throw quotaErr;
      }
      savedBatches.push(items);
    },
  };

  let purgedCalled = false;
  db.simuladoPackages = {
    toArray: async () => [
      { id: 'pkg-old', status: 'expired', expires_at: 1000 },
    ],
    bulkDelete: async () => {
      purgedCalled = true;
    },
  };

  db.transaction = async (mode, table, callback) => {
    return callback();
  };

  const questions = [
    { id: 401, topic: 'Asma Aguda', area: 'Pediatria' },
    { id: 402, topic: 'Cetoacidose', area: 'Clínica Médica' },
  ];

  const result = await db.syncQuestions(questions, 'user_eviction_test');

  assert.equal(result, 2, 'Deve retornar contagem de questões após retentativa bem-sucedida');
  assert.equal(attemptCount, 2, 'Deve ter tentado duas vezes (falha inicial + retry pós-purga)');
  assert.equal(purgedCalled, true, 'Purga deve ter sido executada durante o fluxo de recuperação');
  assert.equal(savedBatches.length, 1);
  assert.equal(savedBatches[0][0].id, 401);
});

test('syncQuestions detecta QuotaExceededError, mas aborta e relança quando não há pacotes expirados para evicção', async () => {
  const { MedQuestDB } = loadDbModule({ window: {} });
  const db = new MedQuestDB();

  let attemptCount = 0;

  db.questions = {
    bulkPut: async () => {
      attemptCount++;
      const quotaErr = new Error('QuotaExceededError: no space left');
      quotaErr.name = 'QuotaExceededError';
      throw quotaErr;
    },
  };

  db.simuladoPackages = {
    toArray: async () => [
      // Todos os pacotes são válidos e recentes (nenhum expirado)
      { id: 'pkg-fresh', status: 'ready', expires_at: Date.now() + 1000000 },
    ],
    bulkDelete: async () => {
      assert.fail('bulkDelete não deve ser chamado quando não há pacotes expirados');
    },
  };

  db.transaction = async (mode, table, callback) => {
    return callback();
  };

  const questions = [{ id: 501, topic: 'IAM com Supra', area: 'Clínica Médica' }];

  await assert.rejects(
    async () => {
      await db.syncQuestions(questions);
    },
    (err) => {
      assert.ok(err && typeof err.message === 'string');
      assert.equal(err.name, 'QuotaExceededError');
      return true;
    }
  );

  assert.equal(attemptCount, 1, 'Não deve retentar persistência se não houve espaço liberado');
});

test('helper purgeExpiredSimuladoPackages opera defensivamente em ambiente SSR', async () => {
  // SSR: window é undefined
  const { purgeExpiredSimuladoPackages } = loadDbModule();
  const count = await purgeExpiredSimuladoPackages();
  assert.equal(count, 0, 'SSR deve retornar 0 sem disparar erro');
});
