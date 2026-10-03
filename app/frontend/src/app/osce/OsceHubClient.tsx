"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Stethoscope, Clock, Award, AlertCircle, 
  CheckCircle2, ChevronRight, Play, Sparkles, Filter
} from "lucide-react";
import { OsceStation } from "@/types/api";

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
  const [stations] = useState<OsceStation[]>(initialStations);
  const [selectedInst, setSelectedInst] = useState<string>("Todas as Bancas");
  const [selectedArea, setSelectedArea] = useState<string>("Todas as Áreas");
  const [activeTab, setActiveTab] = useState<"avulso" | "circuito">("avulso");

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

  // Iniciar circuito de 5 estações
  const handleStartCircuit = () => {
    // Pega a primeira estação de cada grande área disponível
    const firstStation = stations[0];
    if (firstStation) {
      const circuitId = `circuit-${Date.now()}`;
      router.push(`/osce/${firstStation.id}?circuit=${circuitId}&step=1`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto w-full space-y-8 animate-in fade-in duration-300">
      {/* Header com Branding Radical da 2ª Fase */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary/10 via-background to-secondary/10 border border-primary/20 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/15 text-primary text-xs font-semibold tracking-wide uppercase">
              <Stethoscope className="w-3.5 h-3.5" />
              <span>Simulador Oficial de 2ª Fase Prática (OSCE)</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              Arena OSCE & Beira-Leito
            </h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl leading-relaxed">
              Treinamento de estações clínicas com paciente virtual falante, estetoscópio interativo, 
              exames complementares reais e <strong>Espelho de Correção Oficial</strong> das bancas 
              com 2ª fase presencial (<span className="text-foreground font-medium">UNICAMP, UNIFESP, Einstein, Revalida INEP, SCMSP e USP-RP</span>).
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-3 md:gap-4 shrink-0 bg-card/60 backdrop-blur-md p-4 rounded-2xl border border-border">
            <div className="text-center px-2">
              <div className="text-2xl md:text-3xl font-black text-foreground">{stats.total}</div>
              <div className="text-xs text-muted-foreground font-medium">Estações</div>
            </div>
            <div className="text-center px-2 border-x border-border">
              <div className="text-2xl md:text-3xl font-black text-primary">{stats.completed}</div>
              <div className="text-xs text-muted-foreground font-medium">Concluídas</div>
            </div>
            <div className="text-center px-2">
              <div className="text-2xl md:text-3xl font-black text-emerald-500">
                {stats.completed > 0 ? stats.avgScore : "—"}
              </div>
              <div className="text-xs text-muted-foreground font-medium">Média Barema</div>
            </div>
          </div>
        </div>

        {/* Tab Selector: Treino Avulso vs Circuito Oficial */}
        <div className="flex items-center gap-3 mt-8 border-t border-border/60 pt-6">
          <button
            onClick={() => setActiveTab("avulso")}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "avulso"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted/50 hover:bg-muted text-muted-foreground"
            }`}
          >
            Treino Avulso por Estação
          </button>
          <button
            onClick={() => setActiveTab("circuito")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "circuito"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted/50 hover:bg-muted text-muted-foreground"
            }`}
          >
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>Circuito de Prova (5 Estações)</span>
          </button>
        </div>
      </div>

      {/* Seção Circuito de Prova */}
      {activeTab === "circuito" && (
        <div className="rounded-2xl border-2 border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-background to-amber-500/5 p-6 md:p-8 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-bold text-sm">
                <Award className="w-4 h-4" />
                SIMULAÇÃO DO DIA DA PROVA PRESENCIAL
              </div>
              <h2 className="text-2xl font-bold text-foreground">Circuito de Rotação Completo</h2>
              <p className="text-muted-foreground text-sm max-w-2xl">
                Você enfrentará 5 estações seguidas (Clínica Médica, Cirurgia Geral, Pediatria, Ginecologia/Obstetrícia e Preventiva). 
                Ao fim de cada 8 minutos, o sino toca e você roda para a próxima sala. Ao final, receba o barema global da sua 2ª Fase (0 a 50 pontos).
              </p>
            </div>
            <button
              onClick={handleStartCircuit}
              className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-bold bg-amber-500 hover:bg-amber-600 text-black shadow-lg transition-transform active:scale-95 shrink-0"
            >
              <Play className="w-5 h-5 fill-current" />
              <span>Entrar no Circuito Oficial</span>
            </button>
          </div>
        </div>
      )}

      {/* Banner de Destaque FMRP-USP */}
      <div className="rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-primary/20 text-primary text-xs font-bold uppercase tracking-wider">
            <span>🎯 Foco Principal: FMRP-USP / FAEPA</span>
          </div>
          <h3 className="text-lg font-bold text-foreground">
            Estações Canônicas da Prova Prática USP Ribeirão Preto
          </h3>
          <p className="text-xs text-muted-foreground max-w-xl">
            Cenários reais calibrados na conduta do HC-UE, HC-Criança, Hospital Mater e Centro de Saúde Escola Sumarezinho.
          </p>
        </div>
        <button
          onClick={() => { setSelectedInst("USP-RP"); setSelectedArea("Todas as Áreas"); }}
          className={`shrink-0 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-sm ${
            selectedInst === "USP-RP"
              ? "bg-primary text-primary-foreground ring-2 ring-primary/40"
              : "bg-background hover:bg-muted text-foreground border border-border"
          }`}
        >
          {selectedInst === "USP-RP" ? "✓ Filtrando USP-RP (6 Estações)" : "Filtrar USP-RP (6 Estações)"}
        </button>
      </div>

      {/* Filtros de Bancas e Especialidades */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          <Filter className="w-3.5 h-3.5" />
          <span>Filtrar por Banca Oficial com 2ª Fase</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {INSTITUTIONS.map((inst) => (
            <button
              key={inst}
              onClick={() => setSelectedInst(inst)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                selectedInst === inst
                  ? "bg-foreground text-background"
                  : "bg-muted/60 hover:bg-muted text-muted-foreground"
              }`}
            >
              {inst}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          {AREAS.map((area) => (
            <button
              key={area}
              onClick={() => setSelectedArea(area)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                selectedArea === area
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "bg-card hover:bg-muted text-muted-foreground border border-border"
              }`}
            >
              {area}
            </button>
          ))}
        </div>
      </div>

      {/* Grid de Estações */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredStations.map((station) => {
          const isPassed = station.best_score !== null && station.best_score >= 7.0;

          return (
            <div
              key={station.id}
              className="group flex flex-col justify-between rounded-2xl border border-border bg-card hover:border-primary/40 hover:shadow-md transition-all duration-200 overflow-hidden"
            >
              <div className="p-5 space-y-3.5">
                {/* Header do Card */}
                <div className="flex items-center justify-between gap-2">
                  <span className="px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider bg-primary/10 text-primary">
                    {station.institution}
                  </span>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{Math.round(station.duration_seconds / 60)} min</span>
                  </div>
                </div>

                {/* Título & Subtema */}
                <div>
                  <h3 className="text-base font-bold text-foreground group-hover:text-primary transition-colors line-clamp-2">
                    {station.title}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1 font-medium">
                    {station.area} • {station.subtema}
                  </p>
                </div>

                {/* Score Status */}
                <div className="pt-2 border-t border-border/50 flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Desempenho no Barema:</span>
                  {station.best_score !== null ? (
                    <span className={`font-bold flex items-center gap-1 ${
                      isPassed ? "text-emerald-500" : "text-rose-500"
                    }`}>
                      {isPassed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                      {station.best_score.toFixed(1)} / 10.0
                    </span>
                  ) : (
                    <span className="text-muted-foreground/70 italic">Não realizada</span>
                  )}
                </div>
              </div>

              {/* Botão de Entrada */}
              <div className="p-3 bg-muted/20 border-t border-border/50">
                <Link
                  href={`/osce/${station.id}`}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold bg-primary text-primary-foreground hover:bg-primary/90 transition-transform active:scale-98 shadow-sm"
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
        <div className="text-center py-16 border border-dashed border-border rounded-2xl p-6">
          <AlertCircle className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <h3 className="text-base font-semibold text-foreground">Nenhuma estação encontrada</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Tente selecionar outros filtros de bancas ou grandes áreas.
          </p>
        </div>
      )}
    </div>
  );
}
