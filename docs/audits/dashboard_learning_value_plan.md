# Dashboard: learning value review and implementation plan

Review date: 2026-09-29. Scope: current local Dashboard rendering, its server loader, and underlying metric calculations. This is a source-based product review; no authenticated personal results or rendered browser session were inspected. Existing uncommitted Analysis changes were inspected as potential dependencies and left untouched. No application behavior was changed and no tests were run for this document-only review.

## Recommendation

Make the Dashboard a short daily decision page: what deserves attention, what to do now, and whether recent practice shows improvement. Keep detailed comparisons, charts, and methodology in Analysis. Completion of work and evidence of learning must have separate labels.

The current page is useful for starting sessions and organizing workload, but cannot reliably answer whether the learner is closing knowledge gaps. Its most valuable building block is the error notebook; its least defensible headline is estimated readiness based on all-attempt accuracy.

## Keep, change, move, or remove

| Existing element | Decision | Reason / replacement |
| --- | --- | --- |
| Resume session | Keep, compact | Saves work and reduces friction. An old session should not hide today's priorities. |
| Primary recommended action | Keep, redesign | Explain the topic, supporting evidence, session size, and follow-up. Allow a different task when appropriate. |
| Due question and flashcard reviews | Keep | Useful scheduling information. Separate their counts and time estimates; a backlog is not itself a measure of poor learning. |
| Daily question goal | Keep, reduce prominence | Measures activity. Distinguish first exposures from reviewed questions and do not imply completion establishes mastery. |
| Suggested planner topic | Change | Identify it as the next unfinished planner topic, a demonstrated gap, or a general suggestion. Those are different reasons. |
| Error notebook and top three topics | Promote and expand | Show latest unresolved errors, repeated errors, sample size, and corrected items awaiting a delayed check. Offer targeted actions. |
| Weekly pace | Merge into a compact routine summary | Keep for workload planning. Its current all-attempt percentage does not establish improvement. |
| Estimated readiness / competitive badge | Remove from the Dashboard in its current form | It compares historical all-attempt accuracy with a configured/default target. Replace with observed first-attempt and delayed-review results. |
| Coverage footer | Correct, then keep as a secondary link | Never switch between question-bank coverage and a topic mastery heuristic under one label. Prefer assessed versus unassessed topics with a clear denominator. |
| Exam countdown | Keep small | Planning context, not evidence of learning. |
| Streak | Optional, secondary | A routine cue; no need to expand it or add an activity heatmap to the main dashboard. |
| Repeated error totals and review buttons | Consolidate | The hero, daily plan, error section, and footer repeat information without adding evidence. |
| Automatic confetti | Remove current trigger | Zero due reviews plus any historical answer does not mean a task was completed today. Celebrate an actual completion event at most once. |
| Offline controls | Keep as utility | Useful for access; show the banner when offline and keep management outside the learning metrics. |

## Confirmed implementation findings

### 1. Readiness is an accuracy comparison, not a calibrated readiness estimate

`DashboardClient.tsx:169–170,820–889` uses `accuracy_all_attempts`, subtracts a target, and chooses a badge. There is no uncertainty interval or exam representativeness check in this card. Twenty distinct questions only unlock visibility; repeat attempts still contribute to the numerator and denominator. The difference is in percentage points, although the badge uses `%`.

`stats.py:benchmark` supplies a default 76% target and a constant `competitors_average_pct`; neither establishes a real exam cutoff or peer comparison. Do not elevate that constant into the redesigned page. A user-selected target should be called a personal target unless an actual cutoff has a verified source.

### 2. Error resolution is not verification of durable correction

`stats.py:error_notebook_summary` counts a question as unresolved when its latest attempt by ID is wrong. One subsequent correct answer removes it. This is a legitimate notebook status, but it cannot distinguish an immediate retry from successful later recall.

Replace “clean all errors” framing with “review errors.” Track distinct states: latest response incorrect; corrected but follow-up pending; correct on a delayed check. Success on different questions in the same topic provides additional evidence, but should not automatically be attributed to the correction intervention or called mastery.

### 3. The clean-notebook message can be false

`page.tsx:49` converts a failed bottleneck request into `[]`. `DashboardClient.tsx:766–775` interprets an empty list as a completely clean notebook. The bottleneck query also excludes missing subtopics, whereas the notebook total does not require a subtopic. Consequently an empty topic list is not proof of zero unresolved errors.

Use explicit loading/error/empty states. Only show zero unresolved errors after a successful authoritative summary reports zero. If errors exist without usable topic classification, display their total and a general review action.

### 4. Priorities favor volume and planner order

The hero checks an active session, all due reviews, the daily goal, then unresolved errors. Error correction becomes the main action only after the question goal is met, although the separate notebook remains accessible earlier. There is no workload cap in the due-review recommendation; estimated time is a fixed 1.5 minutes per item across both questions and flashcards.

`page.tsx:75–90` chooses the first pending topic from the first unfinished planner week. `stats.py:bottlenecks` sorts by unresolved count, then historical wrong and total attempts. It does not rank recent deterioration, exam importance, or error rate relative to exposure. A heavily practiced topic can dominate simply because it has more recorded mistakes.

Use a small, explainable priority queue with bounded sessions. Keep room for follow-up checks and unassessed material so neither a backlog nor unfinished planner work consumes every recommendation. Validate the ranking as a product heuristic; do not present arbitrary weights as an optimal learning policy.

### 5. Coverage changes meaning silently

`DashboardClient.tsx:901–902` displays `overall_domain_pct`, falling back to `coverage_pct`. The former is the percentage of subtopics meeting an attempts/accuracy heuristic; the latter is distinct answered questions divided by bank size. These measures are not interchangeable. The mastery heuristic itself can be satisfied through repeated attempts because it does not require distinct questions or delayed performance.

Use separate stable definitions. “No data” is better than substituting another metric after a failed request.

### 6. Some suggestions claim more personalization than exists

Without a planner topic or bottleneck, the suggested topic defaults to Clínica Médica, but the hero opens an unfiltered new-question session. The topic card can say “based on exam priorities” even when its source is a bottleneck or this fallback. Topic-specific links omit area and institution.

Every recommendation must state its actual source and preserve its advertised scope. A fallback should say “general practice” and open general practice.

### 7. Daily and weekly activity count different things

`stats.py:_get_streak_and_target_info` counts distinct questions answered that day, including reviews. `benchmark` counts all attempts over seven days. The hero's internal “new questions” logic uses the daily total, so reviews can complete that target. Weekly defaults also differ from the daily configuration fallback.

Specify the goal contract explicitly and share it across the Dashboard and Analysis. If the goal is all practiced questions, label it that way; if it is new questions, count lifetime first attempts. Repeated submissions must not inflate either new-question evidence or distinct practice volume.

## Proposed page order

1. Compact greeting, exam date, and resumable-session link.
2. **Next study action:** one bounded session, its reason, and its actual scope.
3. **Three priorities:** unresolved/repeated errors, a due follow-up, or a topic needing assessment. Each row includes evidence and a direct action.
4. **Learning check:** first-attempt accuracy, delayed-review outcomes, and corrections awaiting verification, with numerators, denominators, and period. Link to Analysis for interpretation and detail.
5. **Today's workload:** questions and flashcards separately, completed versus planned, and remaining backlog. Keep this compact.
6. Secondary links: Planner, coverage details, Analysis, and offline utilities.

Illustrative priority, not personal data: “Topic X: 4/10 first attempts correct; 3 questions still incorrect. Review those errors, then try different questions. Delayed check pending.” Avoid displaying invented sample results as live metrics.

## Metric contract and reuse

The working tree already contains `/stats/learning-analysis` and `api/services/learning_analysis.py`, with first responses, delayed reviews, unresolved and recurring errors, corrected items, pending checks, and scoped study URLs. Reuse and validate this shared service instead of building a competing Dashboard formula. These local changes have not been validated in this review.

- **First-attempt results:** identify first exposure across lifetime history before applying the reporting period. Show correct / distinct first-exposure questions. Changes in topic or question difficulty can explain a percentage change.
- **Delayed reviews:** show correct / assessed questions under an explicit interval convention. The current service uses at least 24 hours since the preceding attempt and one review outcome per question per window. This is a reporting convention, not proof of mastery or a universal scheduling rule. It currently describes question reviews, not flashcard outcomes.
- **Unresolved errors:** latest valid result incorrect; distinguish repeated errors from one-off errors. Keep the timestamps/order definition consistent across old and new endpoints, especially for offline submissions.
- **Follow-up:** the existing service can recognize later success on the same question; it does not establish causal improvement or verified transfer to new questions. Keep those limitations in labels and implementation requirements.
- **Evidence and availability:** report sample counts, scope, dates, and unavailable states. Never convert a request failure into zero errors or zero knowledge. Do not declare broad competence from a fixed small sample.
- **Confidence:** do not invent causes such as careless reading or lack of knowledge from correctness alone. Optional learner-selected reasons could be a later feature after checking capture timing and provenance.

## Implementation sequence

### P0 — Correct misleading claims and states

Remove the readiness badge from the main page; correct coverage semantics and generic recommendation labels; distinguish notebook API failures from zero errors; remove the automatic confetti trigger and misleading “clean” wording. Preserve useful session and offline actions.

Acceptance: failed bottlenecks never display success; unclassified errors remain visible; fallback practice matches its label; no badge claims exam competitiveness from all-attempt accuracy; a missing metric is not replaced with one of another meaning.

### P1 — Share learning evidence and redesign the Dashboard

Validate the existing learning-analysis contract, consume a compact summary, and implement the page order above. Share scope and calculations with Analysis. Consolidate duplicate cards. Use goal-consistent daily/weekly counts and bounded recommendations without combining question and flashcard workload into an unsupported estimate.

Acceptance: repeated attempts do not become new questions; an immediate correct retry is still pending delayed verification; zero observations display an unassessed state; topic actions preserve area/institution/status; Dashboard and Analysis agree for identical scope and time. Inspect mobile and desktop rendering and keyboard navigation during implementation.

### P2 — Complete the improvement loop

Connect correction sessions to later check status and offer different-question practice for the same topic. Ensure pending checks remain reachable even while other topics have errors. Add optional error reasons only if they lead to a useful action.

Acceptance: a learner can trace a flagged error through correction and later evidence; an incorrect follow-up reopens the issue; lack of new evidence is not called improvement. Show question availability honestly when a topic has no unseen items.

## Product success criteria

Evaluate whether the learner can identify the next priority without interpreting multiple scores, start the advertised session, and later see whether a correction held. Track completed delayed checks and recurring-error outcomes alongside first-attempt results; card clicks and question volume alone are insufficient. Compare like scopes and show sample counts. Do not attribute changes to the redesign without an appropriate evaluation.

The older `dashboard_audit.md` is a technical audit, not current evidence of pedagogical validity. Its descriptions of Bayesian readiness and recent-weighted bottlenecks do not match the Dashboard calculations inspected here. This review uses the implementation as its source of truth.
