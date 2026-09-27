import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
import ts from 'typescript';

function load(name, dependencies = {}, globals = {}) {
  dependencies = { './flashcardCache': { cacheCreatedFlashcards: async () => {} }, ...dependencies };
  const source = readFileSync(new URL(`../../src/lib/${name}.ts`, import.meta.url), 'utf8');
  const exports = {};
  runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText, { exports, require: id => {
    assert.ok(id in dependencies, `Unexpected import ${id}`); return dependencies[id];
  }, console, process: { env: {} }, setTimeout, clearTimeout, Headers, AbortController,
  AbortSignal, TypeError, crypto: globalThis.crypto, TextEncoder, URLSearchParams, ...globals });
  return exports;
}
function storage() {
  const map = new Map();
  return { map, getItem: k => map.get(k) ?? null, setItem: (k,v) => map.set(k,v),
    removeItem: k => map.delete(k), key: i => [...map.keys()][i], get length() { return map.size; } };
}

test('reading and removing a session never migrates or erases another owner', async () => {
  const localStorage = storage();
  localStorage.setItem('medquest_quiz_state_v2:alice', '{"private":true}');
  const { readLearningSession, removeLearningSession } = load('sessionState', {
    './db': { getLocalOwnerId: () => 'bob' }, './api': { api: { sessions: { delete: async () => {} } } },
  }, { localStorage, sessionStorage: storage() });
  assert.equal(readLearningSession('quiz', () => true), null);
  removeLearningSession('quiz');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(localStorage.getItem('medquest_quiz_state_v2:alice'), '{"private":true}');
});

test('a delayed session write is cancelled when the active account changes', async () => {
  let owner = 'alice'; let callback; let calls = 0;
  const { writeLearningSession } = load('sessionState', {
    './db': { getLocalOwnerId: () => owner }, './api': { api: { sessions: { save: async () => { calls++; } } } },
  }, { localStorage: storage(), sessionStorage: storage(), setTimeout: fn => { callback = fn; return 1; } });
  writeLearningSession('quiz', { answer: 'A' });
  owner = 'bob'; callback();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 0);
});

test('offline card creation is durable and cannot return a fabricated server ID', async () => {
  const queued = [];
  const { api, OfflineQueuedError } = load('api', {
    './db': { getLocalOwnerId: () => 'alice' }, './sync': { syncManager: { enqueue: async (...args) => { queued.push(args); return 'pending'; } } },
  }, { window: {}, navigator: { onLine: false } });
  await assert.rejects(api.flashcards.save(1, 'Front', 'Back', 'Context'), OfflineQueuedError);
  await assert.rejects(api.flashcards.generate(1, 'A'), OfflineQueuedError);
  await assert.rejects(api.flashcards.generateBatch([{ question_id: 1, wrong_letter: 'A' }]), OfflineQueuedError);
  assert.equal(queued.length, 3);
  assert.equal(JSON.parse(queued[0][1].body).front, 'Front');
  assert.ok(queued.every(item => item[2]));
});

test('server authorization failures are not disguised as local card saves', async () => {
  let queued = 0;
  const { api } = load('api', { './db': { getLocalOwnerId: () => 'alice' }, './sync': { syncManager: { enqueue: async () => { queued++; } } } }, {
    window: {}, navigator: { onLine: true }, fetch: async () => ({ ok: false, status: 403, json: async () => ({ error: 'Forbidden' }) }),
  });
  await assert.rejects(api.flashcards.save(1, 'Front', 'Back', 'Context'), /Forbidden/);
  assert.equal(queued, 0);
});

test('download traverses all pages of cards', async () => {
  const urls = [];
  const { api } = load('api', { './db': { getLocalOwnerId: () => 'alice' }, './sync': {} }, { fetch: async url => {
    urls.push(url);
    return { ok: true, json: async () => urls.length === 1
      ? Array.from({length:100}, (_,i) => ({id:i+1})) : [{id:101}] };
  } });
  assert.equal((await api.flashcards.downloadAll()).length, 101);
  assert.match(urls[1], /after_id=100/);
});

const plan = [{ week: 1, date: '2030-01-01', topics: [{subtema:'Example',area:'Area',estimated_hours:6}] }];
test('calendar schedule skips weekends, respects daily capacity and avoids past times', () => {
  const { scheduleStudyBlocks } = load('googleCalendar');
  const blocks = scheduleStudyBlocks(plan, { days_per_week:5, hours_per_day:2 }, {}, new Date('2030-01-04T15:00:00'));
  assert.equal(blocks.length, 3);
  assert.equal(blocks[0].start.getDay(), 1);
  assert.equal(blocks[0].start.getHours(), 8);
  assert.ok(blocks.every(b => (b.end - b.start) === 120 * 60000));
  assert.throws(() => scheduleStudyBlocks(plan, {days_per_week:5,hours_per_day:2,exam_date:'2030-01-08'}, {}, new Date('2030-01-04T15:00:00')), /não cabe/);
});
function calendar(fetch, completions = []) {
  const api = load('googleCalendar', {}, {
    process: {env:{NEXT_PUBLIC_GOOGLE_CLIENT_ID:'test'}}, fetch,
    window: { google: {accounts:{oauth2:{initTokenClient: config => ({requestAccessToken: () => config.callback({access_token:'test'})})}}} },
  });
  return () => api.syncPlanToGoogleCalendar(plan, {config:{days_per_week:5,hours_per_day:4},ownerId:'alice',completed:{},onComplete:async (...args) => completions.push(args)});
}
test('calendar HTTP failures reject instead of announcing success', async () => {
  let calls = 0;
  const sync = calendar(async () => { calls++; return {ok:false,status:403}; });
  await assert.rejects(sync(), /403/);
  assert.equal(calls, 1);
});
test('calendar uses every page, preserves completed legacy events and imports completion', async () => {
  const urls = []; const completions = [];
  const sync = calendar(async url => { urls.push(url); return {ok:true,status:200,json:async () => urls.length === 1
    ? {items:[],nextPageToken:'second'} : {items:[{id:'legacy',summary:'[MedQuest] 📖 Example (Area)',colorId:'8'}]} }; }, completions);
  await sync();
  assert.equal(urls.length, 2);
  assert.match(urls[1], /pageToken=second/);
  assert.deepEqual(completions, [[1, 'Example']]);
});
test('retrying a partial calendar sync updates the same IDs without deleting events', async () => {
  const events = new Map(); let fail = true; const methods = [];
  const sync = calendar(async (url, init) => {
    const method = init.method || 'GET'; methods.push(method);
    if (method === 'GET') return {ok:true,status:200,json:async () => ({items:[...events.values()]})};
    const body = JSON.parse(init.body);
    if (events.size === 1 && fail) { fail = false; return {ok:false,status:503}; }
    const id = body.id || url.split('/').pop();
    events.set(id, {...body,id});
    return {ok:true,status:200,json:async () => ({id})};
  });
  await assert.rejects(sync(), /503/);
  await sync();
  assert.equal(events.size, 2);
  assert.ok(methods.includes('PATCH'));
  assert.ok(!methods.includes('DELETE'));
});

test('sync retries a processing conflict but stops for a mismatched idempotency key', async () => {
  for (const [code, expected] of [['idempotency_processing', 'pending'], ['payload_mismatch', 'failed']]) {
    const item = {id:'request',owner_id:'alice',endpoint:'/api/flashcards/1/review',method:'POST',body:'{}',status:'pending',retry_count:0,next_retry_at:0};
    const queue = { where: () => ({equals: () => ({filter: fn => ({toArray: async () => fn(item) ? [item] : [],count:async () => 1})})}),
      update: async (_, change) => Object.assign(item, change) };
    const { syncManager } = load('sync', {'./db': {getLocalOwnerId: () => 'alice',localDb:{syncQueue:queue}}}, {
      window:{dispatchEvent(){}},navigator:{onLine:true},CustomEvent:class {},
      fetch:async () => ({ok:false,status:409,headers:new Headers({'Retry-After':'2'}),json:async () => ({code})}),
    });
    await syncManager.sync();
    assert.equal(item.status, expected);
    if (expected === 'pending') assert.ok(item.next_retry_at > Date.now());
  }
});

test('a request started by Alice is not queued as Bob after an account switch', async () => {
  let owner = 'alice'; let queued = 0;
  const { api } = load('api', {'./db':{getLocalOwnerId: () => owner},'./sync':{syncManager:{enqueue:async () => {queued++;}}}}, {
    window:{},navigator:{onLine:true},fetch:async () => {owner = 'bob'; throw new TypeError('Network failed');},
  });
  await assert.rejects(api.flashcards.save(1,'Front','Back','Context'), /Network failed/);
  assert.equal(queued, 0);
});

test('deck deletion invalidates only the current owners matching cached cards', async () => {
  const cards = [{id:1,_owner_id:'alice',deck_name:'Geral'},{id:2,_owner_id:'bob',deck_name:'Geral'},{id:3,_owner_id:'alice',deck_name:'Other'}];
  const { api } = load('api', {'./db':{getLocalOwnerId: () => 'alice',localDb:{flashcards:{where: () => ({equals: owner => ({filter: fn => ({delete: async () => {
    for (let i=cards.length-1;i>=0;i--) if(cards[i]._owner_id === owner && fn(cards[i])) cards.splice(i,1);
  }})})})}}}, './sync':{syncManager:{sync:async () => {},getQueue:async () => [],getFailedItems:async () => []}}}, {
    window:{},navigator:{onLine:true},fetch:async () => ({ok:true,json:async () => ({success:true,deck_name:'Geral',deleted_count:1})}),
  });
  await api.flashcards.deleteDeck('Geral');
  assert.deepEqual(cards.map(c=>c.id), [2,3]);
});
