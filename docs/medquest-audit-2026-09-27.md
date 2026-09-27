# MedQuest audit — 2026-09-27

Scope: local source review of authentication, session persistence, offline requests, flashcards, calendar integration, SSR loading, validation and cleanup opportunities. No application code was changed. Existing changes in `app/backend/api/stats.py` and `app/backend/api/webpush.py` were preserved. This is not a live-production or visual accessibility audit.

Investigation sequence: inventory and validation → account boundaries and persistence → flashcards and calendar workflows → performance and unused code → deterministic reproductions and prioritization.

## Confirmed findings

### 1. High: saved learning sessions cross account boundaries

Location: `app/frontend/src/lib/sessionState.ts:39–79`.

When the current owner has no session, `readLearningSession` scans keys belonging to every owner, copies the first valid session into the current owner's key, and deletes the original. `removeLearningSession` likewise deletes every owner's keys for that session kind.

Reproduced with the actual transpiled module and an in-memory localStorage: user B received user A's saved answer; A's original key disappeared. Clearing B's session also deleted a freshly seeded A key. This can expose another account's study session and erase it on shared browsers.

Fix: read and delete only the current owner's key. Any guest-to-account migration needs an explicitly identified source owner. Add account-switch tests covering quiz and simulado. Also review `db.ts:19–38`: the remembered last user is accepted even when Clerk has no user, while the sign-out handler in `AccountModal.tsx:474` does not clear that marker.

### 2. High: offline-created flashcards never enter the upload queue

Location: `app/frontend/src/lib/api.ts:591–848`.

`save`, `generate`, and `generateBatch` return locally created cards with timestamp-based IDs when offline, but do not enqueue creation requests. The same fallback can hide online server errors. The offline queue allowlist covers attempts, reviews, favorites and planner operations, not these creation routes.

Reproduced `api.flashcards.save` with a cached question and offline navigator: one local card, a successful return value, and zero queued uploads. Later review requests use a local ID that the server does not know. Online review lists also come from the server and omit these local-only cards.

Fix: persist pending creations, upload them idempotently, reconcile local/server IDs before replaying reviews, and explicitly distinguish a pending local save from a server save. Do not mask authorization/validation errors as successful saves.

### 3. High: Calendar sync reports success on HTTP failures and can leave a partial replacement

Location: `app/frontend/src/lib/googleCalendar.ts:246–253,319–374`.

`advancedTwoWaySync` does not check HTTP status on listing, deletion or insertion. It deletes existing unfinished MedQuest events before creating replacements, and catches deletion network errors without stopping. A failed insertion can therefore leave an incomplete calendar while the UI announces success.

Reproduced with the real module and a mocked token callback: every fetch returned HTTP 403, yet the function returned `{ success: true, calendarId: 'primary' }` after GET and POST. No real calendar was accessed.

Fix: validate every response, propagate failures, track per-event outcomes, and use stable event identities for upserts rather than unconditional deletion followed by recreation. Handle event-list pagination; the current code ignores `nextPageToken`.

### 4. Medium: Calendar scheduling ignores study-day settings

Location: `app/frontend/src/lib/googleCalendar.ts:331–371`.

`studyDaysCount` is computed but unused. The active sync path schedules one topic every calendar day regardless of `daysPerWeek`, starting today at 08:00 even when that time has passed. Rotation priorities are also hardcoded to one class and date range.

Fix: derive dates, daily capacity and rotation priorities from saved planner configuration. Add deterministic cases for five-day schedules, afternoon sync, long topics and date boundaries. The advertised two-way sync also never writes calendar completion state back to the app; the source contains a comment acknowledging that missing step.

### 5. Medium: offline flashcard downloads silently stop at 50

Locations: `app/frontend/src/components/OfflinePanel.tsx:95`, `app/frontend/src/lib/api.ts:850–885`, `app/backend/api/flashcards.py:760–805`.

The download uses `getDue(true)`, which sends `all=true`. The backend removes the due-date filter but retains its default 50-row limit. There is no client pagination. Reproduced against an isolated temporary SQLite database containing 60 cards: HTTP 200 returned only 50.

Fix: add a paginated download contract and fetch every page, or explicitly disclose a capped download and let the user choose what to retain. A larger fixed limit alone does not solve this.

### 6. Medium: deleted decks remain available in the offline cache

Locations: `app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx:259–273`, `app/frontend/src/lib/api.ts:969–974`.

Deck deletion calls the server and refreshes the UI, but neither step removes the owner's matching IndexedDB cards. The offline review fallback reads those cached cards again. Source tracing confirms the missing invalidation; this was not exercised in a browser.

Fix: after confirmed deletion, remove the matching local cards and reconcile queued reviews for deleted IDs. Test download → delete deck online → reopen offline.

### 7. Medium: temporary idempotency conflicts become terminal sync failures

Locations: `app/backend/api/idempotency.py:134–151`, `app/frontend/src/lib/sync.ts:282–314`.

The backend returns 409 when an earlier request with the same key is still processing. The sync manager treats all 409 responses as terminal failures. A timed-out request that is still running can therefore stop automatic recovery on its first retry, despite being recoverable after completion or lease expiry.

Fix: give processing conflicts a distinct machine-readable code and retry delay. Retry only that condition; keep a true key/payload mismatch terminal. This finding is based on matching the two code paths, not a live concurrency test.

### 8. Medium: frontend lint gate fails

`npm run lint -- --max-warnings=0` reports three errors and two warnings:

- `SimuladoClient.tsx:153`: incompatible manual memoization dependencies.
- `googleCalendar.ts:237`: explicit `any`.
- `googleCalendar.ts:332`: `prefer-const`.
- `googleCalendar.ts:331`: unused study-day count, tied to finding 4.
- `PlannerClient.tsx:210`: unused `handleDirectGoogleSync`.

Fix the behavior and types rather than suppressing these rules.

## Performance and simplification

- **Remove SSR waterfalls.** `app/frontend/src/app/analise/page.tsx:21–56` waits for nine requests, then overview, then potentially a second readiness request, then radar. Fetch overview with the first group and run institution-dependent work together once its input is available. The dashboard similarly fetches overview and currentUser before its independent data group. These are source-level opportunities; no production latency improvement was measured.
- **Use the existing compound IndexedDB key.** Queries such as `where('_owner_id').equals(uid).filter(q => q.id === id)` in `api.ts` scan an owner's rows to find a known ID. The schema already defines `[id+_owner_id]`; use direct compound-key reads/deletes. Flashcard normalization currently repeats owner scans once per card.
- **Consolidate duplicate flashcard formatting.** The local `formatLocalCard` implementations inside `generate` and `generateBatch` are effectively duplicated. Extract one formatter and one local-card creation/reconciliation helper while fixing finding 2.
- **Remove unreachable calendar UI code.** `handleDirectGoogleSync` has no caller. Its only call to `syncPlanToGoogleCalendarDirectly` makes that export unreachable from the active UI as well. Choose whether to retire the old path or deliberately expose it; do not maintain two divergent scheduling implementations by accident.
- **Remove obsolete type packages after validation.** Installed `react-window` 2.3.0 and `react-virtualized-auto-sizer` 2.0.3 both declare bundled types, while the app also installs their older v1 `@types` packages. Remove the redundant declarations and rerun type-checking.
- **Review unused exports deliberately.** No application callers were found for `clearAllSimuladoPackages`. `cleanup_idempotency_keys` has test callers but no runtime caller in the repository; this likely needs a scheduled maintenance entrypoint rather than deletion, otherwise stored idempotency responses can accumulate.
- **Split large modules by responsibility.** QuizClient is 2,063 lines, SimuladoClient 1,981, api.ts 1,020, stats.py 1,676, and questions.py 1,394 in this checkout. Extract persistence, request orchestration and presentation separately after fixing the data bugs. File length alone is not a defect.

## Validation and limits

| Check | Result |
|---|---|
| Backend `pytest -q` | 288 passed, 16.35 seconds |
| Backend performance guardrails | All five passed on synthetic local SQLite data |
| Frontend unit command | Passed; runner reported one test file |
| `tsc --noEmit --incremental false` | Passed |
| Strict frontend lint | Failed: 3 errors, 2 warnings |
| Production build | Blocked: Next.js could not parse TypeScript `--showConfig` output |
| Account/flashcard/calendar reproductions | Confirmed using real transpiled modules with deterministic doubles |
| Flashcard download cap | Confirmed with a temporary database |

Build diagnosis: standalone `tsc --showConfig` produced 5,494 bytes of valid output, but invoking Next.js's installed `runTypeScriptCli` helper returned exit code 0 with zero stdout bytes. The cause of that subprocess behavior is unresolved; it is not evidence that the TypeScript configuration itself is invalid. No dependency or configuration workaround was applied.

The missing completed standalone build prevented the configured production-server Playwright workflow. Browser appearance, mobile layout, keyboard accessibility, service-worker behavior, live Clerk/Calendar integration, production database latency and dependency security advisories remain unverified. Passing synthetic backend performance checks does not establish production SLAs.

Reproduction harness for this session: `/tmp/medquest-audit-repro.cjs`. Validation logs: `/tmp/medquest-audit-{lint,types,unit,build,performance}.log`.

## Recommended implementation order

1. Restore session ownership boundaries and add shared-browser regression coverage.
2. Repair offline flashcard creation/reconciliation and calendar failure handling.
3. Fix calendar scheduling, download pagination, cache invalidation and temporary-conflict retries.
4. Restore lint/build gates and run browser regressions against the completed production build.
5. Apply measured SSR and IndexedDB optimizations, then remove verified dead code.

## Implementation follow-up

The audit fixes have been implemented. The original findings above describe the pre-fix checkout.

- Session reads/deletes are owner-scoped. Delayed cloud writes and sync completion events are guarded across account changes; session restoration waits for identity resolution. Different study filters now start a new session, while the unfiltered study page offers the resume banner.
- Offline flashcard creation uses the durable request queue and displays a pending message. There are no fabricated local card IDs; confirmed responses populate the local cache. Creation and review effects are committed atomically with their idempotency response. Processing conflicts have a retryable code; authorization and payload errors remain errors.
- Full flashcard downloads use an ID cursor. Deck deletion invalidates only the owner's matching cache, waits for pending flashcard operations, and supports legacy unnamed default-deck cards.
- Calendar integration uses checked, paginated requests and stable event IDs. Completed topics can synchronize back to the planner. The later committed scheduling preference is preserved: each topic remains a whole block, times are rounded to 15 minutes, and the daily target may be exceeded to finish that topic. Old fragments are removed only after replacements succeed; cleanup failures are surfaced rather than swallowed. OAuth timeout/error handling from the newer commits is preserved.
- SSR request waterfalls were reduced, direct IndexedDB key lookups replaced scans, duplicate/offline placeholder code and obsolete type packages were removed, and an explicit `cleanup-idempotency` maintenance command was added. No automatic maintenance schedule was installed.
- The analysis page now recovers institution options on the client if its initial server fetch failed. Browser assertions were corrected for the current review completion message and intentional suppression of scores with insufficient evidence. Test cookies now match the configured test host and avoid external authentication redirects.

Validation: 293 backend tests and 5 deployment tests passed. The frontend regression suite has 19 passing tests, including failed Calendar requests, partial sync recovery, legacy-fragment cleanup, account isolation, queued card creation, pagination and cache invalidation. The final complete browser run passed all 56 tests in 31.1 seconds, including analysis recovery, study resume, offline packages and flashcard review. Strict lint passes. The final production build, service-worker checks and bundle budgets passed (2,317,478 total JavaScript bytes, largest chunk 411,138 bytes); the sandbox subprocess restriction was resolved by running the build with the required execution permission, without disabling type checks. All five synthetic backend performance guardrails passed.

Limits: live authenticated Clerk/Google Calendar flows and production database latency were not tested. The Material Symbols font still produces a 3.96 MB precache warning and is a separate optimization opportunity. Broad module decomposition was deferred in favor of the concrete correctness and duplication fixes.

Calendar implementation references: [event IDs and insertion](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [pagination](https://developers.google.com/workspace/calendar/api/guides/pagination), and [private extended properties](https://developers.google.com/workspace/calendar/api/guides/extended-properties).
