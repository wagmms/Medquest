// src/lib/engine/nursing-queue-engine.ts

import { NursingTask, SUS_FACILITY_MATRICES, SUSFacilityLevel } from '@/types/osce-stage3';

export interface NursingOrderTemplate {
  code: string;
  title: string;
  category: NursingTask['category'];
  baseDurationMs: number;
  requiredSupplies: string[];
  onCompleteEffectId: string;
  initialFeedback: string;
  completionFeedback: string;
  complicationChance?: number;
  complicationFeedback?: string;
}

export const NURSING_CATALOG: Record<string, NursingOrderTemplate> = {
  PREP_NORA_PUMP: {
    code: 'PREP_NORA_PUMP',
    title: 'Diluir Noradrenalina (4 amp + 234ml SG5%) em BIC',
    category: 'MEDICATION',
    baseDurationMs: 40000, // 40 segundos
    requiredSupplies: ['NOREPINEPHRINE_PUMP'],
    onCompleteEffectId: 'START_VASOPRESSOR_NOREPINEPHRINE',
    initialFeedback: 'Enfermagem: "Abrindo as ampolas de Nora e montando a bomba de infusão, doutor..."',
    completionFeedback: 'Enfermagem: "Noradrenalina instalada em bomba a 10 ml/h! Aguardando titular."',
  },
  PERIPHERAL_IV_2X: {
    code: 'PERIPHERAL_IV_2X',
    title: '2 Acessos Venosos Periféricos (Jelco 14/16) + Coleta + SRL',
    category: 'ACCESS',
    baseDurationMs: 25000, // 25 segundos
    requiredSupplies: ['PERIPHERAL_IV_CRYSTALLOID'],
    onCompleteEffectId: 'ESTABLISH_PERIPHERAL_ACCESS',
    initialFeedback: 'Enfermagem: "Garroteando ambos os membros superiores para puncionar com Jelco calibroso..."',
    completionFeedback: 'Enfermagem: "Dois acessos calibrosos garantidos! Correndo Ringer Lactato aquecido aberto."',
    complicationChance: 0.35, // Se em choque profundo, risco de colapso venoso
    complicationFeedback: 'Enfermagem: "Doutor, paciente muito vasoconstrito! Perdi a veia periférica! Vai puncionar Intraósseo ou Central?"',
  },
  PREP_RSI_DRUGS: {
    code: 'PREP_RSI_DRUGS',
    title: 'Preparo de IOT (Sedativo / Bloqueador) + Checar TOT com cuff',
    category: 'AIRWAY_PREP',
    baseDurationMs: 30000, // 30 segundos
    requiredSupplies: ['DEFINITIVE_AIRWAY_TOT'],
    onCompleteEffectId: 'RSI_DRUGS_READY_AT_BEDSIDE',
    initialFeedback: 'Enfermagem: "Aspirando drogas de indução e testando balonete do tubo 8.0..."',
    completionFeedback: 'Enfermagem: "Drogas de IOT aspiradas e identificadas! Laringoscópio testado e pronto à beira-leito."',
  },
  PREP_CHEST_DRAIN_TRAY: {
    code: 'PREP_CHEST_DRAIN_TRAY',
    title: 'Bandeja de Drenagem Torácica + Dreno 32Fr + Selo D’Água',
    category: 'AIRWAY_PREP',
    baseDurationMs: 35000, // 35 segundos
    requiredSupplies: ['CHEST_TUBE_WATER_SEAL'],
    onCompleteEffectId: 'CHEST_TUBE_TRAY_READY',
    initialFeedback: 'Enfermagem: "Montando o sistema de selo d’água com SF e abrindo a bandeja estéril..."',
    completionFeedback: 'Enfermagem: "Mesa de drenagem torácica pronta e lidocaína na agulha. Pode proceder à drenagem!"',
  },
};

export class NursingQueueManager {
  private tasks: NursingTask[] = [];
  private facility: SUSFacilityLevel;
  private isPatientInSevereShock: boolean = false;

  constructor(facility: SUSFacilityLevel) {
    this.facility = facility;
  }

  public setShockState(inShock: boolean) {
    this.isPatientInSevereShock = inShock;
  }

  public orderTask(
    orderCode: string,
    currentSimTimeMs: number
  ): { accepted: boolean; task?: NursingTask; rejectionReason?: string } {
    const template = NURSING_CATALOG[orderCode];
    if (!template) {
      return { accepted: false, rejectionReason: 'Ordem desconhecida pela equipe de enfermagem.' };
    }

    const matrix = SUS_FACILITY_MATRICES[this.facility];

    // 1. Checagem de Insumos da Unidade SUS
    for (const reqSupply of template.requiredSupplies) {
      if (!matrix.availableSupplies[reqSupply]) {
        const msg =
          matrix.unavailableRejectionMessages[reqSupply] ||
          `Insumo indisponível neste nível de atenção (${matrix.label}).`;
        return { accepted: false, rejectionReason: msg };
      }
    }

    // 2. Prevenção de duplicidade ativa
    const existing = this.tasks.find(
      (t) => t.onCompleteEffectId === template.onCompleteEffectId && t.status !== 'COMPLICATION'
    );
    if (existing) {
      return {
        accepted: false,
        rejectionReason: 'Enfermagem: "Doutor, já estamos providenciando ou já concluímos este pedido!"',
      };
    }

    // 3. Capacidade simultânea da equipe (1 na UBS, 2 na UPA, 3 no Terciário)
    const activeCount = this.tasks.filter((t) => t.status === 'PREPARING').length;
    const initialStatus = activeCount < matrix.maxNurses ? 'PREPARING' : 'QUEUED';

    const newTask: NursingTask = {
      id: `${orderCode}_${Date.now()}`,
      title: template.title,
      category: template.category,
      orderedAtSimTimeMs: currentSimTimeMs,
      durationMs: template.baseDurationMs,
      elapsedMs: 0,
      status: initialStatus,
      nurseFeedback:
        initialStatus === 'PREPARING'
          ? template.initialFeedback
          : `Equipe ocupada (${matrix.maxNurses} profissional). Pedido colocado na fila de atendimento!`,
      requiredSupplies: template.requiredSupplies,
      onCompleteEffectId: template.onCompleteEffectId,
      complicationChance: this.isPatientInSevereShock ? template.complicationChance : 0,
      fallbackSuggestion: template.complicationFeedback,
    };

    this.tasks.push(newTask);
    return { accepted: true, task: newTask };
  }

  /**
   * Chamado a cada tick de 1000ms do loop principal
   */
  public tick(deltaMs: number): {
    completedEvents: string[];
    nurseAlerts: string[];
    tasksSnapshot: NursingTask[];
  } {
    const matrix = SUS_FACILITY_MATRICES[this.facility];
    const completedEvents: string[] = [];
    const nurseAlerts: string[] = [];

    // Promove tarefas da fila (QUEUED -> PREPARING) se houver profissional vago
    let activeCount = this.tasks.filter((t) => t.status === 'PREPARING').length;
    for (const task of this.tasks) {
      if (task.status === 'QUEUED' && activeCount < matrix.maxNurses) {
        task.status = 'PREPARING';
        activeCount++;
        nurseAlerts.push(`Enfermagem iniciou o preparo: ${task.title}`);
      }
    }

    // Avança o progresso das tarefas em execução
    for (const task of this.tasks) {
      if (task.status === 'PREPARING') {
        task.elapsedMs += deltaMs;

        if (task.elapsedMs >= task.durationMs) {
          // Checa se ocorreu intercorrência técnica no choque
          if (task.complicationChance && Math.random() < task.complicationChance) {
            task.status = 'COMPLICATION';
            task.nurseFeedback = task.fallbackSuggestion || 'Intercorrência técnica no procedimento!';
            nurseAlerts.push(task.nurseFeedback);
          } else {
            task.status = 'COMPLETED';
            completedEvents.push(task.onCompleteEffectId);
            const tpl = Object.values(NURSING_CATALOG).find(
              (c) => c.onCompleteEffectId === task.onCompleteEffectId
            );
            task.nurseFeedback = tpl?.completionFeedback || 'Procedimento concluído.';
            nurseAlerts.push(task.nurseFeedback);
          }
        }
      }
    }

    return {
      completedEvents,
      nurseAlerts,
      tasksSnapshot: [...this.tasks],
    };
  }
}
