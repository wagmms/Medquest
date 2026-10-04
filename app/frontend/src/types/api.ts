export interface OverviewStats {
  total_questions: number;
  distinct_answered: number;
  total_attempts: number;
  accuracy_all_attempts: number | null;
  accuracy_latest_attempt: number | null;
  coverage_pct: number | null;
  srs_due_count: number;
  accuracy_last7: number | null;
  accuracy_prev7: number | null;
  streak_days: number;
  streak?: {
    days: number;
    weekly_target: number;
    active_days_last_7: number;
    rest_days_available: number;
    policy: "rest_days_preserve_continuity";
  };
  flashcards_due_count?: number;
  today_answered?: number;
  daily_target?: number;
  days_until_exam?: number | null;
  exam_date?: string | null;
  target_score?: number | null;
  target_institution?: string | null;
  primary_institution?: string | null;
}

export interface CoverageSubtema {
  subtema: string;
  area?: string;
  n_questions: number;
  answered: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  coverage_pct: number;
  status: "mastered" | "proficient" | "in_progress" | "not_started";
  highYield?: boolean;
  theory_hours?: number;
}

export interface CoverageArea {
  area: string;
  n_questions: number;
  n_subtemas: number;
  answered_questions: number;
  attempts: number;
  correct: number;
  mastered: number;
  proficient: number;
  in_progress: number;
  not_started: number;
  high_yield_count?: number;
  high_yield_mastered?: number;
  accuracy: number | null;
  subtemas: CoverageSubtema[];
}

export interface CoverageResponse {
  areas: CoverageArea[];
}

export interface TimelineStat {
  day: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface WeakTopic {
  topic: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface BenchmarkStat {
  accuracy_overall: number | null;
  accuracy_last7: number | null;
  target_score: number;
  target_score_pct: number;
  diff_pct: number | null;
  status_label: "aprovado" | "competitivo" | "em_evolucao" | "iniciando";
  total_attempts?: number;
  total_correct?: number;
  is_reliable_sample?: boolean;
  last7_attempts: number;
  weekly_target_questions: number;
  weekly_progress_pct: number;
  competitors_average_pct: number;
}

export interface BottleneckTopic {
  subtema: string;
  area: string;
  unresolved_count?: number;
  attempts: number;
  correct: number;
  wrong_count: number;
  accuracy: number;
  accuracy_pct: number;
  practice_url: string;
}

export interface DomainAreaSummary {
  area: string;
  total_subtemas: number;
  mastered_subtemas: number;
  proficient_subtemas?: number;
  in_progress_subtemas: number;
  not_started_subtemas: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  domain_pct: number;
}

export interface DomainSummaryResponse {
  overall_domain_pct: number;
  total_mastered: number;
  total_subtemas: number;
  areas: DomainAreaSummary[];
}

export interface ErrorNotebookSummary {
  ever_wrong_count: number;
  currently_unresolved_count: number;
  practice_url: string;
}

export interface LearningProfileTopic {
  answered?: number;
  topic: string;
  area: string;
  available: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  diag_accuracy: number | null;
  prac_accuracy: number | null;
  coverage: number;
  confidence: number;
  retrievability: number | null;
  due_count: number;
  priority_score: number;
  reasons: string[];
}

export interface LearningProfile {
  generated_at: string;
  goal: {
    questions_today: number;
    configured_daily_questions: number;
    reviews_due: number;
    reviews_to_do_today: number;
    backlog_pending: number;
    hours_budget: number;
    max_capacity: number;
    target_score: number | null;
    exam_date: string | null;
  };
  topics: LearningProfileTopic[];
  method: { deterministic: boolean; signals: string[] };
}

export type EvidenceStatus = "insufficient" | "forming" | "reliable";

export interface EditalProfileData {
  institution_code: string;
  institution_label: string;
  version: string;
  validity_period: string;
  curation_source: string;
  status: "validated" | "experimental";
  weights: Record<string, number>;
}

export interface ReadinessKeyFactor {
  area: string;
  impact: string;
  recommendation: string;
  factor_type: "low_sample" | "low_accuracy" | "strength";
  action_url?: string;
}

export interface ExamReadinessArea {
  area: string;
  available: number;
  answered: number;
  coverage: number;
  attempts: number;
  correct?: number;
  accuracy: number | null;
  posterior_mean?: number;
  ci_lower?: number;
  ci_upper?: number;
  weight?: number;
  sample: "sufficient" | "limited";
  sample_status?: "insufficient" | "forming" | "reliable";
  action: string;
}

export interface ExamReadiness {
  institution: string | null;
  institution_label?: string;
  coverage: number;
  answered: number;
  available: number;
  readiness_score?: number;
  ci_lower?: number;
  ci_upper?: number;
  evidence_status?: EvidenceStatus;
  edital_profile?: EditalProfileData;
  areas: ExamReadinessArea[];
  key_factors?: ReadinessKeyFactor[];
  limitations?: string[];
  disclaimer: string;
}


export interface Recommendation {
  type: string;
  icon: string;
  title: string;
  description: string;
  cta: string;
  filters: Record<string, string>;
}

export interface BreakdownStat {
  key: string;
  label: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface DistractorStat {
  subtema: string;
  total_wrong: number;
  wrong_choices: {
    letter: string;
    count: number;
  }[];
}

export interface PredictiveScore {
  projected_score: number;
  target_score: number | null;
  is_reliable?: boolean;
  total_attempts?: number;
  minimum_attempts_per_area?: number;
  areas: {
    area: string;
    accuracy: number;
    attempts: number;
  }[];
}

export interface AtRiskTopic {
  subtema: string;
  items_count: number;
  stability: number | null;
  retrievability?: number;
}

export interface PlannerConfig {
  exam_date?: string;
  start_date?: string;
  days_per_week?: number;
  hours_per_day?: number;
  target_score?: number;
  target_institution?: string;
  target_institutions?: string[];
  primary_institution?: string;
  target_specialty?: string;
}

export interface PlannerTopic {
  area: string;
  subtema: string;
  subtopics?: string[];
  questions_available: number;
  estimated_theory_hours: number;
  estimated_practice_hours: number;
  estimated_hours: number;
  theory_source: "curriculum" | "pedagogical_estimate";
  course_module: string | null;
  priority?: number;
  priority_reasons?: string[];
  priority_tier?: string;
  priority_explanation?: string;
}

export interface PlannerWeek {
  week: number;
  date: string;
  topics: PlannerTopic[];
  recommended_hours: number;
  allocated_hours: number;
}

export interface PlannerPlanResponse {
  plan: PlannerWeek[];
  warning?: string;
  total_required_hours?: number;
  total_available_hours?: number;
}

export interface PlannerWeekProgress {
  studied: boolean;
  studied_at: string | null;
  rev24h: boolean;
  rev7d: boolean;
  rev30d: boolean;
}

export interface PlannerProgressMap {
  [weekId: string]: PlannerWeekProgress;
}

export interface PlannerTopicProgressMap {
  [topicId: string]: boolean;
}

export interface QuestionMeta {
  institutions: { institution_code: string; institution_label: string; n: number }[];
  years: number[];
  sources: { source_file: string; n: number }[];
  areas: { area: string; n: number }[];
  specialties: { specialty: string; n: number }[];
  subtemas: { subtema: string; n: number }[];
  topics?: { topic: string; n: number }[];
  total_questions: number;
  answered_questions: number;
}

export interface SubtemaItem {
  subtema: string;
  n: number;
}

export type AdaptiveFocus = "coverage" | "balanced" | "retention";

export interface QuestionListItem {
  id: number;
  source_file: string;
  source_number: number;
  year: number;
  institution_code: string;
  institution_label: string;
  topic: string;
  area: string;
  subtema: string;
  is_autoral?: boolean;
  is_discursive?: boolean;
  adaptive_score?: number;
  adaptive_reasons?: string[];
  retrievability?: number | null;
  is_twin?: boolean;
  twin_for_question_id?: number;
  twin_origin_institution?: string;
  twin_subtema?: string;
  remediation_reason?: "unresolved_error" | "twin_unseen_concept" | "remediation_practice";
}

export type BlindspotSeverity = "CRITICAL" | "HIGH" | "MODERATE";

export interface BlindspotItem {
  subtema: string;
  area: string;
  severity: BlindspotSeverity;
  severity_score: number;
  unresolved_count: number;
  wrong_count: number;
  attempts: number;
  correct: number;
  accuracy_pct: number;
  frequent_distractor?: {
    letter: string;
    count: number;
  } | null;
  fsrs_status?: {
    min_retrievability: number | null;
    cards_due: number;
  };
  clinical_insight: string;
  workout_url: string;
}

export interface BlindspotsSummary {
  total_blindspots: number;
  unresolved_errors_count: number;
  healed_count: number;
  healing_rate_pct: number;
  total_unique_answered: number;
}

export interface BlindspotsResponse {
  summary: BlindspotsSummary;
  blindspots: BlindspotItem[];
}

export interface QuestionAlternative {
  letter: string;
  text: string;
}

export interface ClinicalCase {
  stem: string;
  images: string[];
}

export interface QuestionDetail extends QuestionListItem {
  stem: string;
  alternatives: QuestionAlternative[];
  images: string[];
  already_answered?: {
    selected_letter: string;
    is_correct: number;
  };
  is_verified?: boolean;
  last_updated_at?: string;
  technical_note?: string;
  clinical_case?: ClinicalCase;
  usp_macro?: string;
  usp_micro?: string;
  is_favorite?: boolean;
  times_wrong?: number;
}

export interface AttemptResult {
  is_correct: boolean | null;
  correct_letter: string;
  explanation: string | null;
  next_review_date: string | null;
  is_discursive?: boolean;
}

export interface BatchAttemptItem {
  question_id: number;
  selected_letter: string;
  time_spent_ms?: number;
  confidence?: string;
  is_correct?: boolean;
  user_answer_text?: string;
  twin_for_question_id?: number;
}

export interface BatchAttemptResultItem {
  question_id: number;
  is_correct: boolean;
  correct_letter: string;
  explanation: string | null;
  next_review_date: string;
  is_discursive?: boolean;
}

export interface BatchAttemptResult {
  results: BatchAttemptResultItem[];
}

export interface BatchDetailResponse {
  questions: QuestionDetail[];
}

export interface SearchFilterOptions {
  semantic?: boolean;
  institution?: string;
  area?: string;
  year?: number | string;
  has_images?: boolean;
  limit?: number;
  offset?: number;
}

export interface SearchResult {
  id: number;
  institution_code: string;
  year: number;
  area: string;
  subtema: string;
  stem_snippet: string;
  exp_snippet: string;
  is_autoral?: boolean;
  has_image?: boolean;
}

export interface Flashcard {
  id: number;
  question_id?: number | null;
  front: string;
  back: string;
  next_review_date: string;
  stem?: string;
  source_context?: string;
  is_ai_generated?: boolean;
  area?: string;
  subtema?: string;
  deck_name?: string;
  tags?: string[];
  source_type?: string;
  anki_nid?: number | null;
  anki_cid?: number | null;
}

export interface FlashcardDeck {
  name: string;
  source_type: string;
  total_cards: number;
  due_cards: number;
}

export interface FlashcardDecksResponse {
  total_cards: number;
  due_cards: number;
  decks: FlashcardDeck[];
}

export interface AnkiImportResult {
  success: boolean;
  total_imported: number;
  new_cards: number;
  decks: string[];
}

export interface FlashcardGenerateResponse {
  id: number;
  question_id: number;
  front: string;
  back: string;
  context?: string;
}

export interface BatchFlashcardGenerateResponse {
  success: boolean;
  count: number;
  flashcards: FlashcardGenerateResponse[];
}

export interface NotificationConfig {
  enabled: boolean;
  preferred_hour: number;
  days_of_week: number[];
  max_daily_reminders: number;
  updated_at: string | null;
  has_active_subscription: boolean;
  vapid_public_key: string | null;
}

export interface NotificationConfigUpdate {
  enabled: boolean;
  preferred_hour: number;
  days_of_week: number[];
  max_daily_reminders?: number;
}

export interface PushSubscriptionPayload {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  expiration_time?: number | null;
}

export type SampleStatus = "insufficient" | "forming" | "reliable";

export interface RadarTopicGap {
  subtema: string;
  available: number;
  answered: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  gap_type: "unanswered" | "low_accuracy" | "low_coverage";
  study_url: string;
  simulado_url: string;
  review_url: string;
}

export interface RadarAreaStat {
  area: string;
  available: number;
  answered: number;
  coverage: number;
  attempts: number;
  correct: number;
  accuracy: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  sample_status: SampleStatus;
  priority_topics: RadarTopicGap[];
}

export interface RadarInstitutionData {
  code: string | null;
  label: string;
  total_available: number;
  total_answered: number;
  coverage: number;
  total_attempts: number;
  total_correct: number;
  accuracy: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  sample_status: SampleStatus;
  areas: RadarAreaStat[];
}

export interface InstitutionRadarResponse {
  institution: RadarInstitutionData;
  comparison: {
    type: "global" | "institution";
  } & RadarInstitutionData;
  disclaimer: string;
  sample_thresholds: {
    insufficient: string;
    forming: string;
    reliable: string;
  };
}

export interface ThemeProgress {
  subtema: string;
  theory_completed: boolean;
  study_path: "essential" | "complete";
  updated_at: string | null;
  flashcards_total: number;
  flashcards_due: number;
}

export interface DashboardSummaryResponse {
  stats: OverviewStats;
  benchmark: BenchmarkStat | null;
  bottlenecks: BottleneckTopic[];
  domain_summary: DomainSummaryResponse | null;
  error_notebook: ErrorNotebookSummary | null;
  planner: {
    config: PlannerConfig | null;
    progress: PlannerProgressMap;
    topic_progress: PlannerTopicProgressMap;
  };
}

export interface AuthMeResponse {
  user_id: string;
  email: string | null;
  is_curator: boolean;
}

export interface PreceptorFocusTopic {
  topic: string;
  area: string;
  attempts: number;
  correct?: number;
  accuracy_pct: number;
  wrong: number;
  unresolved_count?: number;
}

export interface PreceptorFocusResponse {
  diagnostic_data: {
    status: string;
    has_data: boolean;
    overall_accuracy_pct: number;
    total_attempts: number;
    srs_due_count: number;
    weak_topics: PreceptorFocusTopic[];
    message?: string;
  };
  analysis_markdown?: string;
  recommended_topic: {
    subtema: string;
    area: string;
    practice_url: string;
  };
  source?: string;
  model?: string;
  generated_at?: string;
}

export interface SpecialtyCutoff {
  specialty: string;
  cutoff_score: number;
  projected_score: number;
  difference: number;
  status: "HIGH_PROBABILITY" | "COMPETITIVE" | "NEEDS_IMPROVEMENT";
  status_label: string;
}

export interface TriEvaluationResponse {
  theta: number;
  standard_error: number;
  pedagogical_coherence_pct: number;
  coherence_label: string;
  institution_code: string;
  institution_label: string;
  projected_score: number;
  raw_score_pct: number;
  national_percentile: number;
  specialty_cutoffs: SpecialtyCutoff[];
}

export interface TriEvaluationPayload {
  responses: Array<{
    question_id?: number;
    id?: number;
    is_correct: boolean;
  }>;
  institution_code?: string;
}

export interface OsceStation {
  id: number;
  code: string;
  title: string;
  area: string;
  subtema: string;
  institution: string;
  year: number;
  difficulty: string;
  duration_seconds: number;
  scenario_door_markdown: string;
  best_score: number | null;
  completed_attempts: number;
}

export interface OsceStationDetail {
  id: number;
  code: string;
  title: string;
  area: string;
  subtema: string;
  institution: string;
  year: number;
  difficulty: string;
  duration_seconds: number;
  scenario_door_markdown: string;
  patient_persona: {
    name?: string;
    age?: number;
    gender?: string;
    chief_complaint?: string;
  };
  physical_exam_categories: string[];
  vitals_available: boolean;
  lab_imaging_catalog: Array<{
    key: string;
    title: string;
  }>;
}

export interface OsceTranscriptItem {
  sender: "candidato" | "paciente" | "examinador";
  message: string;
  timestamp: string;
  elapsed_seconds?: number;
  action_payload?: Record<string, unknown>;
}

export interface OsceChecklistItem {
  id: string;
  title: string;
  category: string;
  weight: number;
  score_earned: number;
  status: "cumprido_total" | "cumprido_parcial" | "nao_cumprido";
  evidence: string;
}

export interface OscePreceptorFeedback {
  final_score: number;
  max_score: number;
  approved: boolean;
  station_title: string;
  institution: string;
  summary: string;
  critical_warnings: string[];
  shock_cards_count: number;
}

export interface OsceShockCard {
  station_code: string;
  front: string;
  back: string;
  category: string;
  weight: number;
}

export interface OsceFinishResponse {
  session_id: string;
  final_score: number;
  status: string;
  evaluated_items: OsceChecklistItem[];
  preceptor_feedback: OscePreceptorFeedback;
  shock_cards: OsceShockCard[];
  elapsed_seconds: number;
  timeline_post_mortem?: OsceTimelinePostMortem;
  competency_radar?: OsceCompetencyRadar;
}

export interface OsceReportResponse {
  session_id: string;
  station_id: number;
  code: string;
  title: string;
  area: string;
  subtema: string;
  institution: string;
  year: number;
  status: string;
  start_time: string;
  end_time?: string;
  elapsed_seconds: number;
  duration_seconds: number;
  final_score: number;
  scenario_door_markdown: string;
  checklist_evaluation: OsceChecklistItem[];
  critical_warnings: string[];
  preceptor_feedback: OscePreceptorFeedback;
  transcript: OsceTranscriptItem[];
  timeline_post_mortem?: OsceTimelinePostMortem;
  competency_radar?: OsceCompetencyRadar;
}

export interface OsceSpokenQueueItem {
  speaker: "examinador" | "paciente";
  text: string;
}

export interface OsceDispatchSpeechResponse {
  transcription: string;
  actions_executed: Array<{
    action_type: string;
    target: string;
    examiner_message: string;
    payload: Record<string, unknown>;
    elapsed_seconds: number;
  }>;
  is_patient_dialogue: boolean;
  patient_reply: string;
  spoken_queue: OsceSpokenQueueItem[];
  transcript: OsceTranscriptItem[];
  elapsed_seconds: number;
  guided_feedback?: OsceLiveFeedback;
}

export interface OsceDrugItem {
  id: string;
  name: string;
  category: string;
  default_dose: string;
  default_unit: string;
  routes: string[];
  indications: string;
  hints?: string;
}

export interface OscePrescriptionItem {
  drug_name: string;
  dose: string;
  unit: string;
  route: string;
  notes?: string;
}

export interface OscePrescribeResponse {
  success: boolean;
  prescription_text: string;
  examiner_message: string;
  matched_criteria: string[];
  spoken_queue: OsceSpokenQueueItem[];
  elapsed_seconds: number;
  guided_feedback?: OsceLiveFeedback;
}

export interface OsceProcedureCatalogItem {
  id: string;
  type: string;
  name: string;
  site: string;
  body_region: string;
  description: string;
}

export interface OsceProcedureResponse {
  success: boolean;
  procedure_type: string;
  anatomical_site: string;
  findings: string;
  examiner_message: string;
  spoken_queue: OsceSpokenQueueItem[];
  elapsed_seconds: number;
  guided_feedback?: OsceLiveFeedback;
}

export interface OsceLiveChecklistItem {
  id: string;
  title: string;
  category: string;
  weight: number;
  score_earned: number;
  completed: boolean;
  status: "cumprido_total" | "cumprido_parcial" | "nao_cumprido";
  matched_keywords: string[];
}

export interface OsceLiveFeedback {
  mode: "blind" | "guided";
  current_score: number;
  max_score: number;
  raw_earned: number;
  raw_weight: number;
  percentage: number;
  items_status: OsceLiveChecklistItem[];
  proactive_hints: string[];
}

export interface OsceTimelineEvent {
  time_seconds: number;
  time_formatted: string;
  event_type: "start" | "vitals" | "physical_exam" | "lab_imaging" | "procedure" | "prescription" | "anamnese" | "conduct" | "hesitacao" | "omissao";
  title: string;
  description: string;
  status: "timely" | "neutral" | "delayed" | "critical_gap";
  feedback: string;
  score_impact: string;
}

export interface OsceTimelineSummary {
  total_events: number;
  timely_count: number;
  delayed_count: number;
  critical_gaps_count: number;
  door_to_first_action_seconds: number;
  door_to_ecg_seconds: number | null;
  pace_label: string;
}

export interface OsceTimelinePostMortem {
  events: OsceTimelineEvent[];
  summary: OsceTimelineSummary;
}

export interface OsceCompetencyDimension {
  key: string;
  name: string;
  score_earned: number;
  score_max: number;
  percentage: number;
  level: "Excelente" | "Satisfatório" | "Necessita Atenção";
  description: string;
  feedback: string;
}

export interface OsceCompetencyRadar {
  overall_average: number;
  strengths: string[];
  weaknesses: string[];
  dimensions: OsceCompetencyDimension[];
}

export interface OsceGenerateStationPayload {
  area?: string;
  subtema?: string;
  difficulty?: "easy" | "medium" | "hard";
  adaptative?: boolean;
}

export interface OsceGenerateStationResponse {
  success: boolean;
  station_id: number;
  code: string;
  title: string;
  area: string;
  subtema: string;
  institution: string;
  difficulty: string;
  message: string;
}

export interface OsceCircuitStationItem {
  step: number;
  station_id: number;
  code: string;
  area: string;
  subtema?: string;
  title: string;
  institution: string;
  duration_seconds?: number;
}

export interface OsceCircuitPlanResponse {
  circuit_id: string;
  institution: string;
  total_steps: number;
  stations: OsceCircuitStationItem[];
}

export interface OsceCircuitStationSummaryItem {
  step: number;
  session_id: string;
  station_id: number;
  code: string;
  area: string;
  title: string;
  institution: string;
  final_score: number;
  approved: boolean;
  status: string;
  critical_warnings?: string[];
}

export interface OsceCircuitSummaryResponse {
  circuit_id: string;
  user_id: string;
  total_score: number;
  max_score: number;
  average_score: number;
  percentage: number;
  approved: boolean;
  stations_completed: number;
  total_stations: number;
  critical_errors_count: number;
  stations: OsceCircuitStationSummaryItem[];
  board_feedback: string;
}




