import React, { useMemo, useState } from "react";
import clsx from "clsx";
import { Filter, RotateCcw, Play, RefreshCw, Brain, SlidersHorizontal, BookOpenCheck, FileSignature, X, Search, Sparkles } from "lucide-react";
import { QuestionMeta } from "@/types/api";
import { SubjectTreeSelector } from "@/components/SubjectTreeSelector";
import { SavedQuizState } from "../QuizClient";

export interface QuizFiltersProps {
  hasSavedState: boolean;
  savedSessionData: SavedQuizState | null;
  discardSavedQuiz: () => void;
  resumeSavedQuiz: () => void;
  showCustomSession: boolean;
  setShowCustomSession: (val: boolean) => void;
  startRecommendedSession: (kind: "adaptive" | "review" | "wrong", focus?: "coverage" | "balanced" | "retention") => void;
  handleFilterSubmit: (e: React.FormEvent) => void;
  studyMode: "TUTOR" | "SIMULADO";
  setStudyMode: (mode: "TUTOR" | "SIMULADO") => void;
  filters: Record<string, string | string[]>;
  setFilters: React.Dispatch<React.SetStateAction<Record<string, string | string[]>>>;
  localLimit: string;
  setLocalLimit: (val: string) => void;
  isUpdatingMeta: boolean;
  dynamicMeta: QuestionMeta;
  subtemaSearch: string;
  setSubtemaSearch: (val: string) => void;
  showTopicTree: boolean;
  setShowTopicTree: React.Dispatch<React.SetStateAction<boolean>>;
}

export function QuizFilters({
  hasSavedState,
  savedSessionData,
  discardSavedQuiz,
  resumeSavedQuiz,
  showCustomSession,
  setShowCustomSession,
  startRecommendedSession,
  handleFilterSubmit,
  studyMode,
  setStudyMode,
  filters,
  setFilters,
  localLimit,
  setLocalLimit,
  isUpdatingMeta,
  dynamicMeta,
  subtemaSearch,
  setSubtemaSearch,
  showTopicTree,
  setShowTopicTree
}: QuizFiltersProps) {
  const [adaptiveFocus, setAdaptiveFocus] = useState<"coverage" | "balanced" | "retention">("balanced");
  const groupedInstitutions = useMemo(() => {
    const map = new Map<string, { codes: string[], n: number }>();
    for (const i of dynamicMeta?.institutions || []) {
        let base = i.institution_code.replace(/\s+\d{4}$/, '').replace(/\s+\d$/, '').trim();
        if (base === 'FAMEMA SP') base = 'FAMEMA';
        if (base === 'SCMRP') base = 'SCM-RP';
        if (base === 'SCM') base = 'SCM-SP';
        
        const existing = map.get(base);
        if (existing) {
            existing.codes.push(i.institution_code);
            existing.n += i.n;
        } else {
            map.set(base, { codes: [i.institution_code], n: i.n });
        }
    }
    return Array.from(map.entries())
        .map(([base, data]) => ({ base, codes: data.codes, n: data.n }))
        .sort((a, b) => b.n - a.n);
  }, [dynamicMeta?.institutions]);

  const selectedInstValue = useMemo(() => {
    if (!filters.institution) return "";
    const currentArr = Array.isArray(filters.institution) ? filters.institution : [filters.institution];
    for (const g of groupedInstitutions) {
       if (g.codes.length === currentArr.length && g.codes.every(c => currentArr.includes(c))) {
           return g.base;
       }
    }
    const single = currentArr[0];
    const group = groupedInstitutions.find(g => g.codes.includes(single));
    if (group && currentArr.length === 1) return group.base; 
    return "";
  }, [filters.institution, groupedInstitutions]);

return (
  <div className="bg-card border border-border shadow-1 rounded-xl p-8 max-w-2xl mx-auto w-full">
    <div className="flex items-center gap-4 mb-6">
      <div className="w-12 h-12 bg-primary/20 text-primary rounded-xl flex items-center justify-center shrink-0">
        <Filter size={24} />
      </div>
      <div>
        <h2 className="text-h2 font-bold text-foreground">Filtros de Estudo</h2>
        <p className="text-muted-foreground text-sm">Monte sua sessão de estudos escolhendo os filtros.</p>
      </div>
    </div>

    {hasSavedState && savedSessionData && (
      <div className="bg-primary/10 border border-primary/30 rounded-xl p-5 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shrink-0 shadow-sm">
            <RotateCcw size={20} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">Sessão de Estudos em Andamento</h3>
            <p className="text-xs text-muted-foreground">
              Você tem uma sessão salva com {savedSessionData.queue.length} questões (Questão {savedSessionData.currentIndex + 1} de {savedSessionData.queue.length}).
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            type="button"
            onClick={discardSavedQuiz}
            className="flex-1 sm:flex-initial px-3 py-2 text-xs font-semibold text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors cursor-pointer"
          >
            Descartar
          </button>
          <button
            type="button"
            onClick={resumeSavedQuiz}
            className="flex-1 sm:flex-initial px-4 py-2 text-xs font-bold bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer hover:scale-[1.02]"
          >
            <Play size={14} fill="currentColor" />
            Continuar Sessão
          </button>
        </div>
      </div>
    )}

    {!showCustomSession && (
      <div className="space-y-4">
        <div>
          <h3 className="text-base font-bold text-foreground">O que você quer fazer agora?</h3>
          <p className="text-sm text-muted-foreground mt-1">Comece pela próxima ação útil; você pode personalizar uma sessão quando precisar.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => startRecommendedSession("review")}
            className="text-left rounded-xl border border-primary/30 bg-primary/5 p-4 sm:p-5 transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center gap-2 text-primary font-bold text-sm sm:text-base"><RefreshCw size={18} /> Revisar o que venceu</div>
              <p className="mt-2 text-xs sm:text-sm text-muted-foreground leading-relaxed">Até 20 questões com repetição pendente no motor FSRS. Prioridade máxima para fixação.</p>
            </div>
            <span className="mt-3 text-xs font-bold text-primary flex items-center gap-1">Iniciar revisão →</span>
          </button>

          <button
            type="button"
            onClick={() => startRecommendedSession("wrong")}
            className="text-left rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 sm:p-5 transition-colors hover:bg-rose-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 cursor-pointer flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-bold text-sm sm:text-base"><RotateCcw size={18} /> Caderno de Erros</div>
              <p className="mt-2 text-xs sm:text-sm text-muted-foreground leading-relaxed">Até 20 questões com erro em aberto. Retifique e zere suas vulnerabilidades.</p>
            </div>
            <span className="mt-3 text-xs font-bold text-rose-600 dark:text-rose-400 flex items-center gap-1">Retificar erros →</span>
          </button>
        </div>

        <div
          className="text-left rounded-xl border border-border bg-muted/30 p-5 transition-colors hover:bg-muted/60 focus-within:ring-2 focus-within:ring-primary flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-foreground font-bold text-base">
                <Brain size={18} className="text-primary" /> Sessão Adaptativa Inteligente
              </div>
              <button
                type="button"
                onClick={() => startRecommendedSession("adaptive", adaptiveFocus)}
                className="px-3.5 py-1.5 bg-primary text-primary-foreground text-xs font-bold rounded-lg hover:bg-primary/90 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
              >
                <Play size={12} fill="currentColor" /> Iniciar 30 Questões
              </button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
              30 questões balanceadas com <span className="text-purple-600 dark:text-purple-400 font-semibold inline-flex items-center gap-0.5"><Sparkles size={11} /> Questões Gêmeas</span> para testar raciocínio clínico sem decoreba.
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-border/50">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Foco da Sessão</span>
              <span className="text-[11px] text-primary font-medium">
                {adaptiveFocus === "coverage" ? "70% Inéditas · 30% Revisão" :
                 adaptiveFocus === "retention" ? "80% Revisão & Erros · 20% Inéditas" :
                 "50% Inéditas · 50% Revisão"}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-1 bg-background p-1 rounded-lg border border-border">
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setAdaptiveFocus("coverage"); }}
                className={clsx(
                  "py-1 px-1.5 text-xs font-semibold rounded-md transition-all text-center cursor-pointer",
                  adaptiveFocus === "coverage" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                )}
                title="Foco em cobrir o edital com novas questões"
              >
                Cobertura
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setAdaptiveFocus("balanced"); }}
                className={clsx(
                  "py-1 px-1.5 text-xs font-semibold rounded-md transition-all text-center cursor-pointer",
                  adaptiveFocus === "balanced" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                )}
                title="Equilíbrio entre questões inéditas e revisões"
              >
                Equilibrado
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setAdaptiveFocus("retention"); }}
                className={clsx(
                  "py-1 px-1.5 text-xs font-semibold rounded-md transition-all text-center cursor-pointer",
                  adaptiveFocus === "retention" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                )}
                title="Foco em fixação, Questões Gêmeas e correção de erros"
              >
                Fixação
              </button>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowCustomSession(true)}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-border py-3 text-sm font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <SlidersHorizontal size={16} /> Montar sessão personalizada
        </button>
      </div>
    )}

    {showCustomSession && <form onSubmit={handleFilterSubmit} className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-foreground">Sessão personalizada</h3>
          <p className="text-sm text-muted-foreground">Use filtros apenas quando houver um objetivo específico.</p>
        </div>
        <button type="button" onClick={() => setShowCustomSession(false)} className="text-sm font-semibold text-primary hover:underline">Voltar</button>
      </div>
      <div className="bg-muted/30 border border-border p-4 rounded-lg flex flex-col sm:flex-row gap-4">
        <button 
          type="button"
          onClick={() => setStudyMode("TUTOR")}
          className={clsx(
            "flex-1 flex flex-col items-center justify-center gap-2 p-4 rounded-md border transition-all",
            studyMode === "TUTOR" ? "bg-primary/10 border-primary text-primary shadow-sm" : "bg-card border-border text-muted-foreground hover:bg-muted/50"
          )}
        >
          <BookOpenCheck size={24} />
          <span className="font-bold">Modo Tutor</span>
          <span className="text-xs text-center">Feedback imediato após cada resposta. Ideal para aprender.</span>
        </button>
        <button 
          type="button"
          onClick={() => setStudyMode("SIMULADO")}
          className={clsx(
            "flex-1 flex flex-col items-center justify-center gap-2 p-4 rounded-md border transition-all",
            studyMode === "SIMULADO" ? "bg-primary/10 border-primary text-primary shadow-sm" : "bg-card border-border text-muted-foreground hover:bg-muted/50"
          )}
        >
          <FileSignature size={24} />
          <span className="font-bold">Modo Simulado</span>
          <span className="text-xs text-center">Foco e resistência. Feedback e correção apenas no final.</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Status</label>
          <select 
            className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            value={filters.status || (filters.unanswered_only === "true" ? "unanswered" : "")}
            onChange={(e) => {
              const val = e.target.value;
              const next: Record<string, string | string[]> = { ...filters, status: val };
              if (val === "unanswered") {
                next.unanswered_only = "true";
              } else if (val === "") {
                delete next.unanswered_only;
              }
              setFilters(next);
            }}
          >
            <option className="bg-background text-foreground" value="unanswered">Não respondidas (Padrão)</option>
            <option className="bg-background text-foreground" value="">Todas (inclui já respondidas)</option>
            <option className="bg-background text-foreground" value="srs_due">Para Revisão (Repetição Espaçada)</option>
            <option className="bg-background text-foreground" value="wrong">Errei anteriormente</option>
          </select>
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Quantidade de Questões</label>
          <input 
            type="number"
            min="1"
            max="200"
            className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            value={localLimit}
            onChange={(e) => {
              const val = e.target.value;
              setLocalLimit(val);
              setFilters((prev) => ({ ...prev, limit: val }));
            }}
          />
          <p className="text-xs text-muted-foreground">Máximo de 200 questões por sessão.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground flex items-center justify-between">
            <span>Área</span>
            {isUpdatingMeta && <span className="text-xs text-muted-foreground animate-pulse">Atualizando...</span>}
          </label>
          <select 
            className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            value={filters.area || ""}
            onChange={(e) => setFilters({ ...filters, area: e.target.value })}
          >
            <option className="bg-background text-foreground" value="">Todas as Áreas</option>
            {(dynamicMeta.areas || []).map(a => (
              <option className="bg-background text-foreground" key={a.area} value={a.area}>{a.area} ({a.n})</option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground flex items-center justify-between">
            <span>Ano</span>
            {isUpdatingMeta && <span className="text-xs text-muted-foreground animate-pulse">Atualizando...</span>}
          </label>
          <select 
            className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            value={filters.year || ""}
            onChange={(e) => setFilters({ ...filters, year: e.target.value })}
          >
            <option className="bg-background text-foreground" value="">Todos os Anos</option>
            {(dynamicMeta.years || []).map(y => (
              <option className="bg-background text-foreground" key={y} value={String(y)}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-3 mt-6">
        <label className="text-sm font-medium text-foreground flex items-center justify-between">
          <span>Instituição / Banca</span>
          {isUpdatingMeta && <span className="text-xs text-muted-foreground animate-pulse">Atualizando...</span>}
        </label>

        <select 
          className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          value={selectedInstValue}
          onChange={(e) => {
             const val = e.target.value;
             if (val === "") {
                 const newFilters = { ...filters };
                 delete newFilters.institution;
                 setFilters(newFilters);
             } else {
                 const group = groupedInstitutions.find(g => g.base === val);
                 if (group) {
                     setFilters({ ...filters, institution: group.codes });
                 } else {
                     setFilters({ ...filters, institution: val });
                 }
             }
          }}
        >
          <option className="bg-background text-foreground" value="">Todas as Instituições ({dynamicMeta?.total_questions ?? 0})</option>
          {groupedInstitutions.map(g => (
            <option className="bg-background text-foreground" key={g.base} value={g.base}>
              {g.base} ({g.n})
            </option>
          ))}
        </select>
      </div>
        
        <div className="space-y-2 md:col-span-2 relative">
          <label className="text-sm font-medium text-foreground flex items-center justify-between">
            <span>Subtemas (Múltipla Escolha)</span>
            {isUpdatingMeta && <span className="text-xs text-muted-foreground animate-pulse">Atualizando...</span>}
          </label>
          
          {/* Chips of selected subtemas */}
          {Array.isArray(filters.subtema) && filters.subtema.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {filters.subtema.map(sub => (
                <span key={sub} className="bg-primary/10 text-primary border border-primary/20 px-3 py-1.5 rounded-full text-sm flex items-center gap-1.5 animate-in zoom-in-95 duration-200">
                  <span className="max-w-[200px] truncate">{sub}</span>
                  <button 
                    type="button" 
                    onClick={() => {
                      const current = (filters.subtema as string[]).filter(x => x !== sub);
                      const newFilters = { ...filters };
                      if (current.length > 0) newFilters.subtema = current;
                      else delete newFilters.subtema;
                      setFilters(newFilters);
                    }} 
                    className="hover:text-destructive hover:bg-destructive/10 rounded-full p-0.5 transition-colors"
                    aria-label="Remover"
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
              <button 
                type="button" 
                onClick={() => {
                  const newFilters = { ...filters };
                  delete newFilters.subtema;
                  setFilters(newFilters);
                }}
                className="text-xs text-muted-foreground hover:text-foreground underline px-2 py-1.5"
              >
                Limpar todos
              </button>
            </div>
          )}
          
          <div className="relative">
            <input
              type="text"
              placeholder="Buscar subtema para adicionar..."
              value={subtemaSearch}
              onChange={(e) => setSubtemaSearch(e.target.value)}
              className="w-full bg-input border border-border rounded-md py-2.5 px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary pl-9"
            />
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              <Search size={16} />
            </div>
          </div>
          
          {subtemaSearch.trim().length > 0 && (
            <div className="absolute z-50 w-full mt-1 bg-card border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
              {dynamicMeta.subtemas
                ?.filter(s => s.subtema.toLowerCase().includes(subtemaSearch.toLowerCase()))
                .filter(s => !(Array.isArray(filters.subtema) && filters.subtema.includes(s.subtema)))
                .length === 0 && (
                  <div className="px-4 py-3 text-sm text-muted-foreground italic">
                    Nenhum subtema disponível encontrado.
                  </div>
              )}
              {dynamicMeta.subtemas
                ?.filter(s => s.subtema.toLowerCase().includes(subtemaSearch.toLowerCase()))
                .filter(s => !(Array.isArray(filters.subtema) && filters.subtema.includes(s.subtema)))
                .slice(0, 50)
                .map(s => (
                  <button 
                    key={s.subtema} 
                    type="button"
                    onClick={() => {
                      const current = Array.isArray(filters.subtema) ? [...filters.subtema] : (filters.subtema ? [filters.subtema as string] : []);
                      current.push(s.subtema);
                      setFilters({ ...filters, subtema: current });
                      setSubtemaSearch("");
                    }}
                    className="w-full text-left flex items-center justify-between px-4 py-2.5 hover:bg-muted text-sm border-b border-border/50 last:border-0"
                  >
                    <span className="truncate pr-4">{s.subtema}</span>
                    <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded-full shrink-0">{s.n}</span>
                  </button>
              ))}
            </div>
          )}
          
          <div className="mt-5 pt-4 border-t border-border">
            <button type="button" onClick={() => setShowTopicTree(value => !value)} className="text-sm font-semibold text-primary hover:underline">
              {showTopicTree ? "Ocultar árvore de temas" : "Abrir árvore de temas"}
            </button>
            {showTopicTree && <div className="mt-3"><SubjectTreeSelector
              selectedSubtemas={Array.isArray(filters.subtema) ? filters.subtema : (filters.subtema ? [filters.subtema] : [])}
              onChange={(newSelection) => {
                const newFilters = { ...filters };
                if (newSelection.length > 0) newFilters.subtema = newSelection;
                else delete newFilters.subtema;
                setFilters(newFilters);
              }}
              availableSubtemas={dynamicMeta.subtemas || []}
            /></div>}
          </div>
        </div>

      <button 
        type="submit"
        className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3.5 rounded-md transition-colors flex items-center justify-center gap-2 w-full mt-2 shadow-sm"
      >
        <Play size={18} fill="currentColor" />
        {studyMode === "TUTOR" ? "Iniciar Sessão de Estudos" : "Iniciar Simulado Personalizado"}
      </button>
    </form>}
  </div>
);
}
