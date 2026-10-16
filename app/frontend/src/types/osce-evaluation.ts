// types/osce-evaluation.ts
// MedQuest OSCE Stage 4 - Contratos Canônicos de Avaliação, Espelho de Prova e Preceptor

export type BaremaCategory = 
  | 'A_AIRWAY' 
  | 'B_BREATHING' 
  | 'C_CIRCULATION' 
  | 'D_DISABILITY' 
  | 'E_EXPOSURE' 
  | 'ANAMNESIS' 
  | 'DIAGNOSIS' 
  | 'COMMUNICATION' 
  | 'PROCEDURE';

export type FulfillmentStatus = 'FULL' | 'PARTIAL' | 'NONE' | 'CRITICAL_ERROR';

export type HeadlineVerdict = 
  | 'APROVADO COM DISTINÇÃO' 
  | 'APROVADO NO LIMITE' 
  | 'REPROVADO POR TÉCNICA' 
  | 'ELIMINADO POR IATROGENIA';

export interface EvaluatedBaremaItem {
  criterion_id: string;
  code: string;
  category: BaremaCategory | string;
  description: string;
  max_score: number;
  awarded_score: number;
  status: FulfillmentStatus;
  timestamp_achieved_sec: number | null;
  evidence_citation: string;
  examiner_note?: string;
}

export interface RedFlagPenalty {
  code: string;
  title: string;
  description: string;
  timestamp_sec: number;
  score_deduction: number;
  caps_station_at?: number;
  clinical_consequence: string;
}

export interface CompetencyRadarScores {
  clinical_reasoning: number;      // 0-100: Diagnóstico, exames pertinentes, correlação clínica
  communication_empathy: number;   // 0-100: Linguagem com paciente e comando em alça fechada
  surgical_semiotics: number;      // 0-100: Ausculta completa, técnica cirúrgica, marcos anatômicos
  patient_safety: number;          // 0-100: Respeito ao ABCDE, ausência de iatrogenias
  sus_time_efficiency: number;     // 0-100: Ritmo, Time-to-Needle e uso racional de insumos
}

export interface ChiefPreceptorReview {
  executive_summary: string;
  what_went_well: string[];
  critical_corrections: string[];
  gold_standard_canonical_conduct: string;
}

export interface MedQuestRemediation {
  recommended_flashcard_decks: string[];
  recommended_qbank_filters: Array<{
    specialty: string;
    subtopic: string;
    difficulty: string;
  }>;
  suggested_retry_station_id?: string;
}

export interface PreceptorFeedback {
  headline_verdict: HeadlineVerdict;
  raw_score: number;
  penalty_deduction: number;
  final_score: number;
  cutoff_score: number;
  approved: boolean;
  station_title: string;
  institution: string;
  summary: string;
  competency_radar_5d: CompetencyRadarScores;
  evaluated_items: EvaluatedBaremaItem[];
  red_flags_triggered: RedFlagPenalty[];
  critical_warnings: string[];
  chief_preceptor_review: ChiefPreceptorReview;
  medquest_remediation: MedQuestRemediation;
  shock_cards_count?: number;
}
