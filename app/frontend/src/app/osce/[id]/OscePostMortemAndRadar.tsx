"use client";

import React, { useState } from "react";
import { 
  Clock, Award, CheckCircle2, ShieldAlert,
  Sparkles, Stethoscope, Activity, FileText, Pill, 
  Zap, Hourglass, Target, ChevronRight, Filter
} from "lucide-react";
import { OsceTimelinePostMortem, OsceCompetencyRadar } from "@/types/api";

interface OscePostMortemAndRadarProps {
  timeline?: OsceTimelinePostMortem;
  radar?: OsceCompetencyRadar;
}

export function OscePostMortemAndRadar({ timeline, radar }: OscePostMortemAndRadarProps) {
  const [activeTab, setActiveTab] = useState<"radar" | "timeline">("radar");
  const [timelineFilter, setTimelineFilter] = useState<"all" | "gaps" | "timely">("all");

  if (!timeline && !radar) return null;

  // Renderizador do Gráfico Radar SVG (Spider Chart)
  const renderSpiderChart = () => {
    if (!radar || !radar.dimensions || radar.dimensions.length === 0) return null;

    const size = 300;
    const cx = size / 2;
    const cy = size / 2;
    const radius = 105;
    const dimensions = radar.dimensions;
    const totalAxes = dimensions.length;

    // Converte polar para cartesiano
    const getCoordinates = (index: number, valuePct: number, maxRadius = radius) => {
      const angle = (index * (2 * Math.PI) / totalAxes) - (Math.PI / 2);
      const r = (valuePct / 100) * maxRadius;
      return {
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle)
      };
    };

    // Polígonos de Nível (25%, 50%, 75%, 100%)
    const levelRings = [25, 50, 75, 100].map((pct) => {
      const points = dimensions.map((_, i) => {
        const { x, y } = getCoordinates(i, pct);
        return `${x},${y}`;
      }).join(" ");
      return { pct, points };
    });

    // Polígono de Dados do Candidato
    const dataPoints = dimensions.map((dim, i) => {
      const { x, y } = getCoordinates(i, dim.percentage);
      return `${x},${y}`;
    }).join(" ");

    return (
      <div className="relative flex flex-col items-center justify-center p-2">
        <svg 
          viewBox={`0 0 ${size} ${size}`} 
          className="w-full max-w-[320px] h-auto overflow-visible select-none drop-shadow-sm"
        >
          {/* Anéis de Nível de Referência */}
          {levelRings.map((ring) => (
            <polygon
              key={ring.pct}
              points={ring.points}
              fill={ring.pct === 100 ? "currentColor" : "none"}
              className={`${
                ring.pct === 100 
                  ? "text-muted/10 stroke-border/70" 
                  : "stroke-border/40"
              }`}
              strokeWidth="1"
              strokeDasharray={ring.pct === 50 ? "3 3" : undefined}
            />
          ))}

          {/* Eixos Radiais */}
          {dimensions.map((_, i) => {
            const { x, y } = getCoordinates(i, 100);
            return (
              <line
                key={i}
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                className="stroke-border/60"
                strokeWidth="1"
              />
            );
          })}

          {/* Polígono de Desempenho do Candidato */}
          <polygon
            points={dataPoints}
            className="fill-emerald-500/25 stroke-emerald-500"
            strokeWidth="2.5"
            strokeLinejoin="round"
          />

          {/* Marcadores e Vértices */}
          {dimensions.map((dim, i) => {
            const { x, y } = getCoordinates(i, dim.percentage);
            const isHigh = dim.percentage >= 70;
            return (
              <g key={i}>
                <circle
                  cx={x}
                  cy={y}
                  r="4"
                  className={isHigh ? "fill-emerald-500 stroke-background" : "fill-amber-500 stroke-background"}
                  strokeWidth="2"
                />
              </g>
            );
          })}

          {/* Rótulos Externos das Competências */}
          {dimensions.map((dim, i) => {
            const { x, y } = getCoordinates(i, 118);
            const isTop = y < cy - 20;
            const isBottom = y > cy + 20;
            const isRight = x > cx + 20;
            const isLeft = x < cx - 20;

            const textAnchor = isRight ? "start" : isLeft ? "end" : "middle";
            const dy = isTop ? "-0.4em" : isBottom ? "1em" : "0.3em";

            return (
              <text
                key={i}
                x={x}
                y={y}
                dy={dy}
                textAnchor={textAnchor}
                className="text-[9px] font-bold fill-foreground/90 uppercase tracking-tighter select-none"
              >
                {dim.name.split(" ")[0]} ({dim.percentage.toFixed(0)}%)
              </text>
            );
          })}
        </svg>

        <div className="flex items-center gap-4 text-[11px] text-muted-foreground pt-2">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
            Aproveitamento no Barema
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-border inline-block"></span>
            Metas da Banca (100%)
          </span>
        </div>
      </div>
    );
  };

  // Helper de ícone por tipo de evento na Linha do Tempo
  const getEventIcon = (type: string) => {
    switch (type) {
      case "vitals": return <Activity className="w-4 h-4 text-primary" />;
      case "physical_exam": return <Stethoscope className="w-4 h-4 text-emerald-500" />;
      case "lab_imaging": return <FileText className="w-4 h-4 text-sky-500" />;
      case "prescription": return <Pill className="w-4 h-4 text-violet-500" />;
      case "procedure": return <Zap className="w-4 h-4 text-amber-500" />;
      case "conduct": return <Target className="w-4 h-4 text-rose-500" />;
      case "hesitacao": return <Hourglass className="w-4 h-4 text-amber-500" />;
      case "omissao": return <ShieldAlert className="w-4 h-4 text-rose-500" />;
      default: return <Clock className="w-4 h-4 text-muted-foreground" />;
    }
  };

  // Filtragem dos eventos da Linha do Tempo
  const filteredEvents = (timeline?.events || []).filter((e) => {
    if (timelineFilter === "gaps") return e.status === "delayed" || e.status === "critical_gap";
    if (timelineFilter === "timely") return e.status === "timely";
    return true;
  });

  return (
    <div className="w-full rounded-2xl border-2 border-border bg-card overflow-hidden shadow-sm space-y-0">
      {/* Barra de Seleção de Abas Superiores */}
      <div className="flex items-center justify-between p-2 md:p-3 bg-muted/40 border-b border-border">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-background border border-border">
          <button
            type="button"
            onClick={() => setActiveTab("radar")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "radar"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            <span>Radar de Competências</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("timeline")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "timeline"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Timeline Post-Mortem</span>
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-[11px] text-muted-foreground">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Análise Preditiva de 2ª Fase Presencial</span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* ABA 1: RADAR DE COMPETÊNCIAS CLÍNICAS */}
      {/* ========================================================================= */}
      {activeTab === "radar" && radar && (
        <div className="p-4 md:p-6 space-y-6 animate-in fade-in duration-200">
          {/* Header & Métricas de Competência */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Card 1: Média Geral das 6 Dimensões */}
            <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 space-y-1.5">
              <span className="text-[10px] font-extrabold uppercase text-primary tracking-wider">
                Aproveitamento Multidimensional
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-foreground">
                  {radar.overall_average.toFixed(1)}%
                </span>
                <span className="text-xs text-muted-foreground font-semibold">
                  nas 6 competências
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-snug">
                Equilíbrio clínico entre anamnese, habilidades práticas e farmacologia.
              </p>
            </div>

            {/* Card 2: Maiores Forças */}
            <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 space-y-1.5">
              <span className="text-[10px] font-extrabold uppercase text-emerald-600 dark:text-emerald-400 tracking-wider flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                Maiores Forças na Estação
              </span>
              <div className="space-y-1">
                {radar.strengths.map((str, i) => (
                  <div key={i} className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                    <span>{str}</span>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">Pontos fortes a manter na rotina.</p>
            </div>

            {/* Card 3: Oportunidades de Refinamento */}
            <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 space-y-1.5">
              <span className="text-[10px] font-extrabold uppercase text-amber-600 dark:text-amber-400 tracking-wider flex items-center gap-1">
                <Target className="w-3 h-3" />
                Foco de Atenção para a 2ª Fase
              </span>
              <div className="space-y-1">
                {radar.weaknesses.length > 0 ? (
                  radar.weaknesses.map((w, i) => (
                    <div key={i} className="text-xs font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                      <span>{w}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-xs font-bold text-emerald-600">Nenhum ponto crítico identificado!</div>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground">Priorize essas áreas na revisão espaçada.</p>
            </div>
          </div>

          {/* Gráfico Spider + Lista das 6 Dimensões */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Esquerda: Spider Chart SVG (5 cols) */}
            <div className="lg:col-span-5 flex flex-col items-center justify-center p-3 rounded-2xl bg-muted/20 border border-border/80">
              {renderSpiderChart()}
            </div>

            {/* Direita: Breakdown das 6 Competências (7 cols) */}
            <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {radar.dimensions.map((dim) => {
                const isExc = dim.percentage >= 80;
                const isSat = dim.percentage >= 60;
                return (
                  <div 
                    key={dim.key} 
                    className="p-3 rounded-xl border border-border bg-card/80 space-y-1.5 hover:border-primary/40 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="text-xs font-bold text-foreground line-clamp-1">
                        {dim.name}
                      </span>
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded-md ${
                        isExc 
                          ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                          : isSat 
                          ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                          : "bg-rose-500/15 text-rose-500"
                      }`}>
                        {dim.percentage.toFixed(0)}%
                      </span>
                    </div>

                    <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                      <div 
                        className={`h-full ${
                          isExc ? "bg-emerald-500" : isSat ? "bg-amber-500" : "bg-rose-500"
                        }`}
                        style={{ width: `${dim.percentage}%` }}
                      />
                    </div>

                    <p className="text-[10px] text-muted-foreground line-clamp-2 leading-relaxed">
                      {dim.feedback}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ABA 2: LINHA DO TEMPO BEIRA-LEITO ("TIMELINE POST-MORTEM") */}
      {/* ========================================================================= */}
      {activeTab === "timeline" && timeline && (
        <div className="p-4 md:p-6 space-y-6 animate-in fade-in duration-200">
          {/* Header de Ritmo & Metas Temporais */}
          <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-extrabold uppercase text-primary tracking-wider">
                  Ritmo Beira-Leito da Prova
                </span>
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                  {timeline.summary.pace_label}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Reconstituição segundo a segundo das suas decisões, intervenções e períodos de hesitação.
              </p>
            </div>

            {/* Badges de Contagem */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {timeline.summary.timely_count} Oportunos
              </span>
              {timeline.summary.delayed_count > 0 && (
                <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {timeline.summary.delayed_count} Atrasados
                </span>
              )}
              {timeline.summary.critical_gaps_count > 0 && (
                <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-500 flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  {timeline.summary.critical_gaps_count} Gaps Críticos
                </span>
              )}
            </div>
          </div>

          {/* Filtros da Timeline */}
          <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
            <span className="text-xs font-bold text-muted-foreground">
              Histórico Cronológico ({filteredEvents.length} eventos registrados):
            </span>

            <div className="flex items-center gap-1">
              <Filter className="w-3 h-3 text-muted-foreground mr-1" />
              <button
                onClick={() => setTimelineFilter("all")}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                  timelineFilter === "all" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Todos
              </button>
              <button
                onClick={() => setTimelineFilter("gaps")}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                  timelineFilter === "gaps" ? "bg-rose-500 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Apenas Atrasos & Falhas
              </button>
              <button
                onClick={() => setTimelineFilter("timely")}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                  timelineFilter === "timely" ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Apenas Oportunos
              </button>
            </div>
          </div>

          {/* Trilha Cronológica Vertical */}
          <div className="relative pl-6 sm:pl-8 space-y-4 before:content-[''] before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
            {filteredEvents.map((evt, idx) => {
              const isTimely = evt.status === "timely";
              const isDelayed = evt.status === "delayed";
              const isGap = evt.status === "critical_gap";

              return (
                <div key={idx} className="relative group">
                  {/* Nó / Círculo na Linha */}
                  <div className={`absolute -left-6 sm:-left-8 top-1.5 w-6 h-6 rounded-full flex items-center justify-center border-2 bg-background transition-transform group-hover:scale-110 ${
                    isTimely 
                      ? "border-emerald-500 text-emerald-500" 
                      : isGap 
                      ? "border-rose-500 text-rose-500 animate-pulse" 
                      : isDelayed 
                      ? "border-amber-500 text-amber-500" 
                      : "border-border text-muted-foreground"
                  }`}>
                    {getEventIcon(evt.event_type)}
                  </div>

                  {/* Card do Evento */}
                  <div className={`p-3.5 rounded-xl border text-xs space-y-1.5 transition-all ${
                    isGap 
                      ? "border-rose-500/30 bg-rose-500/5 shadow-sm" 
                      : isDelayed 
                      ? "border-amber-500/30 bg-amber-500/5" 
                      : isTimely 
                      ? "border-emerald-500/30 bg-card hover:bg-emerald-500/5" 
                      : "border-border bg-card hover:bg-muted/40"
                  }`}>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-black px-2 py-0.5 rounded bg-muted text-foreground border border-border">
                          {evt.time_formatted}
                        </span>
                        <span className="font-bold text-foreground text-xs md:text-sm">
                          {evt.title}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-black px-2 py-0.5 rounded ${
                          isTimely 
                            ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400" 
                            : isGap 
                            ? "bg-rose-500/20 text-rose-600 dark:text-rose-400" 
                            : isDelayed 
                            ? "bg-amber-500/20 text-amber-600 dark:text-amber-400" 
                            : "bg-muted text-muted-foreground"
                        }`}>
                          {evt.score_impact}
                        </span>
                      </div>
                    </div>

                    <p className="text-foreground/90 font-medium text-[11px] leading-relaxed">
                      {evt.description}
                    </p>

                    <div className="pt-1 text-[11px] text-muted-foreground flex items-center gap-1.5 italic border-t border-border/50">
                      <ChevronRight className="w-3 h-3 text-primary shrink-0" />
                      <span>{evt.feedback}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
