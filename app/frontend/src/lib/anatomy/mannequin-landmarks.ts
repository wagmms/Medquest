// src/lib/anatomy/mannequin-landmarks.ts

import { AnatomicalHitbox } from '@/types/osce-stage3';

export const MANNEQUIN_HITBOXES: AnatomicalHitbox[] = [
  // =========================================================================
  // 1. CRICOTIREOIDOSTOMIA / VIA AÉREA CIRÚRGICA
  // =========================================================================
  {
    id: 'CRICOID_MEMBRANE_EXACT',
    name: 'Membrana Cricotireoidea (Topografia Correta)',
    view: 'ANTERIOR',
    svgPath: 'M 192,108 L 208,108 L 208,116 L 192,116 Z',
    labelCoords: { x: 200, y: 112 },
    allowedProcedures: ['SURGICAL_CRICOTHYROIDOTOMY', 'NEEDLE_CRICOTHYROIDOTOMY', 'PALPATE_TRACHEA'],
    anatomicalLandmarkText:
      'Depressão entre a cartilagem tireoide (pomo de adão) e a cartilagem cricoide. Local exato para cricotireoidostomia cirúrgica.',
  },
  {
    id: 'THYROID_GLAND_IATROGENIC',
    name: 'Istmo da Tireoide / Traqueostomia Alta (Zona de Risco Iatrogênico)',
    view: 'ANTERIOR',
    svgPath: 'M 190,118 L 210,118 L 210,130 L 190,130 Z',
    labelCoords: { x: 200, y: 124 },
    allowedProcedures: ['SURGICAL_CRICOTHYROIDOTOMY'],
    anatomicalLandmarkText: 'Região infra-cricoidea sobre o istmo da tireoide e plexo venoso.',
    isIatrogenicZone: true,
    iatrogenicOutcome: {
      complicationName: 'Hemorragia Cervical Maciça por Lesão do Istmo Tireoidiano',
      bancaPenaltyPoints: -2.5,
      vitalSignImpact: { hrDelta: 25, sbpDelta: -30, spo2Delta: -15 },
      feedbackMessage:
        'ERRO CRÍTICO DE TÉCNICA: Incisão realizada ABAIXO da cartilagem cricoide (tentativa de traqueostomia de urgência sobre o istmo tireoidiano), gerando sangramento incoercível! A via aérea cirúrgica de emergência é na MEMBRANA CRICOTIREOIDEA!',
    },
  },

  // =========================================================================
  // 2. DESCOMPRESSÃO TORÁCICA (2º EIC LINHA HEMICLAVICULAR)
  // =========================================================================
  {
    id: 'RIGHT_2ND_ICS_SUPERIOR_BORDER_SAFE',
    name: '2º EIC Direito - Linha Hemiclavicular (Borda Superior da 3ª Costela)',
    view: 'ANTERIOR',
    svgPath: 'M 145,162 L 172,162 L 172,169 L 145,169 Z',
    labelCoords: { x: 158, y: 166 },
    allowedProcedures: ['THORACOCENTESIS_RELIEF', 'AUSCULTATION_BASE'],
    anatomicalLandmarkText:
      '2º Espaço Intercostal Direito na Linha Hemiclavicular, rente à BORDA SUPERIOR da costela inferior (evita o feixe vásculo-nervoso).',
  },
  {
    id: 'RIGHT_2ND_ICS_INFERIOR_BORDER_IATROGENIC',
    name: '2º EIC Direito - Borda Inferior da 2ª Costela (Feixe Intercostal!)',
    view: 'ANTERIOR',
    svgPath: 'M 145,154 L 172,154 L 172,161 L 145,161 Z',
    labelCoords: { x: 158, y: 157 },
    allowedProcedures: ['THORACOCENTESIS_RELIEF'],
    anatomicalLandmarkText: 'Borda INFERIOR da costela superior (sulco costal onde passa o feixe vásculo-nervoso VAN).',
    isIatrogenicZone: true,
    iatrogenicOutcome: {
      complicationName: 'Hemotórax Iatrogênico por Laceração de Artéria Intercostal',
      bancaPenaltyPoints: -1.5,
      vitalSignImpact: { hrDelta: 20, sbpDelta: -25, spo2Delta: -5 },
      feedbackMessage:
        'IATROGENIA DE BANCA: Você puncionou rente à BORDA INFERIOR da costela superior, lacerando o feixe vásculo-nervoso intercostal! A punção de alívio e drenagem devem ser SEMPRE na BORDA SUPERIOR da costela inferior!',
    },
  },

  // =========================================================================
  // 3. DRENAGEM DE TÓRAX (TRIÂNGULO DE SEGURANÇA DE BÜLAU)
  // =========================================================================
  {
    id: 'RIGHT_5TH_ICS_SAFE_TRIANGLE',
    name: '5º EIC Direito - Linha Axilar Média (Triângulo de Segurança)',
    view: 'ANTERIOR',
    svgPath: 'M 122,205 L 145,205 L 145,222 L 122,222 Z',
    labelCoords: { x: 133, y: 213 },
    allowedProcedures: ['CHEST_TUBE_INSERTION', 'THORACOCENTESIS_RELIEF', 'AUSCULTATION_BASE'],
    anatomicalLandmarkText:
      '5º Espaço Intercostal Direito na Linha Axilar Média (Triângulo de Segurança de Bülau: peitoral maior, grande dorsal e linha mamilar).',
  },
  {
    id: 'LEFT_5TH_ICS_SAFE_TRIANGLE',
    name: '5º EIC Esquerdo - Linha Axilar Média (Triângulo de Segurança)',
    view: 'ANTERIOR',
    svgPath: 'M 255,205 L 278,205 L 278,222 L 255,222 Z',
    labelCoords: { x: 266, y: 213 },
    allowedProcedures: ['CHEST_TUBE_INSERTION', 'THORACOCENTESIS_RELIEF', 'AUSCULTATION_BASE'],
    anatomicalLandmarkText:
      '5º Espaço Intercostal Esquerdo na Linha Axilar Média (Triângulo de Segurança).',
  },

  // =========================================================================
  // 4. JANELAS ULTRASSONOGRÁFICAS DO E-FAST
  // =========================================================================
  {
    id: 'EFAST_SUBXIPHOID_PERICARDIAL',
    name: 'Janela Subxifoidea (Pericárdio)',
    view: 'ANTERIOR',
    svgPath: 'M 188,228 L 212,228 L 212,246 L 188,246 Z',
    labelCoords: { x: 200, y: 237 },
    allowedProcedures: ['EFAST_PROBE'],
    anatomicalLandmarkText: 'Região subxifoidea angulando transdutor para o ombro esquerdo (avaliação de tamponamento).',
  },
  {
    id: 'EFAST_RUQ_MORRISON',
    name: 'Janela QSD (Espaço Hepatorrenal de Morrison)',
    view: 'ANTERIOR',
    svgPath: 'M 135,240 L 165,240 L 165,270 L 135,270 Z',
    labelCoords: { x: 150, y: 255 },
    allowedProcedures: ['EFAST_PROBE'],
    anatomicalLandmarkText: 'Linha axilar média direita entre 8º e 11º EIC (avalia líquido livre em Morrison e hemitórax).',
  },
  {
    id: 'EFAST_LUQ_SPLENORENAL',
    name: 'Janela QSE (Espaço Esplenorrenal / Recesso de Koller)',
    view: 'ANTERIOR',
    svgPath: 'M 235,235 L 265,235 L 265,265 L 235,265 Z',
    labelCoords: { x: 250, y: 250 },
    allowedProcedures: ['EFAST_PROBE'],
    anatomicalLandmarkText: 'Linha axilar posterior esquerda entre 6º e 9º EIC (espaço esplenorrenal e recesso costofrênico).',
  },
  {
    id: 'EFAST_SUPRAPUBIC_PELVIC',
    name: 'Janela Suprapúbica (Pélvica / Fundo de Saco de Douglas)',
    view: 'ANTERIOR',
    svgPath: 'M 185,315 L 215,315 L 215,338 L 185,338 Z',
    labelCoords: { x: 200, y: 326 },
    allowedProcedures: ['EFAST_PROBE'],
    anatomicalLandmarkText: 'Região suprapúbica em cortes transversal e longitudinal para avaliar líquido livre pélvico.',
  },

  // =========================================================================
  // 5. ACESSO INTRAÓSSEO E ACESSO CENTRAL
  // =========================================================================
  {
    id: 'RIGHT_IJV_SELDINGER_TRIANGLE',
    name: 'Veia Jugular Interna Direita (Trígono de Sedillot)',
    view: 'ANTERIOR',
    svgPath: 'M 168,110 L 185,110 L 185,128 L 168,128 Z',
    labelCoords: { x: 176, y: 119 },
    allowedProcedures: ['CENTRAL_LINE_INSERTION'],
    anatomicalLandmarkText:
      'Ápice do triângulo de Sedillot (feixes esternal e clavicular do ECM), direcionando agulha para o mamilo ipsilateral.',
  },
  {
    id: 'PROXIMAL_TIBIA_IO_RIGHT',
    name: 'Tíbia Proximal Direita (Acesso Intraósseo EZ-IO)',
    view: 'ANTERIOR',
    svgPath: 'M 155,445 L 175,445 L 175,468 L 155,468 Z',
    labelCoords: { x: 165, y: 456 },
    allowedProcedures: ['INTRAOSSEOUS_ACCESS'],
    anatomicalLandmarkText: 'Superfície anteromedial plana da tíbia, 2 cm distal e 1-2 cm medial à tuberosidade tibial.',
  },
];
