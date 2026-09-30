# Analysis tab: learning value review and implementation plan

Review date: 2026-09-29. Scope: current repository implementation, including rendering, API calculations, recommendation URLs, adaptive goals, and confidence capture. This is a product and measurement review, not a personal diagnosis of the user's knowledge. No authenticated account data or browser rendering was inspected. No application behavior was changed, and prior audit test results were not rerun or treated as current validation.

## Decision

Make the tab answer three questions, in this order:

1. What should I work on next, and what evidence supports that recommendation?
2. What kind of gap is it: an unresolved mistake, uncertain knowledge, overdue review, or an unassessed topic?
3. After studying, did I retain the correction and succeed on different questions?

The current tab contains useful building blocks but emphasizes overlapping summaries of attempts. It does not yet close the loop from identifying a gap to verifying improvement. A technically correct percentage is not automatically a useful measure of learning.

## Keep, change, move, or remove

| Current element | Decision | Learning value and required change |
| --- | --- | --- |
| Adaptive daily goal | Keep as a compact action block | Show a short priority queue, reasons, scope, and realistic workload. Separate workload planning from evidence of mastery. |
| Weak topics | Promote to the main content | Combine recent first-attempt performance, unresolved errors, sample size, and review need. Distinguish unassessed topics from demonstrated weaknesses. |
| Forgetting radar | Keep after correcting semantics | Show questions below the retention threshold and those due for review. Label retention as a model estimate for tracked items. |
| Readiness by exam profile | Simplify and move below priorities | Retain area breakdown and uncertainty. Use a descriptive performance label while profiles remain experimental; do not imply verified exam readiness. |
| Comparative institution radar | Keep as optional detail | Useful when choosing practice for a target institution. Merge overlapping area information and preserve selected institution in actions. |
| Separate predictive score | Remove from the main experience | Duplicates readiness while using a different evidence threshold and fixed USP weights. There is no demonstrated reason for two headline scores. |
| Institution accuracy bar chart | Merge into the optional institution view | Another representation of all-time accuracy adds little actionable information. |
| Daily accuracy and volume | Keep, redesign | Separate first attempts from reviews; offer weekly summaries with denominators, topic scope, and uncertainty. Explain changes in question mix. |
| Six-month activity heatmap | Move to a collapsed activity section or home dashboard | Measures participation. Useful for routines, insufficient for judging learning. |
| Most frequently selected wrong letter | Remove | An option letter has no consistent conceptual meaning across different questions. Replace only with question-specific distractor explanations or verified error categories. |
| Statistical terminology and profile version | Move into methodology details | Keep sample size and a plain uncertainty statement visible. Beta-Binomial terminology should not dominate the study decision. |

## Confirmed findings from the source

### 1. Repeated attempts can inflate apparent evidence

`app/backend/api/stats.py`: `weak_topics`, `timeline`, `_breakdown`, `_get_user_area_attempts`, and `predictive_score` aggregate attempts rather than separating first exposure from repeated practice. Readiness counts unique questions for coverage, but uses attempt counts for its posterior and evidence status.

A repeated response to the same item is not equivalent to a new independent observation of general competence. The current calculation can move toward a narrower interval and a stronger evidence label through repetition. This does not mean repetition is useless for learning; it means learning activities and independent assessment need different reporting.

Recommendation: first-attempt accuracy on distinct questions for new-question performance; delayed review success for retention; latest incorrect responses for unresolved errors. Keep historical all-attempt accuracy only as explicitly labeled detail. First attempts still reflect selection and difficulty biases and must not be presented as a validated exam prediction.

### 2. Weakness ranking is historical and relative

`stats.py:weak_topics` sorts all-time accuracy after a five-attempt minimum, without a low-accuracy condition. Consequently even uniformly strong topics can appear as “weak.” The client shows the first eight and launches `status=all&limit=50`.

Recommendation: call these “topics to investigate” until evidence supports a weakness classification; show recent evidence and unresolved errors. Offer different actions for error review and unseen-question assessment instead of an undifferentiated 50-question session. Preserve area identifiers as well as topic names.

### 3. Wrong-letter aggregation is not a conceptual diagnosis

`stats.py:distractors` groups errors by subtopic and selected letter. `AnalysisClient.tsx` renders “Você costuma errar marcando a …”. It does not inspect the meaning of the selected alternative.

Recommendation: remove this insight. A useful replacement would describe a verified confusion with links to the exact questions. Initially use optional learner-selected causes: knowledge gap, interpretation, reasoning, or time pressure. Do not infer a cause solely from a wrong answer or long response time.

### 4. Forgetting count and retention label overstate the underlying calculation

`stats.py:at_risk` counts every usable FSRS record in each subtopic, then includes that subtopic if its minimum retrievability is below 0.85. The UI calls that full count “cartões em risco” and displays the minimum as a generic retention percentage.

Example: a topic with one item at 60% and nine at 95% can display ten at-risk cards with 60% retention. That is not the count of items below threshold or the topic's average retention.

Recommendation: count threshold-crossing items explicitly; show due-item count separately; ensure the study action selects the same population advertised by the card. Empty data, no tracked cards, loading failure, and no items currently at risk must have separate messages. The current empty state says memory is up to date even when the API fallback is an empty list.

### 5. The two headline estimates have different meanings

`stats.py:_determine_evidence_status` permits global “reliable” evidence with at least 50 attempts and 10 per weighted area. Area badges use 20 attempts, while the separate predictive score requires 20 per area and uses `USP_WEIGHTS` independently of the selected readiness institution.

`app/backend/api/edital_profiles.py` explicitly describes the catalog as provisional. The named profiles use equal 20% area weights and experimental status; they are not validated extractions of official exam distributions.

Recommendation: consolidate the summaries. Label observed performance and uncertainty plainly; retain the experimental-profile status. Define evidence sufficiency using distinct items, breadth, recency, and uncertainty, not an arbitrary count labeled as calibration. Do not claim predictive validity without evaluating against held-out exam-like assessments.

### 6. Recommendations do not consistently preserve context

Readiness area and factor URLs in `stats.py` contain area/status/limit but omit the selected institution. The comparative radar does include institution in its study URLs. The radar also owns independent institution state; changing the parent readiness selector does not synchronize that state after initialization.

The radar ranks unattempted topics before attempted low-accuracy topics, then displays only four gaps. Unassessed topics can therefore crowd out known errors. Its fallback gap type is `low_coverage` even without a coverage threshold check.

Recommendation: one shared scope, with explicit optional comparison; context-preserving URLs; separate assessment gaps and remediation priorities. Reserve room for each instead of letting one category consume the queue.

### 7. Important learning actions come late on narrow screens

`AnalysisClient.tsx` places weak topics in the second grid column after the full first-column content in DOM order. On a single-column layout, readiness, radar, prediction, institution chart, evolution, and activity history precede weak topics.

Recommendation: priorities first in DOM order on all screen sizes. Confirm layout and interaction in an actual browser during implementation; this finding is inferred from the responsive source structure.

### 8. Existing confidence data needs qualification before use

`attempts` stores confidence and response time. However, `QuizClient.tsx` collects much of its self-assessment after the result is available, and `questions.py:_process_single_attempt` defaults omitted confidence to `certeza` in the batch path.

Recommendation: use explicit post-answer ratings for “correct but unsure/guessed,” with provenance. Do not use existing values as a trustworthy pre-answer confidence measure or claim to identify confident misconceptions from them. Introduce optional pre-answer confidence with capture timing/source and missing-value semantics before producing confidence-versus-correctness analytics. Preserve historical ambiguity rather than inventing certainty in a migration.

### 9. Adaptive workload wording exceeds what this endpoint does

`adaptive.py:build_learning_profile` computes backlog counts but does not reschedule those items. The UI says pending items “were redistributed.” It assumes 20 questions per hour, and `questions_today = max(daily_goal, reviews_to_do_today)` can exceed the computed capacity when the configured daily goal is higher.

Recommendation: say the backlog remains pending unless actual scheduling is verified. Reconcile goal and capacity consistently, and describe time as an estimate rather than a guarantee. This matters because the primary study action should be feasible.

## Proposed information order

1. Shared filters: period, institution, area/topic, and new questions versus reviews. State scope next to every exception.
2. “Your next priorities”: three to five evidence-backed topics, each with reason, sample, relevant date, action, and follow-up state.
3. “Is your learning improving?”: new-question accuracy, delayed review success, and unresolved/recurring errors, each with denominators and comparable periods.
4. Expandable topic table: area, subtopic, new-question results, unresolved mistakes, uncertain correct answers, due reviews, evidence status, and recent change.
5. Optional institution comparison and activity history; methodology remains accessible.

Illustrative priority card, not user data: “Topic X — 4 of 10 unseen questions correct in this period; 3 questions still incorrect on their latest attempt. Review these errors, then assess with different questions. Delayed follow-up pending.” The card should not claim improvement immediately after showing an answer.

## Implementation sequence and acceptance criteria

### P0 — Make current claims trustworthy

- Remove wrong-letter insights and the separate headline predictive score; merge redundant institution summaries.
- Correct at-risk item counting, retention labels, and empty/error states.
- Fix context propagation and distinguish unassessed topics from confirmed difficulties.
- Correct workload and redistribution wording; replace “calibrated/reliable” claims that depend only on attempt counts with sample descriptions.
- Display no observed performance percentage for an area with zero answers: its current 50% posterior comes solely from the prior.

Acceptance: a one-at-risk/nine-safe fixture displays one at-risk item; failures do not claim healthy memory; institution-specific actions retain institution; zero observations display “not assessed”; repeating one question cannot qualify a topic as broadly assessed. The final requirement depends on P1's metric contract and should ship with that change, not as a cosmetic label fix alone.

### P1 — Define learning measures and implement the priority view

- Build a shared analytics contract with global first-attempt identification before period filtering, unique-question counts, explicit timezone, and period boundaries.
- Separate first-attempt performance, latest unresolved errors, delayed review outcomes, and explicitly recorded uncertainty.
- Reuse `/stats/bottlenecks` and the error-notebook summary for unresolved questions, extending their scope/recency fields as needed. A latest correct response is an error-notebook status, not proof of lasting mastery.
- Reuse adaptive signals, but show reasons and keep exploration separate from error remediation. Treat any ranking weights as product heuristics pending evaluation.
- Put the priority queue first on desktop and mobile; make error review, unseen practice, and due review distinct actions.

Acceptance: first wrong answer followed by immediate correct repeats leaves first-attempt accuracy unchanged; a prior-period first exposure is not counted as new this period; missing confidence stays unknown; historical recovery is visible without erasing original mistakes; all summaries are isolated by user and agree on filter scope.

### P2 — Verify correction and retention

- Record the baseline, recommended action, practice completion, and subsequent assessment evidence per topic.
- Distinguish immediate correction from delayed retention and performance on different questions.
- Use existing review scheduling where applicable; document minimum elapsed-time rules for reporting delayed reviews. Do not hard-code a universally optimal interval.
- Start with observable states: “needs assessment,” “needs work,” “correction practiced,” “delayed check pending,” and “improvement observed.” Avoid a permanent “mastered” label.
- Add optional error-cause tagging and pre-answer confidence only with clear capture provenance. Keep response time secondary and exclude invalid/missing timings.

Acceptance: immediate retries cannot count as delayed retention; an overdue assessment stays pending; no eligible new questions produces an honest unavailable state; confidence submitted after seeing the answer cannot be reported as pre-answer calibration; improvement displays the actual new evidence and sample size.

### P3 — Validate usefulness before adding more panels

- Browser review at narrow and wide widths, with keyboard navigation and empty/partial/error states.
- Focused API and end-to-end tests for the acceptance cases above and study-link scope.
- Evaluate whether the user can identify the next useful action quickly, whether recommended sessions are completed, and whether subsequent new-question and delayed-review outcomes improve.
- Treat clicks and question volume as usage measures. They do not establish learning gains or that the dashboard caused improvement.
- Defer PDF export, extra prediction models, additional charts, and automated conceptual error classification until the primary learning loop works.

## Evidence informing the plan

Retrieval practice and spaced study support delayed retention. That supports a product emphasis on answering, receiving feedback, and checking retention later; it does not validate MedQuest's FSRS calibration, its current readiness score, or any universal number of questions required for mastery. See [Roediger and Karpicke's retrieval experiments](https://pubmed.ncbi.nlm.nih.gov/16507066/) and [Cepeda and colleagues' spacing experiments](https://pubmed.ncbi.nlm.nih.gov/19439395/).

Correct answers given with low confidence can also benefit from feedback. This supports surfacing explicitly reported uncertainty instead of treating all correct answers alike; see [Butler, Karpicke, and Roediger](https://pubmed.ncbi.nlm.nih.gov/18605878/). The proposed UI hierarchy and priority rules remain design recommendations, not experimentally validated outcomes for this application.

## Implementation update — 2026-09-30

The core learning workflow is now implemented in `/analise`:

- A shared, user-isolated `/api/stats/learning-analysis` report supplies period, institution, area, and topic filters. First exposure is determined from the full history before the period is applied.
- A priority queue precedes every results panel on desktop and mobile. It reserves up to three places for remediation and two for assessment, with separate error, new-question, and due-review actions.
- New-question accuracy and delayed-review outcomes are separate. A question contributes at most once to each measure in a period. The last eligible review must follow at least 24 hours without an attempt on that question. This is a reporting convention and does not modify FSRS scheduling.
- Error follow-up is reconstructed from existing answer records. An immediate correction stays pending until there is subsequent evidence after an interval. A later error invalidates previous recovery evidence. Topic counts remain visible instead of implying that the whole topic is mastered.
- Latest recorded error state follows attempt ID, matching the existing error notebook and study queue. First exposure and review intervals use occurrence timestamps, including offline uploads. Historic confidence values remain excluded because their provenance is ambiguous.
- Forgetting counts now include only tracked questions below the shared FSRS retention target. Due reviews are counted and linked separately; lack of memory data does not generate a reassuring success message.
- Institution detail is optional and explicitly uses lifetime first responses. No percentage derived solely from the prior is displayed for unassessed areas. Experimental profile weights remain labeled as such; repeated answers cannot increase its assessment sample.
- Redundant headline predictions, wrong-letter insights, the separate institution bar chart, and the activity heatmap were removed from this tab. Weekly evidence and optional institution comparisons remain available below the main learning workflow.
- Workload estimates respect time capacity; the new report also caps the estimate at the available question count. Pending reviews are no longer described as automatically rescheduled.
- Scope changes cancel obsolete requests and hide old results until new data arrive. Failure states provide a retry instead of substituting empty or healthy-looking results.

This implementation deliberately reuses answer history instead of adding a second editable progress database. Optional pre-answer confidence and error-cause tagging remain future study-flow features, because existing records cannot safely supply those meanings. Long-term learning improvement must be evaluated through subsequent use; the implementation does not claim that interface changes alone cause improvement.

Validation:

- 75 backend tests passed across learning analysis, Bayesian calculations, institution comparison, adaptive practice, statistics, and API integration.
- Production build and TypeScript checks passed, including service-worker validation and JavaScript performance budgets. The existing oversized icon-font precache warning remains unrelated to analytics.
- Focused ESLint checks passed for the changed UI, API types, and browser tests.
- A synthetic, in-memory SQLite report with 5,000 questions and 50,000 attempts completed in approximately 0.3 seconds locally. This is a local benchmark, not a remote Turso latency guarantee.
- Six focused Playwright tests passed: scoped study links and mobile overflow, error/retry recovery, empty data, late-response cancellation, zero-evidence institution detail, and optional institution comparison. Tests use synthetic account data, not the live account.
- Final desktop (1280px) and mobile (390px) screenshots were visually inspected, including the evidence and correction-follow-up sections. Mobile filters use two columns, a single priority uses the full row, and the browser check confirms no page-level horizontal overflow. All six browser tests passed again after these layout refinements.
