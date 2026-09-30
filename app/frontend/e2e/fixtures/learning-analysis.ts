import type { Page } from '@playwright/test';
import type { LearningAnalysis, LearningTopic, LearningMeasure } from '../../src/types/api';

const measure = (correct: number, total: number): LearningMeasure => ({ correct, total, accuracy: total ? correct / total : null });
export function analysisFixture(params = new URLSearchParams()): LearningAnalysis {
  const institution = params.get('institution') || '';
  const area = params.get('area') || '';
  const subtema = params.get('subtema') || '';
  const scope = { institution, area, subtema, days: Number(params.get('days') || 30), tz_offset: Number(params.get('tz_offset') || 0), start: '2026-09-01', end: '2026-09-30', previous_start: '2026-08-02', previous_end: '2026-08-31' };
  const evidence = {
    available: 20, answered: 10, unseen: 10, new_questions: measure(4, 10), previous_new_questions: measure(2, 8),
    delayed_reviews: measure(2, 3), previous_delayed_reviews: measure(1, 2), unresolved: 3, recurring: 1,
    corrected: 2, retained_corrections: 1, pending_checks: 1, due: 2, tracked: 10, at_risk: 1,
  };
  const topicArea = area || 'Clínica Médica';
  const topic = subtema || 'Hipertensão Arterial Sistêmica';
  const link = (status: string) => `/estudar?${new URLSearchParams({ ...(institution ? { institution } : {}), area: topicArea, subtema: topic, status, limit: '10' })}`;
  const t: LearningTopic = { ...evidence, area: topicArea, topic, legacy_topic: false, last_answered_at: '2026-09-29T12:00:00Z', min_retrievability: .6, change_pp: 15, reason: 'unresolved', follow_up: 'needs_work', actions: { errors: link('wrong'), new: link('new'), reviews: link('srs_due') } };
  return { generated_at: '2026-09-30T12:00:00Z', scope, summary: evidence, topics: [t], priorities: [t],
    weeks: [{ start: '2026-09-01', new_questions: measure(4, 10), delayed_reviews: measure(2, 3) }],
    options: { institutions: [{ key: 'USP-SP', label: 'USP - São Paulo' }, { key: 'UNICAMP', label: 'Unicamp' }], areas: ['Clínica Médica', 'Pediatria'], subtemas: ['Hipertensão Arterial Sistêmica', 'Imunização (PNI)'] },
    goal: { questions: 20, reviews: 2, capacity: 20, pending: 0, hours: 1 }, method: { delayed_review_hours: 24, retention_target: .85, comparison_minimum: 5 } };
}

export async function mockAnalysis(page: Page) {
  await page.addInitScript(() => localStorage.setItem('medquest_onboarding_v1', 'done'));
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    let body: unknown = {};
    if (url.pathname.endsWith('/stats/learning-analysis')) body = analysisFixture(url.searchParams);
    if (url.pathname.endsWith('/stats/exam-readiness')) {
      const institution = url.searchParams.get('institution') || null;
      body = { institution, institution_label: institution || 'Todas as bancas', coverage: 0, answered: 0, available: 20, evidence_status: 'insufficient', readiness_score: .5,
        edital_profile: { status: 'experimental' }, areas: [{ area: 'Clínica Médica', available: 20, answered: 0, attempts: 0, accuracy: null, posterior_mean: .5, action: `/estudar?area=Cl%C3%ADnica+M%C3%A9dica&status=new&limit=10${institution ? `&institution=${institution}` : ''}` }] };
    }
    if (url.pathname.endsWith('/stats/institution-radar')) {
      const institution = url.searchParams.get('institution') || 'USP-SP';
      const compare = url.searchParams.get('compare_institution');
      const stats = { total_available: 100, total_answered: 12, total_attempts: 12, total_correct: 8, coverage: .12, accuracy: 8 / 12, ci_lower: .39, ci_upper: .86, sample_status: 'insufficient',
        areas: [{ area: 'Clínica Médica', available: 100, answered: 12, attempts: 12, correct: 8, coverage: .12, accuracy: 8 / 12, ci_lower: .39, ci_upper: .86, sample_status: 'insufficient', priority_topics: [] }] };
      body = { institution: { ...stats, code: institution, label: institution }, comparison: { ...stats, code: compare || null, label: compare || 'Desempenho Geral', type: compare ? 'institution' : 'global' } };
    }
    await route.fulfill({ json: body });
  });
}
