"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Crosshair,
  Clock, Package, Scissors
} from "lucide-react";
import { OsceSpokenQueueItem, OsceLiveFeedback } from "@/types/api";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import {
  SUSFacilityLevel,
  SUS_FACILITY_MATRICES,
  NursingTask,
  AnatomicalHitbox,
} from "@/types/osce-stage3";
import { MANNEQUIN_HITBOXES } from "@/lib/anatomy/mannequin-landmarks";
import { NursingQueueManager, NURSING_CATALOG } from "@/lib/engine/nursing-queue-engine";

export type ActiveInstrument =
  | "PALPATE_TRACHEA"
  | "AUSCULTATION_BASE"
  | "THORACOCENTESIS_RELIEF"
  | "CHEST_TUBE_INSERTION"
  | "SURGICAL_CRICOTHYROIDOTOMY"
  | "EFAST_PROBE"
  | "INTRAOSSEOUS_ACCESS"
  | "CENTRAL_LINE_INSERTION";

interface InstrumentMeta {
  id: ActiveInstrument;
  label: string;
  shortDesc: string;
  requiresPreparedSupplyId?: string;
}

const INSTRUMENTS: InstrumentMeta[] = [
  { id: "AUSCULTATION_BASE", label: "Estetoscópio / Semiologia", shortDesc: "Ausculta e palpação de marcos" },
  { id: "THORACOCENTESIS_RELIEF", label: "Jelco 14G (Toracocentese)", shortDesc: "Descompressão imediata (2º ou 5º EIC)" },
  {
    id: "CHEST_TUBE_INSERTION",
    label: "Dreno Tubular 32Fr + Bisturi",
    shortDesc: "Drenagem fechada em selo d’água (requer bandeja pronta)",
    requiresPreparedSupplyId: "CHEST_TUBE_TRAY_READY",
  },
  { id: "SURGICAL_CRICOTHYROIDOTOMY", label: "Bisturi Lâmina 11 (Crico)", shortDesc: "Via aérea cirúrgica de emergência" },
  { id: "EFAST_PROBE", label: "Transdutor USG Convexo (E-FAST)", shortDesc: "POCUS trauma: janelas torácicas e abdominais" },
  { id: "INTRAOSSEOUS_ACCESS", label: "Dispositivo Intraósseo (EZ-IO)", shortDesc: "Acesso tibial proximal de urgência" },
  { id: "CENTRAL_LINE_INSERTION", label: "Acesso Central (Seldinger)", shortDesc: "Punção Jugular Interna ou Subclávia" },
];

interface ProcedureMannequinProps {
  sessionId: string;
  elapsedSeconds: number;
  onProcedureExecuted: (
    title: string,
    findings: string,
    examinerMessage: string,
    spokenQueue: OsceSpokenQueueItem[],
    guidedFeedback?: OsceLiveFeedback
  ) => void;
  isLoading?: boolean;
  institution?: string;
}

export function ProcedureMannequin({
  sessionId,
  elapsedSeconds,
  onProcedureExecuted,
  isLoading = false,
  institution = "USP-RP",
}: ProcedureMannequinProps) {
  // Inicialização do nível SUS a partir do hospital
  const initialFacility: SUSFacilityLevel =
    institution.toLowerCase().includes("ubs")
      ? "UBS_PRIMARIA"
      : institution.toLowerCase().includes("upa")
      ? "UPA_SECUNDARIA"
      : "SALA_VERMELHA_TERCIARIA";

  const [facility, setFacility] = useState<SUSFacilityLevel>(initialFacility);
  const queueManagerRef = useRef<NursingQueueManager>(new NursingQueueManager(initialFacility));

  // Estados da Fila de Enfermagem
  const [tasks, setTasks] = useState<NursingTask[]>([]);
  const [completedEffects, setCompletedEffects] = useState<string[]>([]);

  // Estados do Manequim e Instrumental
  const [activeInstrument, setActiveInstrument] = useState<ActiveInstrument>("THORACOCENTESIS_RELIEF");
  const [showSkeletalLandmarks, setShowSkeletalLandmarks] = useState<boolean>(true);
  const [hoveredHitbox, setHoveredHitbox] = useState<AnatomicalHitbox | null>(null);
  const [performedProcedures, setPerformedProcedures] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeSite, setActiveSite] = useState<string | null>(null);

  // Troca de nível de atenção SUS
  const handleFacilityChange = (newLevel: SUSFacilityLevel) => {
    setFacility(newLevel);
    queueManagerRef.current = new NursingQueueManager(newLevel);
    setTasks([]);
    setCompletedEffects([]);
    toast(`Nível de atenção alterado: ${SUS_FACILITY_MATRICES[newLevel].label}`, { icon: "🏥" });
  };

  // Tick da Enfermagem a cada 1 segundo (Game Loop de Latência)
  useEffect(() => {
    const interval = setInterval(() => {
      const { completedEvents, nurseAlerts, tasksSnapshot } = queueManagerRef.current.tick(1000);
      setTasks(tasksSnapshot);

      if (completedEvents.length > 0) {
        setCompletedEffects((prev) => [...prev, ...completedEvents]);
      }

      nurseAlerts.forEach((alert) => {
        const isComplication = alert.includes("Perdi a veia") || alert.includes("Intercorrência");
        if (isComplication) {
          toast.error(alert, { duration: 5000 });
        } else {
          toast.success(alert, { duration: 4000 });
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Solicitar preparo à equipe de enfermagem
  const handleOrderNursing = (orderCode: string) => {
    const res = queueManagerRef.current.orderTask(orderCode, elapsedSeconds * 1000);
    if (!res.accepted) {
      toast.error(res.rejectionReason || "Pedido não autorizado no momento.", { duration: 4500 });
    } else if (res.task) {
      toast(res.task.nurseFeedback, { icon: "⏱️" });
      setTasks((prev) => [...prev, res.task!]);
    }
  };

  // Execução de Procedimento no Hitbox Anatômico
  const handleHitboxClick = useCallback(async (hitbox: AnatomicalHitbox) => {
    if (isProcessing || isLoading || !sessionId) return;
    const instrumentMeta = INSTRUMENTS.find((i) => i.id === activeInstrument);

    // 1. Checagem de Trava Física: O instrumento exige bandeja prévia da enfermagem?
    if (
      instrumentMeta?.requiresPreparedSupplyId &&
      !completedEffects.includes(instrumentMeta.requiresPreparedSupplyId)
    ) {
      toast.error(
        `BLOQUEIO DE SEGURANÇA: Material indisponível à beira-leito! Solicite o preparo da "${instrumentMeta.label}" à equipe de enfermagem ao lado e aguarde a montagem.`,
        { duration: 6000 }
      );
      return;
    }

    // 2. Checagem de Ultrassom na Unidade SUS
    if (activeInstrument === "EFAST_PROBE" && !SUS_FACILITY_MATRICES[facility].availableSupplies.EFAST_ULTRASOUND) {
      toast.error(SUS_FACILITY_MATRICES[facility].unavailableRejectionMessages.EFAST_ULTRASOUND, { duration: 6000 });
      return;
    }

    // 3. Checagem de Iatrogenia Cirúrgica (Borda Inferior da Costela ou Istmo Tireoidiano)
    if (hitbox.isIatrogenicZone && hitbox.iatrogenicOutcome) {
      const outcome = hitbox.iatrogenicOutcome;
      toast.error(
        `🚨 IATROGENIA CRÍTICA (${outcome.bancaPenaltyPoints} pts no Barema): ${outcome.complicationName}! ${outcome.feedbackMessage}`,
        { duration: 8000 }
      );
    }

    setIsProcessing(true);
    setActiveSite(hitbox.id);

    try {
      const res = await api.osce.performProcedure(sessionId, activeInstrument, hitbox.id, elapsedSeconds);
      if (res?.success) {
        setPerformedProcedures((prev) => [...prev, `${activeInstrument}@${hitbox.id}`]);
        toast.success(`Procedimento executado: ${hitbox.name}`);
        onProcedureExecuted(
          hitbox.name,
          res.findings,
          res.examiner_message,
          res.spoken_queue || [],
          res.guided_feedback
        );
      }
    } catch {
      toast.error("Erro ao registrar procedimento beira-leito.");
    } finally {
      setIsProcessing(false);
    }
  }, [activeInstrument, completedEffects, elapsedSeconds, facility, isLoading, isProcessing, onProcedureExecuted, sessionId]);

  const activeMeta = INSTRUMENTS.find((i) => i.id === activeInstrument);

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* 1. SELETOR DE COMPLEXIDADE DO SUS & CONTROLE DE MODO DO MANEQUIM */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-2xl bg-slate-900 border border-slate-800 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded border border-amber-500/30 flex items-center gap-1">
            <Package className="w-3.5 h-3.5" />
            Nível SUS:
          </span>
          <div className="flex gap-1.5">
            {(["UBS_PRIMARIA", "UPA_SECUNDARIA", "SALA_VERMELHA_TERCIARIA"] as SUSFacilityLevel[]).map((lvl) => (
              <button
                key={lvl}
                type="button"
                onClick={() => handleFacilityChange(lvl)}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all cursor-pointer ${
                  facility === lvl
                    ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/40"
                    : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                }`}
              >
                {lvl === "UBS_PRIMARIA" && "UBS"}
                {lvl === "UPA_SECUNDARIA" && "UPA 24h"}
                {lvl === "SALA_VERMELHA_TERCIARIA" && "Sala Vermelha (Terciário)"}
              </button>
            ))}
          </div>
        </div>

        {/* Alternar Modo Treino com Reparos Ósseos vs Modo Prova Real */}
        <button
          type="button"
          onClick={() => setShowSkeletalLandmarks((s) => !s)}
          className={`px-3 py-1.5 rounded-xl font-bold transition-all cursor-pointer border ${
            showSkeletalLandmarks
              ? "bg-indigo-600/20 border-indigo-500 text-indigo-300"
              : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
          }`}
        >
          {showSkeletalLandmarks ? "🦴 Reparos Ósseos: VISÍVEIS (Modo Treino)" : "👁️ Reparos Ocultos (Modo Prova Real)"}
        </button>
      </div>

      {/* 2. GRID PRINCIPAL: MESA CIRÚRGICA (ESQ) + MANEQUIM 2D (CENTRO) + FILA DE ENFERMAGEM (DIR) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        
        {/* COLUNA 1: INSTRUMENTAL CIRÚRGICO ATIVO (3 COLS) */}
        <div className="lg:col-span-3 space-y-2 bg-slate-900/90 border border-slate-800 rounded-2xl p-3">
          <div className="flex items-center justify-between pb-2 mb-1 border-b border-slate-800 text-xs">
            <span className="font-bold text-white flex items-center gap-1.5">
              <Scissors className="w-3.5 h-3.5 text-primary" />
              Instrumento em Mãos
            </span>
          </div>

          <div className="space-y-1.5">
            {INSTRUMENTS.map((inst) => {
              const isLocked =
                inst.requiresPreparedSupplyId &&
                !completedEffects.includes(inst.requiresPreparedSupplyId);

              return (
                <button
                  key={inst.id}
                  type="button"
                  onClick={() => setActiveInstrument(inst.id)}
                  className={`w-full text-left p-2 rounded-xl border transition-all cursor-pointer ${
                    activeInstrument === inst.id
                      ? "bg-sky-600/20 border-sky-500 text-white shadow-md ring-1 ring-sky-500/50"
                      : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="text-xs font-bold flex items-center justify-between">
                    <span className="truncate">{inst.label}</span>
                    {isLocked && (
                      <span className="text-[9px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30 shrink-0 font-mono">
                        Aguarda Enfermagem
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">{inst.shortDesc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* COLUNA 2: MANEQUIM ANATÔMICO 2D VETORIAL (6 COLS) */}
        <div className="lg:col-span-6 bg-slate-950 rounded-2xl border border-slate-800 p-3 flex flex-col items-center justify-center relative overflow-hidden min-h-[440px]">
          <div className="w-full flex items-center justify-between pb-2 mb-2 border-b border-slate-800/80 text-xs">
            <span className="font-mono text-[11px] text-slate-400 flex items-center gap-1.5">
              <Crosshair className="w-3.5 h-3.5 text-sky-400 animate-pulse" />
              Manequim Cirúrgico de Precisão
            </span>
            <span className="text-[11px] font-bold text-sky-400 truncate max-w-[200px]">
              Alvo: {activeMeta?.label}
            </span>
          </div>

          {/* SVG ANATÔMICO MULTICAMADAS COM HITBOXES MILIMÉTRICOS */}
          <div className="relative w-full max-w-[340px] select-none">
            <svg viewBox="0 0 400 520" className="w-full h-auto cursor-crosshair">
              {/* CAMADA 1: SILHUETA CORPORAL */}
              <g id="layer-skin" fill="#1e293b" stroke="#475569" strokeWidth="2">
                <ellipse cx="200" cy="52" rx="34" ry="42" />
                <path d="M 182,90 L 182,130 L 218,130 L 218,90 Z" />
                <path d="M 120,130 C 145,122 255,122 280,130 L 295,210 L 270,350 L 130,350 L 105,210 Z" />
                <path d="M 135,350 L 192,350 L 185,500 L 142,500 Z" />
                <path d="M 208,350 L 265,350 L 258,500 L 215,500 Z" />
              </g>

              {/* CAMADA 2: REPAROS ESQUELÉTICOS (VISÍVEIS NO MODO TREINO) */}
              {showSkeletalLandmarks && (
                <g id="layer-skeleton" opacity="0.7">
                  {/* Cartilagens Tireoide e Cricoide */}
                  <polygon points="193,96 207,96 204,107 196,107" fill="none" stroke="#94a3b8" strokeWidth="1.5" />
                  <rect x="193" y="116" width="14" height="6" rx="2" fill="none" stroke="#94a3b8" strokeWidth="1.5" />

                  {/* Clavículas e Esterno */}
                  <path d="M 125,134 Q 160,142 192,138" fill="none" stroke="#cbd5e1" strokeWidth="3" />
                  <path d="M 275,134 Q 240,142 208,138" fill="none" stroke="#cbd5e1" strokeWidth="3" />
                  <rect x="193" y="138" width="14" height="85" rx="3" fill="#334155" stroke="#94a3b8" strokeWidth="1.5" />

                  {/* Arcos Costais e Feixes Intercostais (2ª a 6ª costelas) */}
                  {[148, 170, 192, 214].map((y, idx) => (
                    <g key={y}>
                      {/* Costela Direita */}
                      <path
                        d={`M 193,${y} Q 155,${y + 2} 125,${y + 12}`}
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="4.5"
                      />
                      {/* Feixe Vásculo-Nervoso (VAN) na borda INFERIOR da costela em vermelho */}
                      <path
                        d={`M 190,${y + 3.5} Q 155,${y + 5.5} 127,${y + 15}`}
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="1.2"
                        strokeDasharray="2,2"
                      />
                      {/* Costela Esquerda */}
                      <path
                        d={`M 207,${y} Q 245,${y + 2} 275,${y + 12}`}
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="4.5"
                      />
                      <text x="197" y={y + 13} fontSize="7" fill="#cbd5e1" fontFamily="monospace">
                        {idx + 2}ºEIC
                      </text>
                    </g>
                  ))}

                  {/* Tuberosidade Tibial */}
                  <circle cx="165" cy="438" r="5" fill="none" stroke="#94a3b8" strokeWidth="1.5" />
                </g>
              )}

              {/* CAMADA 3: HITBOXES ANATÔMICOS CIRÚRGICOS */}
              <g id="layer-hitboxes">
                {MANNEQUIN_HITBOXES.map((hb) => {
                  const isHovered = hoveredHitbox?.id === hb.id;
                  const isDone = performedProcedures.some((p) => p.endsWith(`@${hb.id}`));
                  const isCurrentActive = activeSite === hb.id;

                  return (
                    <g key={hb.id}>
                      <path
                        d={hb.svgPath}
                        onMouseEnter={() => setHoveredHitbox(hb)}
                        onMouseLeave={() => setHoveredHitbox(null)}
                        onClick={() => handleHitboxClick(hb)}
                        fill={
                          isCurrentActive
                            ? "rgba(234, 179, 8, 0.6)"
                            : isDone
                            ? "rgba(16, 185, 129, 0.5)"
                            : isHovered
                            ? hb.isIatrogenicZone && showSkeletalLandmarks
                              ? "rgba(239, 68, 68, 0.55)"
                              : "rgba(56, 189, 248, 0.55)"
                            : showSkeletalLandmarks
                            ? "rgba(148, 163, 184, 0.15)"
                            : "transparent"
                        }
                        stroke={
                          isDone
                            ? "#10b981"
                            : isHovered
                            ? hb.isIatrogenicZone && showSkeletalLandmarks
                              ? "#ef4444"
                              : "#38bdf8"
                            : showSkeletalLandmarks
                            ? "rgba(148, 163, 184, 0.4)"
                            : "transparent"
                        }
                        strokeWidth="1.5"
                        className="transition-colors duration-150 cursor-pointer"
                      />
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* TOOLTIP DE PRECISÃO ANATÔMICA (LUPA DE PALPAÇÃO) */}
            {hoveredHitbox && (
              <div className="absolute bottom-2 left-2 right-2 bg-slate-900/95 border border-sky-500/60 rounded-xl p-2.5 shadow-2xl pointer-events-none text-xs">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-bold text-sky-400">{hoveredHitbox.name}</span>
                  {hoveredHitbox.isIatrogenicZone && showSkeletalLandmarks && (
                    <span className="text-[9px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded font-bold border border-rose-500/40">
                      ZONA DE RISCO IATROGÊNICO
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-300 leading-snug">
                  {hoveredHitbox.anatomicalLandmarkText}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* COLUNA 3: GESTÃO DE ENFERMAGEM & INSUMOS CRÍTICOS (3 COLS) */}
        <div className="lg:col-span-3 space-y-3 bg-slate-900/90 border border-slate-800 rounded-2xl p-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-xs">
            <span className="font-bold text-white flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              Equipe de Enfermagem
            </span>
            <span className="text-[10px] font-mono text-emerald-400">
              {SUS_FACILITY_MATRICES[facility].maxNurses} prof. disponíveis
            </span>
          </div>

          {/* Ordens Prontas para Delegação com Latência */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
              Ordens de Beira-Leito:
            </span>
            {Object.values(NURSING_CATALOG).map((order) => (
              <button
                key={order.code}
                type="button"
                onClick={() => handleOrderNursing(order.code)}
                className="w-full text-left p-2 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/50 text-xs transition-all flex items-center justify-between cursor-pointer"
              >
                <span className="font-medium text-slate-200 truncate pr-2">{order.title}</span>
                <span className="text-[9px] font-mono bg-slate-900 px-1.5 py-0.5 rounded text-amber-400 shrink-0 border border-slate-800">
                  ~{order.baseDurationMs / 1000}s
                </span>
              </button>
            ))}
          </div>

          {/* Barras de Progresso e Fila em Tempo Real */}
          <div className="pt-2 border-t border-slate-800 space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
              Preparo à Beira-Leito:
            </span>
            {tasks.length === 0 && (
              <p className="text-xs text-slate-500 italic py-1">Nenhum preparo em andamento.</p>
            )}
            {tasks.map((t) => {
              const pct = Math.min(100, Math.round((t.elapsedMs / t.durationMs) * 100));
              return (
                <div key={t.id} className="bg-slate-950 p-2 rounded-xl border border-slate-800 text-xs">
                  <div className="flex justify-between items-center text-[11px] mb-1">
                    <span className="font-semibold text-slate-200 truncate pr-1">{t.title}</span>
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.2 rounded font-mono ${
                        t.status === "COMPLETED"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : t.status === "COMPLICATION"
                          ? "bg-rose-500/20 text-rose-400"
                          : t.status === "QUEUED"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-sky-500/20 text-sky-400"
                      }`}
                    >
                      {t.status === "PREPARING" ? `${pct}%` : t.status}
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        t.status === "COMPLETED"
                          ? "bg-emerald-500"
                          : t.status === "COMPLICATION"
                          ? "bg-rose-500"
                          : "bg-sky-500"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
