# MedQuest tab review — 2026-09-27

Scope: additional review after the earlier audit/fixes, against commit `464ad1b` plus the existing uncommitted changes. Application code was not changed during this review. Existing changes were preserved.

## Findings and recommended order

### 1. Active Review: keyboard activation can record the wrong grade — P1

`app/frontend/src/app/revisao-ativa/FlashcardClient.tsx:160–185`

The global key handler ignores inputs/selects, but not buttons or open dialogs. Once a card is revealed, Enter and Space call `handleReview("certeza")` and prevent the default action. A keyboard user focusing **Errei** or **Difícil** can therefore submit **Fácil** instead. The same handler remains enabled while the Anki dialog is open.

Fix: let focused interactive controls handle their native activation; disable card shortcuts while a modal is open. Cover Enter/Space on all three grading buttons and modal controls.

Browser reproduction confirmed: reveal card, focus **Errei**, press Enter; the outgoing review request contains `confidence: "certeza"`. The isolated reproduction passed in 1.7 seconds. Script retained at `/tmp/medquest-tab-keyboard-reproduction.spec.ts`; log at `/tmp/medquest-tabs-keyboard.log`. This test asserts the defect, not correct behavior, and was therefore removed from the application test suite after the audit.

### 2. Planner → Calendar: ISO exam dates bypass the deadline — P1

`app/frontend/src/lib/googleCalendar.ts:52`; `app/frontend/src/app/planner/PlannerWizard.tsx:150`

The wizard saves a full ISO timestamp, but Calendar appends `T00:00:00` to that timestamp. The resulting Invalid Date makes the deadline comparison always false.

Executed reproduction against the actual scheduling module: exam `2030-01-01` correctly rejects a block on January 2; exam `2030-01-01T12:00:00.000Z` schedules the same block after the exam. Normalize to a validated calendar date before comparing. Preserve the intentionally requested whole-topic scheduling behavior.

### 3. Planner → Analysis: multiple institutions become one nonexistent institution — P2

`app/frontend/src/app/planner/PlannerWizard.tsx:163`; `app/backend/api/plan.py:46–49`; `app/frontend/src/app/analise/page.tsx:24–27`

Planner stores `USP-SP, USP-RP` or `Todas as Bancas` as `target_institution`. Analysis passes this display string directly to APIs expecting one institution code. Both the initial readiness report and institution radar are affected.

Executed with an isolated seeded database: readiness for `USP-SP` returned one available question; `USP-SP, USP-RP` and `Todas as Bancas` each returned zero despite matching questions existing. Use a canonical primary institution for single-institution reports, or define explicit aggregate behavior. Never use the display label as a code.

### 4. Planner: completed-topic count doubles — P2

`app/frontend/src/app/planner/PlannerClient.tsx:303`; `app/backend/api/plan.py:127–133`

The API returns both `1:Topic=true` and `Topic=true` for one completion. The client counts all truthy map values. This displays two completions for one topic and can exceed 100%. Counting keys also includes completions outside the currently displayed plan.

Executed API reproduction confirmed both keys. Count completed topics from the displayed plan with one consistent completion predicate.

### 5. Planner: queued offline actions are presented as failures — P2

`app/frontend/src/app/planner/PlannerClient.tsx:240–264`; `app/frontend/src/lib/api.ts:54–75`

Planner mutations are durably queued offline and then throw `OfflineQueuedError`. Topic/reset handlers catch that as an ordinary failure; topic completion is visually reverted. The server may later apply an action that the UI said failed. A queued reset is particularly confusing because it clears progress after reconnection.

Handle queued success separately, show pending synchronization, and reconcile after delivery. Make queued reset status explicit.

### 6. Dashboard / Study: completed study appears resumable — P2

`app/frontend/src/app/DashboardClient.tsx:89–95`; `app/frontend/src/app/estudar/QuizClient.tsx:605–619`

Study persists its completed state as `FINISHED`. Dashboard excludes only `RESULTS`, which belongs to Simulado, so completed study qualifies for the active-session banner.

Use the actual quiz state contract: resume only `PLAYING`; optionally offer a separate link to the completed summary. Preserve completed summaries deliberately rather than deleting useful history.

### 7. Analysis: filter failures leave stale charts under the new selection — P2

`app/frontend/src/app/analise/AnalysisClient.tsx:69–104`

Changing the timeline range or institution updates the selected control immediately. If the request fails, the catch only logs to the console and leaves the previous data in place. The loading indicator clears, making old data appear to belong to the newly selected filter.

Show a visible error/retry and keep the displayed data associated with its successfully loaded filter, or revert the selection on failure. Also pass the abort signal through the readiness request to avoid unnecessary requests.

### 8. Dashboard: service errors look like zero progress — P2

`app/frontend/src/app/page.tsx:12–30,43–50`

Overview failures become zeroed `DEFAULT_STATS`, and planner failures become missing plans/progress. The client receives no error indicator or retry action. This is indistinguishable from an empty account and can mislead users about saved progress and pending reviews.

Represent unavailable data separately from zero. Allow per-section retries while keeping successful sections visible. Analysis has a related fallback issue: API failures become an apparent lack of evidence rather than a service error.

### 9. Simulado: obsolete summary write always returns 405 — P2

`app/frontend/src/app/simulado/SimuladoClient.tsx:559`; `app/frontend/src/lib/api.ts:217–235`; `app/backend/api/sessions.py`

Submission calls `POST /api/sessions/simulado`, but that endpoint only accepts GET, PUT and DELETE. An isolated API request confirmed HTTP 405. A separate effect at `SimuladoClient.tsx:919–932` writes the summary to the valid `/api/simulado/sessions` endpoint.

Remove the obsolete helper/call and centralize summary persistence at the supported endpoint, including recovery after offline submission. This is a redundant failed request, not proof that every exam loses its history: the second path currently provides the actual save.

### 10. Themes: “after theory” improvement is not measured after theory — P2

`app/backend/api/adaptive.py:125–149`; `app/frontend/src/app/temas/ThemeClient.tsx:58–63`

The backend defines diagnostic accuracy from the first five attempts, and practice accuracy from all later attempts. It does not partition by theory completion time or diagnostic session. The UI nevertheless describes practice accuracy as occurring after theoretical study. Repeated attempts on one question can fill the diagnostic sample even though the journey requires distinct answered questions.

Either label these as first-five versus subsequent attempts, or record session phase/theory completion time and calculate genuine before/after samples. Include sample sizes and avoid interpreting repeated-question exposure as demonstrated learning gain.

## Tab-by-tab coverage and improvements

| Tab | Evaluation | Additional improvement |
| --- | --- | --- |
| Dashboard | Findings 6 and 8; planner suggestions also use a different completion predicate from Planner. | Share completion semantics and expose partial-load status. |
| Planner | Findings 2–5; inspected setup, progress, reset and Calendar flow. | Normalize dates/institution codes at API boundaries; count only visible plan topics. |
| Coverage | Inspected search, status filters, priorities, area expansion and study/theme links. No additional data-corruption defect confirmed. | Add `aria-expanded`/`aria-controls` to area toggles and `aria-pressed` to filter buttons. Provide a compact mobile alternative to the seven-column table; current horizontal scrolling is intentional but cumbersome. |
| Study | Reviewed submission locks, offline handling, deferred review and session persistence; finding 6 affects the Dashboard integration. Existing resume/sync cases passed. | Keep completed-summary and resumable-session concepts distinct. Extract session/filter handling from the large client component after behavior is covered. |
| Simulado | Finding 9; inspected timer, submission, offline resolution and summary persistence. Existing exam/offline cases passed. | Add explicit timer-expiry plus server-failure coverage; centralize summary persistence. |
| Analysis | Findings 3, 7 and 8; reviewed filter state, SSR fallbacks and readiness evidence display. | Keep partial errors visible; reduce duplicate data fetching only after measuring route timings. |
| Active Review | Finding 1; inspected fetch, grading, offline queue and Anki interaction. Existing offline flow passed. | Keyboard and modal interaction tests are needed in addition to mouse-based grading tests. |
| Themes | Finding 10; inspected progression, theory save and diagnostic/practice/review links. | Use comparable samples and expose counts in learning-change summaries. |
| Search / shared navigation | `/buscar` redirects to Study; inspected header/sidebar and keyboard handling. | Preserve legacy query parameters if old search URLs must remain supported. Share navigation definitions; scope global shortcuts to noninteractive targets. |

## Validation and limits

- Existing Playwright suite: **56 passed**, 30.5 seconds. It mixes browser flows and pure utility cases; this is not 56 full-page visual checks. Log: `/tmp/medquest-tabs-e2e.log`.
- Executed scheduling reproduction against the actual TypeScript module.
- Executed completion-map, institution-readiness and obsolete summary endpoint checks against a temporary SQLite database. No production data was changed.
- Active Review's incorrect keyboard grade was additionally reproduced in Chromium. Remaining findings are supported by source/control-flow inspection.
- The mocked E2E environment bypasses server-side API fetches. It does not establish full populated Dashboard/Planner/Coverage rendering correctness. No claim of exhaustive mobile visual QA or performance profiling is made.
- Live Clerk, Google OAuth/Calendar, Anki and production service behavior were not exercised. No Calendar events or external account settings were changed.

Recommended implementation order: keyboard grading and Calendar deadline; then institution/date/progress contracts; then stale-data/error states and session-state integration; then redundant writes, measurement labels and accessibility improvements.
