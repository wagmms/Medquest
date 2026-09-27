# Follow-up on the ten tab-review findings

Reviewed the relocated checkout at `/home/wagmoraes/Projetos IA/MedQuest`, starting from `0d77758` (clean working tree). Existing user changes were preserved. No deployment, database migration or live integration mutation was performed.

| Original finding | State in the latest user version | Follow-up |
| --- | --- | --- |
| Active Review records the wrong keyboard grade | Anki modal guard added, but Enter/Space on grading buttons still reached the global Easy shortcut. | Ignore handled/repeated/modified keystrokes, editable/interactive targets and open modal dialogs. Six Chromium cases verify all three grades with Enter and Space. |
| Calendar ISO exam date bypasses deadline | Fixed by extracting the date portion. | Preserved. Added a regression that rejects a post-exam block for both date-only and full ISO inputs. Whole-topic scheduling remains intact. |
| Multiple institutions produce empty readiness | Fixed in backend normalization, primary-institution metadata and Analysis initialization. | Preserved and verified with existing Planner API tests, including composite and all-institution cases. |
| Planner completion count doubles | Fixed by counting topics from the displayed plan. | Preserved. Dashboard now also respects the completion aliases used by Planner after a topic changes weeks. |
| Offline Planner mutations appear to fail | Topic/week handlers fixed; reset deliberately excluded from queuing. Setup still used an error state for queued configuration and had no recovery notification. | Added a pending-sync state to setup, blocked repeated submission while pending, and refreshed after successful queued Planner updates. Verified resets are not queued. |
| Completed study session appears resumable | Fixed: Dashboard accepts quiz state PLAYING only. | Preserved. |
| Analysis shows stale results and cannot retry | Error messages and abort signals added, but retry buttons set state to its existing value, triggering no fetch. Old charts remained visible under the new selection. | Explicit retry counters trigger new requests. Failed sections hide stale results; successful results identify the institution/range they represent. Initial server failures feed the same error states. Chromium verifies failure, unchanged-filter retry and recovery. |
| Dashboard masks API failures | Overview error panel added. Planner fetch failures still became empty progress and generated misleading suggestions. Analysis SSR also used silent empty defaults. | Keep Planner failure separate from empty progress and show a retry panel. Add an initial-load warning listing unavailable Analysis sections. Six server-rendering unit cases check Dashboard failure and completion behavior. |
| Simulado redundant summary request | Endpoint corrected, but both the submit handler and results effect still wrote the summary, potentially with different filters. | Removed redundant helper/call. One guarded results effect handles normal and offline recovery; summaries use durable queuing on network failure. Browser test verifies a single summary request with correct counts. |
| Theme “after theory” comparison is misleading | Still present; backend still groups the first five attempts versus later attempts. | Label the actual measurement, show subsequent sample count, and explicitly note repeated questions and absence of a before/after-theory split. No score algorithm changed. |

## Validation

- Production build passed, including TypeScript, service-worker checks and performance budgets (2,403,366 total JavaScript bytes, largest chunk 412,658 bytes).
- Frontend unit suite: 32 passed.
- Planner backend suite: 24 passed, including institution normalization. Pytest emitted only a read-only cache warning; tests use temporary databases.
- Existing backend exam-summary persistence test: passed.
- Browser suite: **65 passed in 37.7 seconds** in the final full run. The first run exposed one obsolete answer-button selector from the new strikethrough markup and one incomplete mock in the new Analysis regression. Both fixtures were corrected; the targeted rerun passed all 9 cases.
- ESLint passed without errors or warnings; `git diff --check` passed.

Live Clerk, Google Calendar and Anki were not exercised. The existing Material Symbols font precache warning remains; it does not fail the build. The browser suite includes both browser flows and utility cases and is not exhaustive production or mobile visual testing.

Logs: `/tmp/medquest-followup-build.log`, `/tmp/medquest-followup-unit.log`, `/tmp/medquest-followup-backend.log`, `/tmp/medquest-followup-summary-backend.log`, `/tmp/medquest-followup-e2e-final.log`, `/tmp/medquest-followup-lint-final.log`.
