"use client";

import React, { useState } from "react";
import {
  Award,
  CheckCircle2,
  XCircle,
  Clock,
  BookOpen,
  RotateCcw,
  ChevronRight,
  ShieldAlert,
  HelpCircle,
  FileText,
  Activity,
  HeartPulse,
} from "lucide-react";
import {
  PreceptorFeedback,
  CompetencyRadarScores,
  EvaluatedBaremaItem,
  FulfillmentStatus,
} from "@/types/osce-evaluation";

interface StationResultMirrorProps {
  feedback: PreceptorFeedback;
  stationTitle: string;
  institution: string;
  area: string;
  subtema?: string;
  elapsedSeconds: number;
  onRetryStation: () => void;
  onGoBack?: () => void;
}

// =========================================================================
// RADAR DE 5 COMPETÊNCIAS MÉDICAS EM SVG PURO (LEVE & 60FPS)
// =========================================================================
function CompetencyRadarSVG({ scores }: { scores?: CompetencyRadarScores }) {
  const safeScores: CompetencyRadarScores = scores || {
    clinical_reasoning: 75,
    communication_empathy: 70,
    surgical_semiotics: 70,
    patient_safety: 80,
    sus_time_efficiency: 75,
  };

  const axes = [
    { key: "clinical_reasoning", label: "Raciocínio Clínico", value: safeScores.clinical_reasoning },
    { key: "communication_empathy", label: "Comunicação & Empatia", value: safeScores.communication_empathy },
    { key: "surgical_semiotics", label: "Semiotécnica & Prática", value: safeScores.surgical_semiotics },
    { key: "patient_safety", label: "Segurança do Paciente", value: safeScores.patient_safety },
    { key: "sus_time_efficiency", label: "Eficiência SUS / Tempo", value: safeScores.sus_time_efficiency },
  ];

  const size = 320;
  const center = size / 2;
  const maxRadius = 100;
  const totalAxes = axes.length;

  const getCoordinates = (index: number, valuePct: number) => {
    const angle = (index * (2 * Math.PI)) / totalAxes - Math.PI / 2;
    const r = (Math.max(0, Math.min(100, valuePct)) / 100) * maxRadius;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const polygonPoints = axes
    .map((axis, i) => {
      const { x, y } = getCoordinates(i, axis.value);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="relative flex flex-col items-center justify-center p-2">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="w-full max-w-[320px] h-auto overflow-visible select-none drop-shadow-md"
      >
        {/* Anéis de Referência: 25%, 50%, 75%, 100% */}
        {[25, 50, 75, 100].map((level) => {
          const ringPoints = axes
            .map((_, i) => {
              const { x, y } = getCoordinates(i, level);
              return `${x},${y}`;
            })
            .join(" ");

          return (
            <polygon
              key={level}
              points={ringPoints}
              fill={level === 100 ? "rgba(15, 23, 42, 0.4)" : "none"}
              stroke="rgba(148, 163, 184, 0.2)"
              strokeWidth="1"
              strokeDasharray={level === 50 ? "3,3" : undefined}
            />
          );
        })}

        {/* Eixos Radiais e Rótulos */}
        {axes.map((axis, i) => {
          const end = getCoordinates(i, 100);
          const labelPos = getCoordinates(i, 122);
          return (
            <g key={axis.key}>
              <line
                x1={center}
                y1={center}
                x2={end.x}
                y2={end.y}
                stroke="rgba(148, 163, 184, 0.25)"
                strokeWidth="1"
              />
              <text
                x={labelPos.x}
                y={labelPos.y}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-slate-300 text-[9px] font-mono font-bold uppercase tracking-wider"
              >
                {axis.label} ({Math.round(axis.value)}%)
              </text>
            </g>
          );
        })}

        {/* Polígono de Desempenho do Candidato */}
        <polygon
          points={polygonPoints}
          fill="rgba(16, 185, 129, 0.25)"
          stroke="#10b981"
          strokeWidth="2.5"
          className="transition-all duration-500 ease-out"
        />

        {/* Pontos nos vértices */}
        {axes.map((axis, i) => {
          const pt = getCoordinates(i, axis.value);
          return (
            <circle
              key={axis.key}
              cx={pt.x}
              cy={pt.y}
              r="4"
              className="fill-emerald-400 stroke-slate-900 stroke-2"
            />
          );
        })}
      </svg>
    </div>
  );
}

// =========================================================================
// COMPONENTE PRINCIPAL: ESPELHO OFICIAL DE CORREÇÃO (2ª FASE)
// =========================================================================
export function StationResultMirror({
  feedback,
  stationTitle,
  institution,
  area,
  subtema,
  elapsedSeconds,
  onRetryStation,
  onGoBack,
}: StationResultMirrorProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");

  const verdictStyles = {
    "APROVADO COM DISTINÇÃO": {
      bg: "bg-emerald-500/10 border-emerald-500/40 text-emerald-300",
      badge: "bg-emerald-500 text-slate-950",
      border: "border-emerald-500/30",
    },
    "APROVADO NO LIMITE": {
      bg: "bg-sky-500/10 border-sky-500/40 text-sky-300",
      badge: "bg-sky-500 text-slate-950",
      border: "border-sky-500/30",
    },
    "REPROVADO POR TÉCNICA": {
      bg: "bg-amber-500/10 border-amber-500/40 text-amber-300",
      badge: "bg-amber-500 text-slate-950",
      border: "border-amber-500/30",
    },
    "ELIMINADO POR IATROGENIA": {
      bg: "bg-rose-500/15 border-rose-500/60 text-rose-300",
      badge: "bg-rose-600 text-white animate-pulse",
      border: "border-rose-500/50",
    },
  };

  const currentVerdict = feedback.headline_verdict || (
    feedback.approved ? "APROVADO NO LIMITE" : "REPROVADO POR TÉCNICA"
  );
  const style = verdictStyles[currentVerdict] || verdictStyles["REPROVADO POR TÉCNICA"];

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const getStatusBadge = (status: FulfillmentStatus | string) => {
    switch (status) {
      case "FULL":
      case "cumprido_total":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" /> CUMPRIDO TOTAL
          </span>
        );
      case "PARTIAL":
      case "cumprido_parcial":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            <HelpCircle className="w-3 h-3" /> PARCIAL
          </span>
        );
      case "CRITICAL_ERROR":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/25 text-rose-300 border border-rose-500/50">
            <ShieldAlert className="w-3 h-3" /> IATROGENIA
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">
            <XCircle className="w-3 h-3" /> NÃO REALIZADO
          </span>
        );
    }
  };

  const evaluatedItems: EvaluatedBaremaItem[] = feedback.evaluated_items || [];
  const filteredItems = evaluatedItems.filter((item) => {
    if (selectedCategory === "ALL") return true;
    const cat = (item.category || "").toUpperCase();
    return cat.includes(selectedCategory);
  });

  return (
    <div className="max-w-5xl mx-auto w-full p-4 md:p-6 space-y-6 text-slate-100 font-sans pb-28 animate-in fade-in duration-300">
      {/* ========================================================================= */}
      {/* 1. CABEÇALHO OFICIAL DA BANCA EXAMINADORA */}
      {/* ========================================================================= */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-6 backdrop-blur-md">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-3 py-1 rounded-md text-xs font-mono font-bold uppercase tracking-widest bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              BANCA {institution || "USP-RP"}
            </span>
            <span className="text-xs font-mono text-slate-400 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-indigo-400" />
              ESPELHO OFICIAL DE 2ª FASE
            </span>
            <span className="text-xs font-mono text-slate-500">
              • Tempo Decorrido: {formatTime(elapsedSeconds)}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">
            {stationTitle}
          </h1>
          <div className="text-xs text-slate-400 flex gap-3 font-medium">
            <span><strong>Grande Área:</strong> {area}</span>
            {subtema && <span>• <strong>Subtema:</strong> {subtema}</span>}
          </div>
        </div>

        {/* NOTA OFICIAL E VEREDITO */}
        <div className={`p-5 rounded-xl border flex flex-col items-center justify-center min-w-[220px] text-center ${style.bg} ${style.border}`}>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest opacity-80">
            Nota Oficial da Banca
          </span>
          <div className="text-4xl md:text-5xl font-black font-mono my-1 tracking-tight">
            {feedback.final_score.toFixed(1)}
            <span className="text-lg font-normal text-slate-400"> / 10.0</span>
          </div>
          <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${style.badge}`}>
            {currentVerdict}
          </span>
          <span className="text-[10px] font-mono text-slate-400 mt-1">
            Nota de Corte: {feedback.cutoff_score || 7.0}
          </span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. ALERTAS DE RED FLAGS / IATROGENIAS CLÍNICAS */}
      {/* ========================================================================= */}
      {feedback.red_flags_triggered && feedback.red_flags_triggered.length > 0 && (
        <div className="p-5 rounded-2xl border-2 border-rose-500/50 bg-rose-950/20 space-y-3 shadow-xl">
          <div className="flex items-center gap-2.5 text-rose-400 font-bold text-sm tracking-wide">
            <ShieldAlert className="w-5 h-5 animate-bounce" />
            <span>FALTAS GRAVES / IATROGENIAS IDENTIFICADAS PELA BANCA:</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            {feedback.red_flags_triggered.map((rf, idx) => (
              <div
                key={idx}
                className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-3.5 space-y-1.5"
              >
                <div className="flex items-center justify-between text-xs font-bold text-rose-300">
                  <span>{rf.title}</span>
                  <span className="font-mono text-rose-400">-{rf.score_deduction.toFixed(1)} pts</span>
                </div>
                <p className="text-xs text-slate-300 leading-snug">
                  {rf.description}
                </p>
                <div className="text-[11px] font-mono text-rose-400/90 bg-rose-500/10 px-2 py-1 rounded border border-rose-500/20">
                  ⛔ Consequência: {rf.clinical_consequence}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. RADAR DE COMPETÊNCIAS + PARECER DO PRECEPTOR CHEFE */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* COLUNA ESQUERDA: RADAR DE 5 COMPETÊNCIAS (5 Colunas) */}
        <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between shadow-xl">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Award className="w-4 h-4 text-emerald-400" /> Matriz de Competências Médicas
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Avaliação psicométrica baseada nas diretrizes de 2ª fase das bancas de residência.
            </p>
          </div>

          <div className="my-2">
            <CompetencyRadarSVG scores={feedback.competency_radar_5d} />
          </div>

          <div className="space-y-2 border-t border-slate-800 pt-3 text-xs">
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1.5">
                <HeartPulse className="w-3.5 h-3.5 text-rose-400" /> Segurança do Paciente:
              </span>
              <span className="font-mono font-bold text-slate-100">
                {feedback.competency_radar_5d?.patient_safety || 80}%
              </span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-sky-400" /> Semiotécnica & Prática:
              </span>
              <span className="font-mono font-bold text-slate-100">
                {feedback.competency_radar_5d?.surgical_semiotics || 70}%
              </span>
            </div>
          </div>
        </div>

        {/* COLUNA DIREITA: PARECER FORMATIVO DO PRECEPTOR CHEFE (7 Colunas) */}
        <div className="lg:col-span-7 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between space-y-4 shadow-xl">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-indigo-400" /> Parecer do Preceptor Chefe
            </h2>
            <p className="text-xs text-slate-300 mt-2 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              {feedback.chief_preceptor_review?.executive_summary || feedback.summary}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="bg-emerald-950/15 border border-emerald-500/20 rounded-xl p-3 space-y-1">
              <span className="font-bold text-emerald-400 uppercase text-[10px] tracking-wider block">
                ✓ Pontos Fortes na Estação
              </span>
              <ul className="space-y-1 text-slate-300 list-disc list-inside">
                {(feedback.chief_preceptor_review?.what_went_well || ["Abordagem inicial estruturada."]).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>

            <div className="bg-rose-950/15 border border-rose-500/20 rounded-xl p-3 space-y-1">
              <span className="font-bold text-rose-400 uppercase text-[10px] tracking-wider block">
                ⚠ Correções Críticas
              </span>
              <ul className="space-y-1 text-slate-300 list-disc list-inside">
                {(feedback.chief_preceptor_review?.critical_corrections || ["Revisar passos operacionais do barema."]).map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* CONDUTA CANÔNICA PADRÃO-OURO */}
          <div className="bg-slate-950 border border-indigo-500/30 rounded-xl p-4 space-y-1.5">
            <div className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
              <span>🎯 Conduta Canônica Padrão-Ouro (Gabarito da Estação)</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-mono whitespace-pre-line bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
              {feedback.chief_preceptor_review?.gold_standard_canonical_conduct ||
                "Abordagem sistemática segundo os protocolos do ATLS/ACLS com estabilização e conduta cirúrgica precisa."}
            </p>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. TABELA DO CHECKLIST BAREMA OFICIAL ITEM A ITEM */}
      {/* ========================================================================= */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-slate-800 flex flex-wrap justify-between items-center gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" /> Checklist Barema Oficial Itemizado
            </h2>
            <p className="text-xs text-slate-400">
              Auditoria de cada critério da banca com carimbo de tempo e evidência capturada
            </p>
          </div>

          <div className="flex flex-wrap gap-1.5 text-xs">
            {["ALL", "ANAMNESE", "FISICO", "PROCEDIMENTO", "DIAGNOSTICO", "CONDUTA"].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg font-mono text-[11px] font-semibold transition cursor-pointer ${
                  selectedCategory === cat
                    ? "bg-indigo-600 text-white shadow-md"
                    : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                }`}
              >
                {cat === "ALL" ? "Todos" : cat}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-950/60 text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <th className="py-3.5 px-4">Cód / Bloco</th>
                <th className="py-3.5 px-4">Critério Avaliado pela Banca</th>
                <th className="py-3.5 px-4">Evidência Auditada</th>
                <th className="py-3.5 px-4 text-center">Status</th>
                <th className="py-3.5 px-4 text-right">Pontuação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70 text-xs">
              {filteredItems.map((item, idx) => (
                <tr key={item.criterion_id || idx} className="hover:bg-slate-800/30 transition">
                  <td className="py-3.5 px-4 font-mono font-bold text-slate-300 whitespace-nowrap">
                    <div>{item.code || `ITEM-${idx + 1}`}</div>
                    <span className="text-[10px] text-indigo-400 font-normal">{item.category}</span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-200 max-w-md font-medium">
                    {item.description || item.code}
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px] max-w-sm">
                    {item.timestamp_achieved_sec !== null && item.timestamp_achieved_sec !== undefined && (
                      <span className="inline-flex items-center gap-1 text-indigo-300 mr-1.5">
                        <Clock className="w-3 h-3" />
                        {formatTime(item.timestamp_achieved_sec)}
                      </span>
                    )}
                    {item.evidence_citation || (item as unknown as { evidence?: string }).evidence || "Não identificado nas ações."}
                  </td>
                  <td className="py-3.5 px-4 text-center whitespace-nowrap">
                    {getStatusBadge(item.status)}
                  </td>
                  <td className="py-3.5 px-4 text-right font-mono font-bold whitespace-nowrap">
                    <span className={(item.awarded_score || 0) > 0 ? "text-emerald-400" : "text-slate-500"}>
                      {(item.awarded_score || (item as unknown as { score_earned?: number }).score_earned || 0).toFixed(2)}
                    </span>
                    <span className="text-slate-600"> / {(item.max_score || (item as unknown as { weight?: number }).weight || 1.0).toFixed(2)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 5. FOOTER: PRESCRIÇÃO DE REMEDIAÇÃO NO MEDQUEST & RE-TREINO */}
      {/* ========================================================================= */}
      <div className="bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/30 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-center gap-4 shadow-xl">
        <div className="space-y-1">
          <div className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
            <BookOpen className="w-4 h-4" /> Prescrição de Estudo Dirigido no MedQuest
          </div>
          <p className="text-sm text-slate-300">
            Recomendamos revisar os baralhos de flashcards e questões comentadas de{" "}
            <span className="font-semibold text-white">
              {(feedback.medquest_remediation?.recommended_flashcard_decks || [
                `${area} (${subtema || "Protocolos Beira-Leito"})`,
              ]).join(", ")}
            </span>.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {onGoBack && (
            <button
              onClick={onGoBack}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition border border-slate-700 cursor-pointer"
            >
              Voltar à Arena
            </button>
          )}
          <button
            onClick={onRetryStation}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" /> Refazer Esta Estação <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
