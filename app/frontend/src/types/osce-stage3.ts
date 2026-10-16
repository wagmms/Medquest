// src/types/osce-stage3.ts

export type SUSFacilityLevel = 'UBS_PRIMARIA' | 'UPA_SECUNDARIA' | 'SALA_VERMELHA_TERCIARIA';

export type TaskStatus = 'QUEUED' | 'PREPARING' | 'READY_FOR_DOCTOR' | 'COMPLETED' | 'BLOCKED_NO_SUPPLY' | 'COMPLICATION';

export type AnatomicalView = 'ANTERIOR' | 'POSTERIOR' | 'HEAD_NECK_AIRWAY';

export interface NursingTask {
  id: string;
  title: string;
  category: 'MEDICATION' | 'ACCESS' | 'MONITORING' | 'AIRWAY_PREP' | 'LAB_IMAGING';
  orderedAtSimTimeMs: number;
  durationMs: number;
  elapsedMs: number;
  status: TaskStatus;
  nurseFeedback: string;
  requiredSupplies: string[];
  onCompleteEffectId: string;
  complicationChance?: number; // Ex: 0.25 para falha de acesso periférico no choque hipovolêmico
  fallbackSuggestion?: string;
}

export interface AnatomicalHitbox {
  id: string;
  name: string;
  view: AnatomicalView;
  svgPath: string; // Coordenadas do polígono SVG
  labelCoords: { x: number; y: number };
  allowedProcedures: string[];
  anatomicalLandmarkText: string;
  isIatrogenicZone?: boolean;
  iatrogenicOutcome?: {
    complicationName: string;
    bancaPenaltyPoints: number;
    vitalSignImpact: { hrDelta: number; sbpDelta: number; spo2Delta: number };
    feedbackMessage: string;
  };
}

export interface SUSSupplyMatrix {
  facility: SUSFacilityLevel;
  label: string;
  maxNurses: number; // Limita quantas tarefas simultâneas a enfermagem consegue executar
  availableSupplies: Record<string, boolean>;
  unavailableRejectionMessages: Record<string, string>;
}

export const SUS_FACILITY_MATRICES: Record<SUSFacilityLevel, SUSSupplyMatrix> = {
  UBS_PRIMARIA: {
    facility: 'UBS_PRIMARIA',
    label: 'UBS - Atenção Primária (Recurso Básico)',
    maxNurses: 1, // Apenas 1 técnico de enfermagem disponível
    availableSupplies: {
      O2_CATHETER: true,
      BAG_VALVE_MASK: true,
      PERIPHERAL_IV_CRYSTALLOID: true,
      EPINEPHRINE_IM_IV: true,
      JELCO_14G_THORACOCENTESIS: true,
      DEFINITIVE_AIRWAY_TOT: true, // Kit básico de intubação
      NOREPINEPHRINE_PUMP: false,
      CHEST_TUBE_WATER_SEAL: false,
      EFAST_ULTRASOUND: false,
      CENTRAL_VENOUS_CATHETER: false,
      BLOOD_TRANSFUSION_O_NEG: false,
      VIDEO_LARYNGOSCOPE: false,
    },
    unavailableRejectionMessages: {
      NOREPINEPHRINE_PUMP: 'Doutor, estamos numa UBS! Não temos bomba de infusão nem Noradrenalina aqui. Precisamos estabilizar no soro e acionar o SAMU (Vaga Zero)!',
      CHEST_TUBE_WATER_SEAL: 'Doutor, não temos dreno tubular nem selo d’água na UBS. Se for pneumotórax hipertensivo, utilize o Jelco 14 para punção de alívio!',
      EFAST_ULTRASOUND: 'Não temos aparelho de Ultrassom na UBS, doutor. O diagnóstico do choque deve ser clínico!',
      BLOOD_TRANSFUSION_O_NEG: 'Sem agência transfusional na UBS! Apenas cristaloide disponível.',
    },
  },
  UPA_SECUNDARIA: {
    facility: 'UPA_SECUNDARIA',
    label: 'UPA 24h - Porte II (Sala de Emergência)',
    maxNurses: 2,
    availableSupplies: {
      O2_CATHETER: true,
      BAG_VALVE_MASK: true,
      PERIPHERAL_IV_CRYSTALLOID: true,
      EPINEPHRINE_IM_IV: true,
      JELCO_14G_THORACOCENTESIS: true,
      DEFINITIVE_AIRWAY_TOT: true,
      NOREPINEPHRINE_PUMP: true,
      CHEST_TUBE_WATER_SEAL: true,
      CENTRAL_VENOUS_CATHETER: true,
      EFAST_ULTRASOUND: false, // UPA comum sem USG point-of-care beira-leito
      BLOOD_TRANSFUSION_O_NEG: false,
      VIDEO_LARYNGOSCOPE: false,
    },
    unavailableRejectionMessages: {
      EFAST_ULTRASOUND: 'Doutor, o ultrassom da UPA está em manutenção hoje. Raio-X portátil disponível se o paciente estabilizar!',
      BLOOD_TRANSFUSION_O_NEG: 'Não temos bolsa O negativo estocada nesta UPA. Já acionamos a regulação, use Ringer Lactato!',
      VIDEO_LARYNGOSCOPE: 'Sem videolaringoscópio na UPA. Temos laringoscópio Macintosh tradicional nº 3 e 4 e fio-guia Bougie.',
    },
  },
  SALA_VERMELHA_TERCIARIA: {
    facility: 'SALA_VERMELHA_TERCIARIA',
    label: 'Hospital Terciário (HC-FMUSP / UNICAMP - Sala Vermelha)',
    maxNurses: 3,
    availableSupplies: {
      O2_CATHETER: true,
      BAG_VALVE_MASK: true,
      PERIPHERAL_IV_CRYSTALLOID: true,
      EPINEPHRINE_IM_IV: true,
      JELCO_14G_THORACOCENTESIS: true,
      DEFINITIVE_AIRWAY_TOT: true,
      NOREPINEPHRINE_PUMP: true,
      CHEST_TUBE_WATER_SEAL: true,
      CENTRAL_VENOUS_CATHETER: true,
      EFAST_ULTRASOUND: true,
      BLOOD_TRANSFUSION_O_NEG: true,
      VIDEO_LARYNGOSCOPE: true,
    },
    unavailableRejectionMessages: {},
  },
};
