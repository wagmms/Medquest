"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  Award,
  HelpCircle,
  CheckCircle2,
  AlertCircle,
  Compass,
  ArrowUpRight,
  Minus,
  ArrowDownRight,
  ShieldCheck,
  Building2,
  Info
} from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { QuestionListItem, BatchAttemptResultItem, TriEvaluationResponse, SpecialtyCutoff } from "@/types/api";

const AVAILABLE_INSTITUTIONS = [
  { code: "ENARE", label: "ENARE (Exame Nacional de Residência)" },
  { code: "USP", label: "USP-SP (Faculdade de Medicina da USP)" },
  { code: "SUS-SP", label: "SUS-SP (Secretaria de Saúde de SP)" },
  { code: "UNIFESP", label: "UNIFESP (Escola Paulista de Medicina)" },
  { code: "UNICAMP", label: "UNICAMP (Campinas)" },
];

export interface SimuladoTriScorecardProps {
  queue: QuestionListItem[];
  resultsMap: Record<number, BatchAttemptResultItem>;
  initialInstitution?: string;
}

export const SimuladoTriScorecard: React.FC<SimuladoTriScorecardProps> = ({
  queue,
  resultsMap,
  initialInstitution = "ENARE",
}) => {
  const [selectedInst, setSelectedInst] = useState<string>(initialInstitution);
  const [triData, setTriData] = useState<TriEvaluationResponse | null>(null);
  const [showMethodology, setShowMethodology] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Prepara respostas do simulado de forma memorizada
  const responses = useMemo(() => {
    return queue.map((q) => {
      const res = resultsMap[q.id];
      return {
        question_id: q.id,
        is_correct: Boolean(res?.is_correct),
      };
    });
  }, [queue, resultsMap]);

  const hasResponses = responses.length > 0;
  const [loading, setLoading] = useState<boolean>(hasResponses);

  const handleInstitutionChange = (newInst: string) => {
    setSelectedInst(newInst);
    setLoading(true);
    setFetchError(null);
  };

  useEffect(() => {
    if (!hasResponses) {
      return;
    }

    const controller = new AbortController();

    api.questions
      .evaluateTri(
        {
          responses,
          institution_code: selectedInst,
        },
        controller.signal
      )
      .then((data) => {
        setTriData(data);
        setLoading(false);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.error("Erro ao calcular nota TRI do simulado:", err);
          setFetchError("Não foi possível carregar a avaliação TRI da banca.");
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedInst, responses, hasResponses]);

  if (!hasResponses) {
    return null;
  }

  const getStatusBadge = (status: SpecialtyCutoff["status"]) => {
    switch (status) {
      case "HIGH_PROBABILITY":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 size={13} className="shrink-0" />
            Alta Probabilidade
          </span>
        );
      case "COMPETITIVE":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <AlertCircle size={13} className="shrink-0" />
            Zona de Corte
          </span>
        );
      case "NEEDS_IMPROVEMENT":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30">
            <Minus size={13} className="shrink-0" />
            Abaixo do Corte
          </span>
        );
    }
  };

  const getDiffBadge = (diff: number) => {
    if (diff > 0) {
      return (
        <span className="inline-flex items-center text-xs font-bold text-emerald-600 dark:text-emerald-400">
          <ArrowUpRight size={14} />+{diff.toFixed(1)} pts
        </span>
      );
    }
    if (diff === 0) {
      return (
        <span className="inline-flex items-center text-xs font-bold text-muted-foreground">
          No corte exato
        </span>
      );
    }
    return (
      <span className="inline-flex items-center text-xs font-bold text-rose-600 dark:text-rose-400">
        <ArrowDownRight size={14} />{diff.toFixed(1)} pts
      </span>
    );
  };

  return (
    <div className="w-full max-w-3xl bg-card border border-border shadow-sm rounded-2xl p-6 sm:p-7 mb-8 text-left transition-all">
      {/* Header com Seletor de Banca */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-border/70">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <TrendingUp size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-black text-foreground">Scorecard TRI & Ranking Preditivo</h3>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-primary/15 text-primary uppercase tracking-wider">
                3PL Psychometrics
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Projeção calculada por Teoria de Resposta ao Item com quadratura numérica EAP.
            </p>
          </div>
        </div>

        {/* Seletor de Banca */}
        <div className="flex items-center gap-2 shrink-0">
          <Building2 size={16} className="text-muted-foreground" />
          <select
            value={selectedInst}
            onChange={(e) => handleInstitutionChange(e.target.value)}
            disabled={loading}
            className="text-xs sm:text-sm font-semibold bg-muted/60 hover:bg-muted text-foreground border border-border rounded-lg px-3 py-1.5 outline-none transition-colors cursor-pointer"
          >
            {AVAILABLE_INSTITUTIONS.map((inst) => (
              <option key={inst.code} value={inst.code}>
                {inst.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center gap-3">
          <div className="w-7 h-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-muted-foreground font-medium animate-pulse">
            Calibrando parâmetros 3PL e estimando proficiência a posteriori...
          </p>
        </div>
      ) : fetchError ? (
        <div className="py-6 text-center text-sm text-destructive font-medium">
          {fetchError}
        </div>
      ) : triData ? (
        <div className="pt-6 space-y-6">
          {/* Grid de Métricas Principais */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* 1. Nota TRI Projetada */}
            <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Nota TRI Projetada</span>
                <Award size={16} className="text-primary" />
              </div>
              <div className="my-2">
                <span className="text-3xl font-black text-foreground">
                  {triData.projected_score.toFixed(1)}
                </span>
                <span className="text-xs text-muted-foreground ml-1.5 font-semibold">/ 100</span>
              </div>
              <div className="text-[11px] text-muted-foreground">
                Acerto bruto de <strong className="text-foreground">{triData.raw_score_pct}%</strong> ({queue.filter(q => resultsMap[q.id]?.is_correct).length}/{queue.length})
              </div>
            </div>

            {/* 2. Percentil Nacional */}
            <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Percentil Nacional</span>
                <Compass size={16} className="text-emerald-500" />
              </div>
              <div className="my-2">
                <span className="text-3xl font-black text-emerald-600 dark:text-emerald-400">
                  {triData.national_percentile >= 50
                    ? `Top ${(100 - triData.national_percentile).toFixed(1)}%`
                    : `${triData.national_percentile.toFixed(1)}º Perc.`}
                </span>
              </div>
              <div className="text-[11px] text-muted-foreground">
                Acima de <strong className="text-foreground">{triData.national_percentile}%</strong> dos concorrentes simulados.
              </div>
            </div>

            {/* 3. Coerência Pedagógica */}
            <div className="bg-muted/30 border border-border rounded-xl p-4 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Coerência Pedagógica</span>
                <ShieldCheck size={16} className="text-blue-500" />
              </div>
              <div className="my-2">
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-black text-foreground">
                    {triData.pedagogical_coherence_pct.toFixed(0)}%
                  </span>
                  <span className="text-xs font-semibold text-muted-foreground">índice</span>
                </div>
              </div>
              {/* Barra de progresso de coerência */}
              <div className="w-full bg-border h-1.5 rounded-full overflow-hidden mb-1">
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-500",
                    triData.pedagogical_coherence_pct >= 85
                      ? "bg-emerald-500"
                      : triData.pedagogical_coherence_pct >= 70
                      ? "bg-amber-500"
                      : "bg-rose-500"
                  )}
                  style={{ width: `${triData.pedagogical_coherence_pct}%` }}
                />
              </div>
              <div className="text-[10px] text-muted-foreground truncate" title={triData.coherence_label}>
                {triData.pedagogical_coherence_pct >= 85
                  ? "Consistência sólida"
                  : triData.pedagogical_coherence_pct >= 70
                  ? "Distribuição balanceada"
                  : "Oscilações por chute"}
              </div>
            </div>
          </div>

          {/* Banner de Feedback de Coerência */}
          <div className="bg-muted/20 border border-border/80 rounded-xl p-3.5 flex items-start gap-3">
            <Info size={17} className="text-primary shrink-0 mt-0.5" />
            <div className="text-xs text-muted-foreground leading-relaxed">
              <strong className="text-foreground font-semibold">Diagnóstico TRI: </strong>
              {triData.coherence_label}
            </div>
          </div>

          {/* Termômetro de Corte por Especialidades Médicas */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                <span>Termômetro de Corte por Especialidade ({triData.institution_code})</span>
              </h4>
              <span className="text-[11px] text-muted-foreground">
                Baseado nos editais oficiais mais recentes
              </span>
            </div>

            <div className="border border-border rounded-xl overflow-hidden divide-y divide-border">
              {triData.specialty_cutoffs.map((spec) => (
                <div
                  key={spec.specialty}
                  className="p-3 sm:px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-semibold text-sm text-foreground">
                      {spec.specialty}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 sm:gap-6 self-end sm:self-auto">
                    <div className="text-right">
                      <div className="text-xs font-semibold text-foreground">
                        Nota de Corte: {spec.cutoff_score.toFixed(1)}
                      </div>
                      <div className="text-[11px]">
                        {getDiffBadge(spec.difference)}
                      </div>
                    </div>

                    <div className="min-w-[150px] text-right">
                      {getStatusBadge(spec.status)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Acordeão de Metodologia TRI */}
          <div className="pt-2">
            <button
              onClick={() => setShowMethodology(!showMethodology)}
              className="text-xs text-muted-foreground hover:text-foreground font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <HelpCircle size={14} />
              {showMethodology ? "Ocultar detalhes da metodologia TRI" : "Como a TRI calcula sua nota e evita chutes?"}
            </button>

            {showMethodology && (
              <div className="mt-3 bg-muted/20 border border-border rounded-xl p-4 text-xs text-muted-foreground space-y-2 leading-relaxed animate-in fade-in-50">
                <p>
                  <strong className="text-foreground">Modelo Logístico 3PL:</strong> Diferente de uma prova com pontuação linear bruta, a TRI avalia três parâmetros essenciais em cada questão médica:
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>Parâmetro a (Discriminação):</strong> Mede o poder da questão de diferenciar candidatos de alto e baixo rendimento.</li>
                  <li><strong>Parâmetro b (Dificuldade):</strong> Ponto da escala de proficiência onde a probabilidade de acerto é de 50%.</li>
                  <li><strong>Parâmetro c (Acerto ao acaso / Chute):</strong> Probabilidade de um candidato sem domínio acertar a questão por eliminação ou sorte.</li>
                </ul>
                <p>
                  <strong className="text-foreground">Coerência Pedagógica:</strong> Candidatos que erram questões fáceis e acertam apenas questões muito difíceis têm probabilidade elevada de acerto por chute, reduzindo o valor agregado desses pontos e alinhando sua projeção à realidade dos grandes concursos como ENARE e USP.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
};
