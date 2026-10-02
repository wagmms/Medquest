"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Search, X, Sparkles, Filter, Image as ImageIcon, 
  ExternalLink, PlayCircle, BookOpen, AlertCircle, RefreshCw
} from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { SearchResult, SearchFilterOptions } from "@/types/api";

const QUICK_TOPICS = [
  "IAM com supra",
  "Choque Séptico",
  "Cetoacidose",
  "Apendicite",
  "Pré-eclâmpsia",
  "Tromboembolismo",
  "Dengue",
  "Meningite",
  "Asma aguda"
];

const AREAS = [
  "Todas",
  "Clínica Médica",
  "Cirurgia",
  "Pediatria",
  "Ginecologia e Obstetrícia",
  "Medicina Preventiva e Social"
];

const INSTITUTIONS = [
  "Todas",
  "USP-SP",
  "ENARE",
  "UNICAMP",
  "SUS-SP",
  "SCMSP",
  "IAMSPE"
];

function getAreaBadgeColor(area: string) {
  if (area.includes("Clínica")) return "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20";
  if (area.includes("Cirurgia")) return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
  if (area.includes("Pediatria")) return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
  if (area.includes("Ginecologia")) return "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20";
  if (area.includes("Preventiva")) return "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20";
  return "bg-muted text-muted-foreground border-border";
}

interface SearchClientProps {
  initialQuery?: string;
  initialArea?: string;
  initialInstitution?: string;
}

export function SearchClient({
  initialQuery = "",
  initialArea = "Todas",
  initialInstitution = "Todas"
}: SearchClientProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [selectedArea, setSelectedArea] = useState(initialArea);
  const [selectedInstitution, setSelectedInstitution] = useState(initialInstitution);
  const [selectedYear, setSelectedYear] = useState<string>("Todos");
  const [onlyWithImage, setOnlyWithImage] = useState(false);
  
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Atalho de teclado: '/' foca no campo de busca
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== inputRef.current && !(document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const executeSearch = useCallback(async (
    q: string, 
    area: string, 
    inst: string, 
    year: string, 
    withImg: boolean
  ) => {
    const cleanQ = q.trim();
    const hasFilters = area !== "Todas" || inst !== "Todas" || year !== "Todos" || withImg;

    if (!cleanQ && !hasFilters) {
      setResults([]);
      setIsLoading(false);
      setHasSearched(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);

    const filterOpts: SearchFilterOptions = {
      limit: 50,
      area: area !== "Todas" ? area : undefined,
      institution: inst !== "Todas" ? inst : undefined,
      year: year !== "Todos" ? year : undefined,
      has_images: withImg ? true : undefined,
    };

    try {
      const data = await api.questions.search(cleanQ, filterOpts, controller.signal);
      setResults(data);
      setHasSearched(true);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      console.error("Falha ao buscar questões:", err);
      setError("Não foi possível carregar os resultados da busca. Tente novamente.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounced search trigger
  useEffect(() => {
    const timer = setTimeout(() => {
      void executeSearch(query, selectedArea, selectedInstitution, selectedYear, onlyWithImage);
    }, 280);

    return () => clearTimeout(timer);
  }, [query, selectedArea, selectedInstitution, selectedYear, onlyWithImage, executeSearch]);

  const handleClear = () => {
    setQuery("");
    inputRef.current?.focus();
  };

  const handleStartPracticeBatch = () => {
    if (results.length === 0) return;
    // Se há um termo ou subtema dominante, direciona para o modo estudar
    const targetSubtema = results[0]?.subtema;
    if (targetSubtema) {
      router.push(`/estudar?subtema=${encodeURIComponent(targetSubtema)}&limit=20`);
    } else {
      router.push(`/estudar?limit=20`);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto px-4 sm:px-6 py-6 pb-24">
      {/* Top Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-primary font-bold text-xs tracking-wider uppercase">
          <Sparkles className="w-4 h-4" />
          <span>Pesquisa Clínica em 42.800+ Questões</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">
          Busca Clínica Instantânea
        </h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Pesquise por síndromes, sinais semiológicos, condutas de emergência, achados de imagem ou bancas examinadoras.
        </p>
      </div>

      {/* Main Search Bar */}
      <div className="relative flex items-center w-full">
        <div className="absolute left-4 text-muted-foreground pointer-events-none flex items-center justify-center">
          <Search className="w-5 h-5" />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ex: infarto com supra, cetoacidose, sinal de Cullen, apendicite, pré-eclâmpsia..."
          className="w-full h-13 pl-12 pr-24 rounded-2xl bg-card border border-border/70 text-foreground placeholder:text-muted-foreground/60 text-base shadow-xs focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all"
        />
        <div className="absolute right-3 flex items-center gap-1.5">
          {query && (
            <button
              onClick={handleClear}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              title="Limpar busca"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <span className="hidden sm:inline-flex items-center justify-center px-2 py-0.5 text-[11px] font-mono text-muted-foreground bg-muted/60 rounded-md border border-border/50">
            /
          </span>
        </div>
      </div>

      {/* Quick Clinical Suggestions */}
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
        <span className="text-xs font-semibold text-muted-foreground mr-1">Sugestões rápidas:</span>
        {QUICK_TOPICS.map((topic) => (
          <button
            key={topic}
            onClick={() => setQuery(topic)}
            className="text-xs font-medium px-2.5 py-1 rounded-lg bg-card hover:bg-primary/10 hover:text-primary border border-border/60 text-foreground transition-all cursor-pointer"
          >
            {topic}
          </button>
        ))}
      </div>

      {/* Structured Filters */}
      <div className="flex flex-wrap items-center gap-3 p-3.5 rounded-2xl bg-card border border-border/60 shadow-2xs">
        <div className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground uppercase tracking-wider mr-1">
          <Filter className="w-3.5 h-3.5" />
          <span>Filtros:</span>
        </div>

        {/* Área Filter */}
        <div className="flex items-center gap-1.5 text-xs">
          <label htmlFor="area-filter" className="text-muted-foreground font-medium">Área:</label>
          <select
            id="area-filter"
            value={selectedArea}
            onChange={(e) => setSelectedArea(e.target.value)}
            className="h-8 px-2.5 rounded-lg bg-background border border-border/70 text-foreground font-medium text-xs focus:ring-1 focus:ring-primary cursor-pointer"
          >
            {AREAS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        {/* Banca Filter */}
        <div className="flex items-center gap-1.5 text-xs">
          <label htmlFor="institution-filter" className="text-muted-foreground font-medium">Banca:</label>
          <select
            id="institution-filter"
            value={selectedInstitution}
            onChange={(e) => setSelectedInstitution(e.target.value)}
            className="h-8 px-2.5 rounded-lg bg-background border border-border/70 text-foreground font-medium text-xs focus:ring-1 focus:ring-primary cursor-pointer"
          >
            {INSTITUTIONS.map((inst) => (
              <option key={inst} value={inst}>{inst}</option>
            ))}
          </select>
        </div>

        {/* Ano Filter */}
        <div className="flex items-center gap-1.5 text-xs">
          <label htmlFor="year-filter" className="text-muted-foreground font-medium">Ano:</label>
          <select
            id="year-filter"
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            className="h-8 px-2.5 rounded-lg bg-background border border-border/70 text-foreground font-medium text-xs focus:ring-1 focus:ring-primary cursor-pointer"
          >
            <option value="Todos">Todos</option>
            <option value="2026">2026</option>
            <option value="2025">2025</option>
            <option value="2024">2024</option>
            <option value="2023">2023</option>
            <option value="2022">2022</option>
            <option value="2021">2021</option>
          </select>
        </div>

        {/* Imagem Toggle */}
        <button
          onClick={() => setOnlyWithImage(!onlyWithImage)}
          className={clsx(
            "flex items-center gap-1.5 h-8 px-3 rounded-lg text-xs font-medium border transition-colors cursor-pointer ml-auto sm:ml-0",
            onlyWithImage
              ? "bg-primary text-primary-foreground border-primary shadow-xs"
              : "bg-background text-muted-foreground border-border/70 hover:bg-muted"
          )}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          <span>Com Imagem</span>
        </button>
      </div>

      {/* Results Header */}
      {hasSearched && (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-b border-border/40 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-foreground">
              {results.length} {results.length === 1 ? "questão encontrada" : "questões encontradas"}
            </span>
            {isLoading && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground animate-pulse">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Atualizando...</span>
              </div>
            )}
          </div>

          {results.length > 0 && (
            <button
              onClick={handleStartPracticeBatch}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-xs hover:bg-primary/90 transition-all cursor-pointer"
            >
              <PlayCircle className="w-4 h-4" />
              <span>Resolver no Estudar</span>
            </button>
          )}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl border border-destructive/30 bg-destructive/10 text-destructive flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {/* Initial state (No search executed) */}
      {!hasSearched && !isLoading && (
        <div className="flex flex-col items-center justify-center p-12 text-center rounded-3xl border border-dashed border-border/80 bg-muted/20">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-3">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-foreground mb-1">
            Explore 42.800+ Questões Comentadas
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Digite um quadro clínico, droga ou conceito das bancas examinadoras para pesquisar instantaneamente no acervo completo.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {["ECG com supradesnivelamento", "Intoxicação por paracetamol", "Critérios de Wells para TEP"].map((term) => (
              <button
                key={term}
                onClick={() => setQuery(term)}
                className="text-xs px-3 py-1.5 rounded-full bg-card border border-border text-foreground hover:border-primary transition-all cursor-pointer"
              >
                &ldquo;{term}&rdquo;
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading state skeleton */}
      {isLoading && results.length === 0 && (
        <div className="flex flex-col gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-5 rounded-2xl bg-card border border-border/60 animate-pulse space-y-3">
              <div className="flex gap-2">
                <div className="h-5 w-20 bg-muted rounded-md" />
                <div className="h-5 w-16 bg-muted rounded-md" />
                <div className="h-5 w-32 bg-muted rounded-md" />
              </div>
              <div className="h-4 w-full bg-muted rounded" />
              <div className="h-4 w-3/4 bg-muted rounded" />
            </div>
          ))}
        </div>
      )}

      {/* No results found */}
      {hasSearched && !isLoading && results.length === 0 && (
        <div className="flex flex-col items-center justify-center p-12 text-center rounded-3xl border border-border/60 bg-card">
          <div className="w-12 h-12 rounded-2xl bg-muted text-muted-foreground flex items-center justify-center mb-3">
            <BookOpen className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-foreground mb-1">
            Nenhuma questão encontrada
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            Não encontramos questões correspondentes aos termos e filtros selecionados. Tente usar termos mais abrangentes ou remover os filtros de banca e ano.
          </p>
        </div>
      )}

      {/* Results List */}
      {results.length > 0 && (
        <div className="flex flex-col gap-3.5">
          {results.map((q) => (
            <div
              key={q.id}
              className="p-4 sm:p-5 rounded-2xl bg-card border border-border/60 hover:border-primary/40 transition-all shadow-2xs group flex flex-col gap-3"
            >
              {/* Card Header */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                  {/* Institution Badge */}
                  <span className="px-2 py-0.5 rounded-md bg-foreground/10 text-foreground font-bold text-xs">
                    {q.institution_code} {q.year}
                  </span>

                  {/* Area Badge */}
                  <span className={clsx("px-2 py-0.5 rounded-md border text-xs font-semibold", getAreaBadgeColor(q.area))}>
                    {q.area}
                  </span>

                  {/* Subtema */}
                  {q.subtema && (
                    <span className="px-2 py-0.5 rounded-md bg-muted/60 text-muted-foreground text-xs font-medium truncate max-w-[200px]">
                      {q.subtema}
                    </span>
                  )}

                  {/* Image Badge */}
                  {q.has_image && (
                    <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 text-[11px] font-bold">
                      <ImageIcon className="w-3 h-3" />
                      <span>Imagem</span>
                    </span>
                  )}

                  {/* Autoral Badge */}
                  {q.is_autoral && (
                    <span className="px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-bold uppercase">
                      Autoral
                    </span>
                  )}
                </div>

                <Link
                  href={`/estudar?id=${q.id}`}
                  className="flex items-center gap-1 text-xs font-bold text-primary group-hover:underline cursor-pointer"
                >
                  <span>Resolver questão</span>
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>

              {/* Stem Snippet */}
              <div 
                className="text-sm text-foreground leading-relaxed line-clamp-3 [&_b]:bg-primary/20 [&_b]:text-primary [&_b]:font-bold [&_b]:rounded [&_b]:px-0.5"
                dangerouslySetInnerHTML={{ __html: q.stem_snippet }}
              />

              {/* Explanation Snippet (if available) */}
              {q.exp_snippet && (
                <div className="p-2.5 rounded-xl bg-muted/30 border border-border/40 text-xs text-muted-foreground">
                  <span className="font-bold text-foreground/80 mr-1.5">💡 Comentário:</span>
                  <span 
                    className="leading-relaxed [&_b]:bg-primary/20 [&_b]:text-primary [&_b]:font-bold [&_b]:rounded [&_b]:px-0.5"
                    dangerouslySetInnerHTML={{ __html: q.exp_snippet }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
