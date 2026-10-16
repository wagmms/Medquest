"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Stethoscope, Clock, Award, AlertCircle, 
  CheckCircle2, ChevronRight, Play, Sparkles, Filter,
  Zap, Brain, Loader2, Target, Sliders
} from "lucide-react";
import { OsceStation } from "@/types/api";
import { api } from "@/lib/api";

interface OsceHubClientProps {
  initialStations: OsceStation[];
}

const INSTITUTIONS = [
  "Todas as Bancas",
  "USP-RP",
  "UNICAMP",
  "UNIFESP",
  "Einstein",
  "Revalida INEP",
  "SCMSP"
];

const AREAS = [
  "Todas as Áreas",
  "Clínica Médica",
  "Cirurgia Geral",
  "Pediatria",
  "Ginecologia e Obstetrícia",
  "Medicina Preventiva"
];

export function OsceHubClient({ initialStations }: OsceHubClientProps) {
  const router = useRouter();
  const [stations, setStations] = useState<OsceStation[]>(initialStations);
  const [selectedInst, setSelectedInst] = useState<string>("Todas as Bancas");
  const [selectedArea, setSelectedArea] = useState<string>("Todas as Áreas");
  const [activeTab, setActiveTab] = useState<"avulso" | "circuito">("avulso");

  // Estados do Motor IA de Estações Inéditas Infinitas (FMRP-USP)
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatingStep, setGeneratingStep] = useState<string>("");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [showCustomGen, setShowCustomGen] = useState(false);
  const [selectedGenArea, setSelectedGenArea] = useState<string>("Clínica Médica");
  const [selectedGenDifficulty, setSelectedGenDifficulty] = useState<"easy" | "medium" | "hard">("hard");

  const filteredStations = useMemo(() => {
    return stations.filter((st) => {
      const matchInst = selectedInst === "Todas as Bancas" || st.institution === selectedInst;
      const matchArea = selectedArea === "Todas as Áreas" || st.area === selectedArea;
      return matchInst && matchArea;
    });
  }, [stations, selectedInst, selectedArea]);

  // Estatísticas gerais
  const stats = useMemo(() => {
    const completed = stations.filter(s => s.completed_attempts > 0);
    const avgScore = completed.length > 0 
      ? completed.reduce((acc, s) => acc + (s.best_score || 0), 0) / completed.length 
      : 0;
    return {
      total: stations.length,
      completed: completed.length,
      avgScore: avgScore.toFixed(1)
    };
  }, [stations]);

  const [isStartingCircuit, setIsStartingCircuit] = useState(false);

  // Iniciar circuito de 5 estações
  const handleStartCircuit = async () => {
    if (isStartingCircuit) return;
    setIsStartingCircuit(true);
    try {
      const targetInst = selectedInst !== "Todas as Bancas" ? selectedInst : "USP-RP";
      const plan = await api.osce.getCircuitPlan(targetInst);
      if (plan?.stations && plan.stations.length > 0) {
        const first = plan.stations[0];
        router.push(`/osce/${first.station_id}?circuit=${plan.circuit_id}&step=1`);
      } else {
        const first = stations[0];
        if (first) {
          const circuitId = `circuit-${Date.now()}`;
          router.push(`/osce/${first.id}?circuit=${circuitId}&step=1`);
        }
      }
    } catch (err) {
      console.error("Falha ao iniciar circuito:", err);
      const first = stations[0];
      if (first) {
        const circuitId = `circuit-${Date.now()}`;
        router.push(`/osce/${first.id}?circuit=${circuitId}&step=1`);
      }
    } finally {
      setIsStartingCircuit(false);
    }
  };

  // Motor de Geração Inédita FMRP-USP
  const handleGenerateStation = async (adaptative: boolean, overrideArea?: string) => {
    if (isGenerating) return;
    setIsGenerating(true);
    setGenerationError(null);
    setGeneratingStep("Analisando histórico de raciocínio clínico e pontos cegos...");

    const t1 = setTimeout(() => {
      setGeneratingStep("Sintetizando caso clínico nos moldes do HC da FMRP-USP...");
    }, 900);

    const t2 = setTimeout(() => {
      setGeneratingStep("Parametrizando persona de paciente, gasometrias e laudos...");
    }, 1800);

    const t3 = setTimeout(() => {
      setGeneratingStep("Calibrando barema oficial FMRP-USP e critérios de corte...");
    }, 2700);

    try {
      const targetArea = overrideArea || (adaptative ? undefined : selectedGenArea);
      const res = await api.osce.generateStation({
        adaptative,
        area: targetArea,
        difficulty: selectedGenDifficulty
      });

      if (res.success && res.station_id) {
        setGeneratingStep("Estação sintetizada com sucesso! Abrindo a Arena...");
        // Adiciona otimisticamente a nova estação na lista
        const newStationSummary: OsceStation = {
          id: res.station_id,
          code: res.code,
          title: res.title,
          area: res.area,
          subtema: res.subtema,
          institution: res.institution,
          year: 2026,
          difficulty: res.difficulty,
          duration_seconds: 480,
          scenario_door_markdown: "",
          completed_attempts: 0,
          best_score: null
        };
        setStations(prev => [newStationSummary, ...prev]);

        setTimeout(() => {
          router.push(`/osce/${res.station_id}`);
        }, 400);
      } else {
        throw new Error(res.message || "Erro ao sintetizar estação inédita.");
      }
    } catch (err: unknown) {
      console.error("Falha ao gerar estação FMRP-USP:", err);
      setGenerationError(err instanceof Error ? err.message : "Não foi possível gerar a estação agora.");
      setIsGenerating(false);
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    }
  };

  return (
    <div className="max-w-7xl mx-auto w-full space-y-6 animate-in fade-in duration-300">
      {/* Header com Branding Clínico de 2ª Fase */}
      <div className="bg-surface border border-line-subtle rounded-sm p-6 md:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-xs bg-accent/10 text-accent text-xs font-mono-lab uppercase font-semibold border border-accent/20">
              <Stethoscope className="w-3.5 h-3.5" />
              <span>Simulador Oficial de 2ª Fase Prática (OSCE)</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-ink-primary font-sans">
              Arena OSCE & Beira-Leito
            </h1>
            <p className="text-ink-secondary text-sm max-w-2xl leading-relaxed">
              Treinamento de estações clínicas com paciente virtual falante, estetoscópio interativo, 
              exames complementares reais e <strong>Espelho de Correção Oficial</strong> das bancas 
              com 2ª fase presencial (<span className="text-ink-primary font-medium">UNICAMP, UNIFESP, Einstein, Revalida INEP, SCMSP e USP-RP</span>).
            </p>
          </div>

          {/* Métricas Clínicas */}
          <div className="grid grid-cols-3 gap-2 shrink-0 bg-canvas p-3 rounded-sm border border-line-subtle">
            <div className="text-center px-3 py-1">
              <div className="text-xl md:text-2xl font-bold font-mono-lab tabular-nums text-ink-primary">{stats.total}</div>
              <div className="text-[11px] font-mono-lab text-ink-tertiary uppercase">Estações</div>
            </div>
            <div className="text-center px-3 py-1 border-x border-line-subtle">
              <div className="text-xl md:text-2xl font-bold font-mono-lab tabular-nums text-accent">{stats.completed}</div>
              <div className="text-[11px] font-mono-lab text-ink-tertiary uppercase">Feitas</div>
            </div>
            <div className="text-center px-3 py-1">
              <div className="text-xl md:text-2xl font-bold font-mono-lab tabular-nums text-emerald-500">
                {stats.completed > 0 ? stats.avgScore : "—"}
              </div>
              <div className="text-[11px] font-mono-lab text-ink-tertiary uppercase">Média</div>
            </div>
          </div>
        </div>

        {/* Tab Selector: Treino Avulso vs Circuito Oficial */}
        <div className="flex items-center gap-2 mt-6 border-t border-line-subtle pt-5">
          <button
            onClick={() => setActiveTab("avulso")}
            className={`px-3.5 py-1.5 rounded-xs text-xs font-mono-lab font-semibold transition-colors cursor-pointer ${
              activeTab === "avulso"
                ? "bg-ink-primary text-canvas shadow-xs"
                : "bg-canvas text-ink-secondary hover:text-ink-primary border border-line-subtle"
            }`}
          >
            Treino Avulso por Estação
          </button>
          <button
            onClick={() => setActiveTab("circuito")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs text-xs font-mono-lab font-semibold transition-colors cursor-pointer ${
              activeTab === "circuito"
                ? "bg-ink-primary text-canvas shadow-xs"
                : "bg-canvas text-ink-secondary hover:text-ink-primary border border-line-subtle"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Circuito de Prova (5 Estações)</span>
          </button>
        </div>
      </div>

      {/* Seção Circuito de Prova */}
      {activeTab === "circuito" && (
        <div className="rounded-sm border border-amber-500/30 bg-surface p-5 md:p-6 space-y-4 shadow-xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-amber-500/10 text-amber-500 text-xs font-mono-lab uppercase font-bold border border-amber-500/20">
                <Award className="w-3.5 h-3.5" />
                <span>Simulação do Dia da Prova Presencial</span>
              </div>
              <h2 className="text-xl font-bold text-ink-primary">Circuito de Rotação Completo</h2>
              <p className="text-ink-secondary text-xs md:text-sm max-w-2xl leading-relaxed">
                Você enfrentará 5 estações seguidas (Clínica Médica, Cirurgia Geral, Pediatria, Ginecologia/Obstetrícia e Preventiva). 
                Ao fim de cada 8 minutos, o sino toca e você roda para a próxima sala. Ao final, receba o barema global da sua 2ª Fase (0 a 50 pontos).
              </p>
            </div>
            <button
              onClick={handleStartCircuit}
              disabled={isStartingCircuit}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xs font-mono-lab text-xs font-bold bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white shadow-xs transition-colors shrink-0 cursor-pointer"
            >
              {isStartingCircuit ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{isStartingCircuit ? "Montando Circuito Oficial..." : "Entrar no Circuito Oficial"}</span>
            </button>
          </div>
        </div>
      )}

      {/* MÓDULO: MOTOR DE ESTAÇÕES INÉDITAS INFINITAS VIA IA DA FMRP-USP */}
      <div className="rounded-sm border border-accent/30 bg-surface p-5 md:p-7 relative overflow-hidden shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-accent/10 text-accent text-xs font-mono-lab uppercase font-bold border border-accent/20">
              <Zap className="w-3 h-3 text-amber-400" />
              <span>Motor de Estações Inéditas Infinitas • IA FMRP-USP</span>
            </div>
            <h2 className="text-xl md:text-2xl font-bold text-ink-primary tracking-tight font-sans">
              Gerador de Casos Inéditos da USP Ribeirão Preto
            </h2>
            <p className="text-xs md:text-sm text-ink-secondary leading-relaxed">
              Algoritmo adaptativo calibrado com os protocolos beira-leito dos hospitais da FMRP-USP (<span className="text-ink-primary font-medium">HC-UE, HC-Criança, Hospital Mater e CSE Sumarezinho</span>).
              O motor analisa seus erros e sintetiza estações focadas nas suas fraquezas clínicas com pacientes, gasometrias, ECGs e baremas oficiais.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row lg:flex-col gap-2.5 shrink-0">
            {/* Botão Adaptativo de 1 Clique */}
            <button
              onClick={() => handleGenerateStation(true)}
              disabled={isGenerating}
              className="inline-flex items-center justify-center gap-2.5 px-5 py-3 rounded-xs font-mono-lab text-xs font-bold bg-accent hover:opacity-90 text-white shadow-xs transition-opacity disabled:opacity-60 cursor-pointer"
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Brain className="w-4 h-4 text-amber-300" />
              )}
              <div className="text-left">
                <div className="font-bold leading-tight">
                  {isGenerating ? "Sintetizando Estação..." : "Gerar Caso Adaptativo (1 Clique)"}
                </div>
                <div className="text-[10px] font-normal opacity-80">
                  Prioriza minhas fragilidades clínicas
                </div>
              </div>
            </button>

            {/* Botão para Configurar Área Específica */}
            <button
              onClick={() => setShowCustomGen(!showCustomGen)}
              disabled={isGenerating}
              className="inline-flex items-center justify-center gap-2 px-3.5 py-2 rounded-xs text-xs font-mono-lab font-medium bg-canvas hover:bg-surface text-ink-secondary hover:text-ink-primary border border-line-subtle transition-colors cursor-pointer"
            >
              <Sliders className="w-3.5 h-3.5 text-accent" />
              <span>{showCustomGen ? "Recolher Opções" : "Sintetizar por Área da FMRP-USP"}</span>
            </button>
          </div>
        </div>

        {/* Painel Expansível de Geração por Área */}
        {showCustomGen && (
          <div className="mt-5 pt-5 border-t border-line-subtle grid grid-cols-1 md:grid-cols-3 gap-3 animate-in fade-in duration-200">
            <div className="space-y-1">
              <label className="text-[11px] font-mono-lab font-bold text-ink-tertiary uppercase tracking-wider">
                Especialidade Clínica
              </label>
              <select
                value={selectedGenArea}
                onChange={(e) => setSelectedGenArea(e.target.value)}
                disabled={isGenerating}
                className="w-full bg-canvas border border-line-subtle rounded-xs px-3 py-2 text-xs font-mono-lab text-ink-primary focus:outline-none focus:border-accent"
              >
                <option value="Clínica Médica">Clínica Médica (HC-UE / Emergência)</option>
                <option value="Cirurgia Geral">Cirurgia Geral (HC-UE / Trauma)</option>
                <option value="Pediatria">Pediatria (HC-Criança / Sala Vermelha)</option>
                <option value="Ginecologia e Obstetrícia">Ginecologia & Obstetrícia (Hospital Mater)</option>
                <option value="Medicina Preventiva">Medicina Preventiva (CSE Sumarezinho)</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-mono-lab font-bold text-ink-tertiary uppercase tracking-wider">
                Nível de Dificuldade
              </label>
              <select
                value={selectedGenDifficulty}
                onChange={(e) => setSelectedGenDifficulty(e.target.value as "easy" | "medium" | "hard")}
                disabled={isGenerating}
                className="w-full bg-canvas border border-line-subtle rounded-xs px-3 py-2 text-xs font-mono-lab text-ink-primary focus:outline-none focus:border-accent"
              >
                <option value="hard">R1 Alta Complexidade (Padrão Prova FMRP-USP)</option>
                <option value="medium">R1 Moderado (Treinamento Clínico)</option>
                <option value="easy">Internato Guiado (Introdução)</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={() => handleGenerateStation(false)}
                disabled={isGenerating}
                className="w-full py-2 px-4 rounded-xs text-xs font-mono-lab font-bold bg-accent hover:opacity-90 text-white transition-opacity shadow-xs flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Target className="w-3.5 h-3.5" />
                <span>Gerar Estação Desta Área</span>
              </button>
            </div>
          </div>
        )}

        {/* Feedback Ativo de Síntese Clínica */}
        {isGenerating && (
          <div className="mt-4 p-3 rounded-xs bg-canvas border border-accent/40 flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />
            <div className="space-y-0.5 font-mono-lab">
              <div className="text-[11px] font-bold text-ink-tertiary uppercase">
                Processador de Provas FMRP-USP em execução:
              </div>
              <div className="text-xs text-ink-primary font-medium">
                {generatingStep}
              </div>
            </div>
          </div>
        )}

        {/* Erro de Geração */}
        {generationError && (
          <div className="mt-4 p-3 rounded-xs bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-xs font-mono-lab text-rose-500">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{generationError}</span>
          </div>
        )}
      </div>

      {/* Banner de Destaque FMRP-USP */}
      <div className="rounded-sm border border-line-subtle bg-surface p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs bg-accent/10 text-accent text-xs font-mono-lab uppercase font-semibold border border-accent/20">
            <span>🎯 Foco: FMRP-USP / FAEPA</span>
          </div>
          <h3 className="text-sm font-bold text-ink-primary">
            Estações Canônicas da Prova Prática USP Ribeirão Preto
          </h3>
          <p className="text-xs text-ink-secondary max-w-xl">
            Cenários reais calibrados na conduta do HC-UE, HC-Criança, Hospital Mater e Centro de Saúde Escola Sumarezinho.
          </p>
        </div>
        <button
          onClick={() => { setSelectedInst("USP-RP"); setSelectedArea("Todas as Áreas"); }}
          className={`shrink-0 px-3.5 py-1.5 rounded-xs text-xs font-mono-lab font-semibold transition-colors cursor-pointer ${
            selectedInst === "USP-RP"
              ? "bg-ink-primary text-canvas shadow-xs"
              : "bg-canvas hover:bg-surface text-ink-primary border border-line-subtle"
          }`}
        >
          {selectedInst === "USP-RP" ? "✓ Filtrando USP-RP" : "Filtrar USP-RP"}
        </button>
      </div>

      {/* Filtros de Bancas e Especialidades */}
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 text-xs font-mono-lab font-semibold text-ink-tertiary uppercase tracking-wider">
          <Filter className="w-3.5 h-3.5" />
          <span>Filtrar por Banca Oficial com 2ª Fase</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {INSTITUTIONS.map((inst) => (
            <button
              key={inst}
              onClick={() => setSelectedInst(inst)}
              className={`px-3 py-1 rounded-xs text-xs font-mono-lab transition-colors cursor-pointer border ${
                selectedInst === inst
                  ? "bg-ink-primary text-canvas border-ink-primary font-bold shadow-xs"
                  : "bg-surface text-ink-secondary border-line-subtle hover:border-line-crisp"
              }`}
            >
              {inst}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-1.5 pt-1">
          {AREAS.map((area) => (
            <button
              key={area}
              onClick={() => setSelectedArea(area)}
              className={`px-3 py-1 rounded-xs text-xs font-mono-lab transition-colors cursor-pointer border ${
                selectedArea === area
                  ? "bg-accent text-white border-accent font-bold shadow-xs"
                  : "bg-surface text-ink-secondary border-line-subtle hover:border-line-crisp"
              }`}
            >
              {area}
            </button>
          ))}
        </div>
      </div>

      {/* Grid de Estações */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredStations.map((station) => {
          const isPassed = station.best_score !== null && station.best_score >= 7.0;
          const isAiGenerated = station.code?.startsWith("USP-RP-AI-");

          return (
            <div
              key={station.id}
              className="group flex flex-col justify-between rounded-sm border border-line-subtle bg-surface hover:border-line-crisp transition-all shadow-xs overflow-hidden"
            >
              <div className="p-4 space-y-3">
                {/* Header do Card */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="px-2 py-0.5 rounded-xs text-xs font-mono-lab font-semibold uppercase bg-canvas border border-line-subtle text-ink-secondary">
                      {station.institution}
                    </span>
                    {isAiGenerated && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[10px] font-mono-lab font-bold uppercase bg-accent/10 text-accent border border-accent/20">
                        <Zap className="w-2.5 h-2.5 text-amber-400" />
                        <span>IA Inédita</span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-xs font-mono-lab tabular-nums text-ink-tertiary">
                    <Clock className="w-3 h-3" />
                    <span>{Math.round(station.duration_seconds / 60)} min</span>
                  </div>
                </div>

                {/* Título & Subtema */}
                <div>
                  <h3 className="text-sm font-semibold text-ink-primary group-hover:text-accent transition-colors line-clamp-2">
                    {station.title}
                  </h3>
                  <p className="text-xs text-ink-secondary mt-1 font-mono-lab">
                    {station.area} • {station.subtema}
                  </p>
                </div>

                {/* Score Status */}
                <div className="pt-2 border-t border-line-subtle flex items-center justify-between text-xs font-mono-lab">
                  <span className="text-ink-tertiary">Desempenho Barema:</span>
                  {station.best_score !== null ? (
                    <span className={`font-bold tabular-nums flex items-center gap-1 ${
                      isPassed ? "text-emerald-500" : "text-rose-500"
                    }`}>
                      {isPassed ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                      {station.best_score.toFixed(1)} / 10.0
                    </span>
                  ) : (
                    <span className="text-ink-tertiary/70 italic text-[11px]">Não realizada</span>
                  )}
                </div>
              </div>

              {/* Botão de Entrada */}
              <div className="p-2.5 bg-canvas border-t border-line-subtle">
                <Link
                  href={`/osce/${station.id}`}
                  className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xs text-xs font-mono-lab font-semibold bg-accent/10 hover:bg-accent hover:text-white text-accent border border-accent/20 transition-colors shadow-xs"
                >
                  <span>Abrir Porta da Estação</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {filteredStations.length === 0 && (
        <div className="text-center py-12 border border-dashed border-line-subtle rounded-sm p-6 bg-surface">
          <AlertCircle className="w-8 h-8 text-ink-tertiary mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-ink-primary font-mono-lab">Nenhuma estação encontrada</h3>
          <p className="text-xs text-ink-secondary mt-1">
            Tente selecionar outros filtros de bancas ou grandes áreas.
          </p>
        </div>
      )}
    </div>
  );
}
