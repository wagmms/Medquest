"use client";

import React, { useState, useEffect } from "react";
import { SimuladoSessionItem } from "@/types/api";
import { api } from "@/lib/api";
import { History, Clock, Trash2, RotateCcw } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

export const SimuladoHistoryView: React.FC = () => {
  const [sessions, setSessions] = useState<SimuladoSessionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchSessions = async () => {
    setIsLoading(true);
    try {
      const res = await api.questions.getSimuladoSessions();
      setSessions(res.sessions || []);
    } catch {
      // Falha silenciosa ou offline
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    api.questions
      .getSimuladoSessions()
      .then((res) => {
        if (isMounted) setSessions(res.sessions || []);
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleDeleteSession = async (clientSessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Deseja realmente remover este simulado do seu histórico?")) return;
    setDeletingId(clientSessionId);
    try {
      await api.questions.deleteSimuladoSession(clientSessionId);
      setSessions((prev) => prev.filter((s) => s.client_session_id !== clientSessionId));
      toast.success("Registro de simulado removido.");
    } catch {
      toast.error("Erro ao remover simulado.");
    } finally {
      setDeletingId(null);
    }
  };

  const formatSeconds = (sec: number) => {
    const hours = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}min`;
    }
    return `${mins} min`;
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-foreground">Histórico de Simulados Realizados</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Acompanhe o seu desempenho, tempo gasto e consistência ao longo do tempo.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchSessions}
          disabled={isLoading}
          className="self-start sm:self-auto px-3.5 py-2 rounded-xl border border-border bg-muted/40 hover:bg-muted text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
        >
          <RotateCcw size={14} className={clsx(isLoading && "animate-spin")} />
          Atualizar
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-2xl bg-muted/30 border border-border animate-pulse" />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="bg-card border border-border rounded-3xl p-12 text-center flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 text-muted-foreground flex items-center justify-center">
            <History size={32} />
          </div>
          <div className="space-y-1 max-w-md">
            <h3 className="text-base font-bold text-foreground">Nenhum simulado finalizado ainda</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Conclua uma Prova Oficial ou um Sprint de Treino para registrar seu histórico e acompanhar sua evolução na Teoria de Resposta ao Item (TRI).
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {sessions.map((session) => {
            const acc = session.accuracy_percent || 0;
            const isExcellent = acc >= 80;
            const isGood = acc >= 70;

            const instLabel = Array.isArray(session.filters?.institutions) && session.filters.institutions.length > 0
              ? session.filters.institutions.join(", ")
              : "Simulado Geral";

            const yearLabel = Array.isArray(session.filters?.years) && session.filters.years.length > 0
              ? session.filters.years.join(", ")
              : "";

            return (
              <div
                key={session.client_session_id}
                className="bg-card border border-border hover:border-primary/40 rounded-2xl p-5 sm:p-6 shadow-xs hover:shadow-sm transition-all flex flex-col gap-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={clsx(
                        "w-12 h-12 rounded-xl flex items-center justify-center font-bold text-sm shrink-0",
                        isExcellent
                          ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                          : isGood
                          ? "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30"
                          : "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                      )}
                    >
                      {acc.toFixed(0)}%
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-base font-bold text-foreground">
                          {instLabel} {yearLabel && `· ${yearLabel}`}
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(session.completed_at)} · {session.total_questions} questões
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-auto">
                    <div className="text-right">
                      <p className="text-xs font-bold text-foreground">
                        {session.correct_count} de {session.total_questions} acertos
                      </p>
                      <p className="text-[11px] text-muted-foreground flex items-center gap-1 justify-end">
                        <Clock size={12} /> {formatSeconds(session.elapsed_seconds)}
                      </p>
                    </div>

                    <button
                      type="button"
                      title="Excluir este simulado do histórico"
                      onClick={(e) => handleDeleteSession(session.client_session_id, e)}
                      disabled={deletingId === session.client_session_id}
                      className="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* Accuracy progress bar */}
                <div className="w-full bg-muted h-2 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "h-full transition-all duration-500",
                      isExcellent ? "bg-emerald-500" : isGood ? "bg-blue-500" : "bg-amber-500"
                    )}
                    style={{ width: `${Math.min(100, Math.max(0, acc))}%` }}
                  />
                </div>

                {/* Area Breakdown Pills */}
                {session.area_results && session.area_results.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-2 border-t border-border/60">
                    {session.area_results.map((areaItem, idx) => {
                      const areaAcc = areaItem.total > 0 ? (areaItem.correct / areaItem.total) * 100 : 0;
                      return (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted/40 border border-border/60 text-[11px] font-medium text-muted-foreground"
                        >
                          <span className="font-semibold text-foreground">{areaItem.area}:</span>
                          <span
                            className={clsx(
                              "font-bold",
                              areaAcc >= 75 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
                            )}
                          >
                            {areaItem.correct}/{areaItem.total} ({areaAcc.toFixed(0)}%)
                          </span>
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
