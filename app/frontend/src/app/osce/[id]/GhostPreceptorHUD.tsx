"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Sparkles, CheckCircle2, CircleDashed, AlertCircle, 
  ChevronDown, ChevronUp, Award, Lightbulb, 
  Eye, Zap, Filter
} from "lucide-react";
import { OsceLiveFeedback } from "@/types/api";

interface GhostPreceptorHUDProps {
  feedback: OsceLiveFeedback | null;
  mode: "blind" | "guided";
}

export function GhostPreceptorHUD({ feedback, mode }: GhostPreceptorHUDProps) {
  const [isMinimized, setIsMinimized] = useState(false);
  const [filter, setFilter] = useState<"all" | "completed" | "pending">("all");
  const [scoreAnimation, setScoreAnimation] = useState<string | null>(null);

  const prevScoreRef = useRef<number>(0);

  // Animação de comemoração quando a pontuação aumenta
  useEffect(() => {
    if (!feedback) return;
    if (feedback.current_score > prevScoreRef.current && prevScoreRef.current > 0) {
      const delta = feedback.current_score - prevScoreRef.current;
      setScoreAnimation(`+${delta.toFixed(1)} pts!`);
      const t = setTimeout(() => {
        setScoreAnimation(null);
      }, 2500);
      return () => clearTimeout(t);
    }
    prevScoreRef.current = feedback.current_score;
  }, [feedback?.current_score, feedback]);

  // Se o aluno escolheu Modo Prova Cega, o Preceptor Fantasma não dá spoiler do barema
  if (mode === "blind") {
    return (
      <div className="rounded-xl border border-border bg-card/60 p-2.5 px-3 flex items-center justify-between text-xs text-muted-foreground shadow-sm">
        <div className="flex items-center gap-2">
          <Eye className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="font-semibold text-foreground/80">Modo Prova Cega Oficial</span>
          <span className="text-[11px] hidden sm:inline">• Barema e notas ocultos durante a avaliação</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted font-mono font-medium">USP-RP / Banca Real</span>
      </div>
    );
  }

  // Se ainda não carregou o feedback
  if (!feedback) {
    return (
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 flex items-center gap-2 text-xs text-primary animate-pulse">
        <Sparkles className="w-4 h-4" />
        <span>Conectando ao Preceptor Fantasma...</span>
      </div>
    );
  }

  const items = feedback.items_status || [];
  const completedCount = items.filter(i => i.status === "cumprido_total").length;
  const partialCount = items.filter(i => i.status === "cumprido_parcial").length;
  const pendingCount = items.filter(i => i.status === "nao_cumprido").length;

  const filteredItems = items.filter(item => {
    if (filter === "completed") return item.status === "cumprido_total" || item.status === "cumprido_parcial";
    if (filter === "pending") return item.status === "nao_cumprido";
    return true;
  });

  const percentage = Math.min(100, Math.max(0, feedback.percentage || 0));

  return (
    <div className="w-full rounded-2xl border-2 border-primary/30 bg-card/95 backdrop-blur-md shadow-md overflow-hidden transition-all duration-300">
      {/* Topo do Widget / Barra Principal */}
      <div className="p-3 md:p-3.5 bg-gradient-to-r from-primary/15 via-primary/5 to-secondary/15 flex items-center justify-between border-b border-border/80">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-primary text-primary-foreground shadow-sm flex items-center justify-center">
            <span className="text-sm">👻</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-foreground text-xs md:text-sm tracking-tight flex items-center gap-1.5">
                Preceptor Fantasma
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/20 text-primary uppercase tracking-wider">
                  Treino Guiado
                </span>
              </span>
              {scoreAnimation && (
                <span className="text-xs font-black text-emerald-500 animate-bounce bg-emerald-500/20 px-2 py-0.5 rounded-full">
                  {scoreAnimation}
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground hidden sm:block">
              Barema e dicas de segurança em tempo real conforme você atua
            </p>
          </div>
        </div>

        {/* Nota Dinâmica e Botão Recolher */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="text-right">
              <div className="font-mono text-sm md:text-base font-black text-primary">
                {feedback.current_score.toFixed(1)} <span className="text-xs font-semibold text-muted-foreground">/ {feedback.max_score.toFixed(1)}</span>
              </div>
              <div className="text-[10px] font-bold text-muted-foreground">
                {percentage.toFixed(0)}% concluído
              </div>
            </div>

            <div className="w-14 sm:w-20 bg-muted rounded-full h-2.5 overflow-hidden border border-border/50">
              <div 
                className={`h-full transition-all duration-500 ${
                  percentage >= 70 ? "bg-emerald-500" : percentage >= 40 ? "bg-amber-500" : "bg-primary"
                }`}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>

          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1.5 rounded-xl border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title={isMinimized ? "Expandir barema ao vivo" : "Minimizar"}
          >
            {isMinimized ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Seção Expandida */}
      {!isMinimized && (
        <div className="p-3 md:p-4 space-y-3.5 text-xs animate-in slide-in-from-top-2 duration-200">
          {/* Alertas Proativos do Preceptor Fantasma */}
          {feedback.proactive_hints && feedback.proactive_hints.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-1.5 shadow-sm">
              <div className="flex items-center gap-1.5 font-bold text-amber-600 dark:text-amber-400 text-xs">
                <Lightbulb className="w-4 h-4 shrink-0 animate-pulse" />
                <span>Orientações Proativas do Preceptor Beira-Leito:</span>
              </div>
              <ul className="space-y-1 pl-5 list-disc text-foreground/90 font-medium text-[11px] leading-relaxed">
                {feedback.proactive_hints.map((hint, idx) => (
                  <li key={idx}>{hint}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Filtros e Métricas dos Itens do Barema */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-border/60">
            <div className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground">
              <Award className="w-3.5 h-3.5 text-primary" />
              <span>Marcos do Barema:</span>
              <span className="text-emerald-500 font-bold ml-1">{completedCount} atingidos</span>
              {partialCount > 0 && <span className="text-amber-500 font-bold ml-1">• {partialCount} parciais</span>}
              <span className="text-muted-foreground ml-1">• {pendingCount} pendentes</span>
            </div>

            {/* Botoes de Filtro */}
            <div className="flex items-center gap-1">
              <Filter className="w-3 h-3 text-muted-foreground mr-0.5" />
              <button
                onClick={() => setFilter("all")}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-bold transition-colors ${
                  filter === "all" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Todos ({items.length})
              </button>
              <button
                onClick={() => setFilter("pending")}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-bold transition-colors ${
                  filter === "pending" ? "bg-amber-500 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Pendentes ({pendingCount})
              </button>
              <button
                onClick={() => setFilter("completed")}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-bold transition-colors ${
                  filter === "completed" ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Garantidos ({completedCount + partialCount})
              </button>
            </div>
          </div>

          {/* Lista com Scroll dos Itens do Barema em Tempo Real */}
          <div className="max-h-48 overflow-y-auto pr-1 space-y-1.5 divide-y divide-border/40 border border-border/60 rounded-xl bg-background/50 p-2">
            {filteredItems.length === 0 ? (
              <div className="p-3 text-center text-muted-foreground text-[11px]">
                Nenhum item com esse filtro no momento.
              </div>
            ) : (
              filteredItems.map((item) => {
                const isTotal = item.status === "cumprido_total";
                const isPartial = item.status === "cumprido_parcial";

                return (
                  <div 
                    key={item.id}
                    className={`pt-1.5 pb-1 flex items-start justify-between gap-2.5 transition-colors ${
                      isTotal ? "text-foreground" : isPartial ? "text-foreground/90" : "text-muted-foreground"
                    }`}
                  >
                    <div className="flex items-start gap-2 min-w-0">
                      <div className="mt-0.5 shrink-0">
                        {isTotal ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        ) : isPartial ? (
                          <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                        ) : (
                          <CircleDashed className="w-3.5 h-3.5 text-muted-foreground/60" />
                        )}
                      </div>

                      <div className="min-w-0 space-y-0.5">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.2 bg-muted rounded text-muted-foreground">
                            {item.category || "Item"}
                          </span>
                          <span className={`text-[11px] font-semibold leading-snug line-clamp-2 ${
                            isTotal ? "text-foreground font-bold" : ""
                          }`}>
                            {item.title}
                          </span>
                        </div>

                        {item.matched_keywords && item.matched_keywords.length > 0 && (
                          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
                            <Zap className="w-2.5 h-2.5" />
                            <span>Gatilho ativado: {item.matched_keywords.join(", ")}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className={`font-mono text-[11px] font-bold px-1.5 py-0.5 rounded ${
                        isTotal 
                          ? "bg-emerald-500/15 text-emerald-500" 
                          : isPartial 
                          ? "bg-amber-500/15 text-amber-500" 
                          : "bg-muted text-muted-foreground"
                      }`}>
                        {item.score_earned.toFixed(1)} / {item.weight.toFixed(1)}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
