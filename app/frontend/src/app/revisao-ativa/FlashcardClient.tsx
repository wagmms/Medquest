"use client";

import { useState, useEffect, useCallback } from "react";
import { Flashcard, FlashcardDeck } from "@/types/api";
import { api, OfflineQueuedError } from "@/lib/api";
import { localDb, getLocalOwnerId } from "@/lib/db";
import { normalizeFlashcard } from "@/lib/normalizeFlashcard";
import { FormattedContent } from "@/components/FormattedContent";
import { answerAnkiCard } from "@/lib/ankiConnect";
import dynamic from "next/dynamic";
import {
  Sparkles,
  CheckCircle2,
  RotateCcw,
  BrainCircuit,
  XCircle,
  Download,
  AlertTriangle,
  ExternalLink,
  CalendarClock,
  Layers,
  Zap,
  Tag,
  BookOpen,
  Trash2,
} from "lucide-react";
import toast from "react-hot-toast";
import { motion } from "framer-motion";
import Link from "next/link";
import { useCurator } from "@/hooks/useCurator";
import { useWakeLock } from "@/hooks/useWakeLock";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

const AnkiIntegrationModal = dynamic(
  () => import("./components/AnkiIntegrationModal").then((mod) => mod.AnkiIntegrationModal),
  { ssr: false }
);

export function FlashcardClient({ subtema }: { subtema?: string }) {
  const [queue, setQueue] = useState<Flashcard[]>([]);
  const [loading, setLoading] = useState(true);
  useWakeLock(queue.length > 0 && !loading);
  const [flipped, setFlipped] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [initialDueCount, setInitialDueCount] = useState(0);
  const [upcoming, setUpcoming] = useState<Flashcard[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [lastScheduled, setLastScheduled] = useState<string | null>(null);
  const [showUpcoming, setShowUpcoming] = useState(false);

  const { isCurator } = useCurator();
  const [isDeletingCard, setIsDeletingCard] = useState(false);
  const [showDeleteCardConfirm, setShowDeleteCardConfirm] = useState(false);

  // Deck State
  const [decks, setDecks] = useState<FlashcardDeck[]>([]);
  const [selectedDeck, setSelectedDeck] = useState<string>("all");
  const [isAnkiModalOpen, setIsAnkiModalOpen] = useState(false);

  const loadDecks = useCallback(async () => {
    try {
      const res = await api.flashcards.getDecks();
      setDecks(res.decks || []);
    } catch (e) {
      console.warn("Falha ao carregar lista de baralhos:", e);
    }
  }, []);

  const fetchDue = useCallback(async (signal?: AbortSignal, deckFilter: string = selectedDeck) => {
    setLoading(true);
    setLoadError(null);
    setFlipped(false);
    setLastScheduled(null);
    try {
      const [cards, upcomingCards, decksRes] = await Promise.all([
        api.flashcards.getDue(false, signal, deckFilter, subtema),
        api.flashcards.getUpcoming(signal, deckFilter, subtema),
        api.flashcards.getDecks().catch(() => ({ decks: [], total_cards: 0, due_cards: 0 })),
      ]);
      if (signal?.aborted) return;
      if (decksRes?.decks) setDecks(decksRes.decks);
      const normalizedCards = cards.map(normalizeFlashcard);
      setQueue(normalizedCards);
      setInitialDueCount(normalizedCards.length);
      setUpcoming(upcomingCards.map(normalizeFlashcard));

      // Migração automática de cartões legados no IndexedDB local
      if (typeof window !== "undefined" && localDb) {
        const uid = getLocalOwnerId();
        for (const card of normalizedCards) {
          localDb.flashcards
            .update([card.id, uid], {
              front: card.front,
              back: card.back,
            })
            .catch(() => {});
        }
      }
    } catch (error) {
      if (!signal?.aborted) {
        console.error("Erro ao buscar flashcards", error);
        setLoadError("Não foi possível carregar sua fila de revisão.");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [selectedDeck, subtema]);

  const handleReview = useCallback(async (confidence: string) => {
    if (queue.length === 0 || submitting) return;
    setSubmitting(true);
    const currentCard = queue[0];

    // Atualização Otimista da Interface
    setQueue(prev => prev.slice(1));
    setFlipped(false);
    

    try {
      const result = await api.flashcards.review(currentCard.id, confidence);
      setLastScheduled(result.next_review_date);
      if (currentCard.anki_cid) {
        try {
          const ankiState = await answerAnkiCard(currentCard.anki_cid, confidence);
          if (ankiState) {
            await api.flashcards.syncAnkiStates([ankiState]);
            toast.success("Avaliação sincronizada com o Anki.");
          }
        } catch (ankiError) {
          // The MedQuest review is already saved. The user can retry a pull
          // from the Anki modal without losing their study progress.
          console.warn("Falha ao enviar avaliação ao Anki:", ankiError);
          toast("Avaliação salva no MedQuest; não foi possível enviá-la ao Anki agora.", { icon: "⚠️" });
        }
      }
      if (localDb) {
        try {
          const uid = getLocalOwnerId();
          await localDb.flashcards.delete([currentCard.id, uid]);
        } catch {
          // ignore local cleanup error
        }
      }
    } catch (err) {
      if (err instanceof OfflineQueuedError) {
        toast("Avaliação salva neste dispositivo e será sincronizada quando a conexão voltar.", { icon: "💾" });
        if (localDb) {
          try {
            const uid = getLocalOwnerId();
            await localDb.flashcards.delete([currentCard.id, uid]);
          } catch {
            // ignore local cleanup error
          }
        }
      } else {
        setQueue(prev => [currentCard, ...prev.filter(card => card.id !== currentCard.id)]);
        toast.error("Não foi possível salvar. O cartão voltou para a fila.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [queue, submitting]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void fetchDue(controller.signal, selectedDeck);
    }, 0);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [fetchDue, selectedDeck]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (queue.length === 0 || loading || submitting || isAnkiModalOpen || showDeleteCardConfirm) return;
      if (e.defaultPrevented || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
      const target = e.target;
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('button, a, input, textarea, select, [role="button"], [role="dialog"]'))) return;
      if (document.querySelector('[aria-modal="true"]')) return;

      if (!flipped) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setFlipped(true);
        }
      } else {
        if (e.key === "1") {
          e.preventDefault();
          handleReview("errei");
        } else if (e.key === "2") {
          e.preventDefault();
          handleReview("duvida");
        } else if (e.key === "3" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleReview("certeza");
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [queue, loading, submitting, flipped, isAnkiModalOpen, showDeleteCardConfirm, handleReview]);

  const handleReport = async () => {
    if (queue.length === 0 || submitting) return;
    const reason = window.prompt("Qual o problema com este flashcard? (Ex: Erro médico, desatualizado, mal formatado)");
    if (!reason) return;

    setSubmitting(true);
    try {
      await api.flashcards.report(queue[0].id, reason);
      toast.success("Obrigado! O flashcard foi reportado e será auditado.");
      setQueue(prev => prev.slice(1));
      setFlipped(false);
    } catch {
      toast.error("Erro ao reportar flashcard.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteFlashcard = async () => {
    if (queue.length === 0 || isDeletingCard) return;
    const currentCard = queue[0];
    setIsDeletingCard(true);
    try {
      await api.flashcards.delete(currentCard.id);
      if (typeof window !== "undefined" && localDb) {
        try {
          const uid = getLocalOwnerId();
          await localDb.flashcards.delete([currentCard.id, uid]);
        } catch {}
      }
      setQueue(prev => prev.slice(1));
      setFlipped(false);
      setShowDeleteCardConfirm(false);
      toast.success("Flashcard excluído com sucesso!");
    } catch (err: unknown) {
      console.error("Erro ao excluir flashcard:", err);
      const msg = err instanceof Error ? err.message : "Erro ao excluir flashcard.";
      toast.error(msg);
    } finally {
      setIsDeletingCard(false);
    }
  };

  const renderFrontContent = (frontText: string) => {
    const parts = frontText.split(/({{c\d+::.*?}})/);
    const hasCloze = parts.some(p => p.startsWith("{{c") && p.endsWith("}}"));

    if (!hasCloze) {
      return <FormattedContent content={frontText} />;
    }

    return (
      <div className="space-y-2">
        {parts.map((part, i) => {
          if (part.startsWith("{{c") && part.endsWith("}}")) {
            const match = part.match(/{{c\d+::(.*?)(?:::([^}]+))?}}/);
            const content = match ? match[1] : part.slice(6, -2);
            const hint = match && match[2] ? match[2] : "";

            if (!flipped) {
              return (
                <span
                  key={i}
                  className="inline-block px-3 py-1 bg-purple-500/15 text-purple-600 dark:text-purple-400 font-bold border-b-2 border-purple-500 rounded mx-1 select-none animate-pulse"
                >
                  [{hint || "..."}]
                </span>
              );
            }
            return (
              <span
                key={i}
                className="inline-block px-2.5 py-1 bg-purple-500/20 text-purple-600 dark:text-purple-400 border border-purple-500/40 rounded-lg mx-1 font-bold animate-in fade-in zoom-in-95 duration-200"
              >
                {content}
              </span>
            );
          }
          if (part.includes("![imagem]") || part.includes("<img")) {
            return <FormattedContent key={i} content={part} />;
          }
          return <span key={i}>{part}</span>;
        })}
      </div>
    );
  };

  const totalDueAcrossDecks = decks.reduce((acc, d) => acc + d.due_cards, 0);

  return (
    <div className="max-w-3xl mx-auto w-full flex flex-col items-center gap-5 pb-12">
      {subtema && (
        <div className="w-full rounded-sm border border-line-subtle bg-surface p-4 shadow-xs">
          <p className="font-semibold text-sm text-ink font-mono-lab">Flashcards: {subtema}</p>
          <div className="flex flex-wrap gap-4 mt-1.5 text-xs font-mono-lab text-accent">
            <Link href={`/temas?${new URLSearchParams({ subtema })}`} className="hover:underline">← Voltar ao tema</Link>
            <Link href="/revisao-ativa" className="hover:underline">Ver todos os temas</Link>
          </div>
        </div>
      )}
      {/* Header com Seletor de Baralho e Botão Anki */}
      <div className="w-full flex items-center justify-between flex-wrap gap-3 pb-2.5 border-b border-line-subtle">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-accent font-bold text-xs uppercase tracking-wider font-mono-lab">
            <ClinicalIcon name="srs" size={16} />
            <span>Revisão Ativa (FSRS v6)</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Seletor de Baralho */}
          {decks.length > 0 && (
            <div className="flex items-center gap-1.5 bg-surface border border-line-subtle rounded-sm px-2.5 py-1.5 min-h-[36px] text-xs font-mono-lab shadow-xs">
              <ClinicalIcon name="stethoscope" size={13} className="text-ink-muted" />
              <select
                value={selectedDeck}
                onChange={(e) => setSelectedDeck(e.target.value)}
                className="bg-transparent font-semibold text-ink focus:outline-none cursor-pointer text-xs"
                aria-label="Filtrar por baralho"
              >
                <option value="all">Todos os Baralhos{subtema ? "" : ` (${totalDueAcrossDecks})`}</option>
                {decks.map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.name}{subtema ? "" : ` (${d.due_cards})`}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Botão de Integração com o Anki */}
          <button
            type="button"
            onClick={() => setIsAnkiModalOpen(true)}
            className="flex items-center gap-1.5 bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 px-3 py-1.5 min-h-[36px] rounded-sm font-bold text-xs font-mono-lab transition-all shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent cursor-pointer"
          >
            <ClinicalIcon name="zap" size={13} />
            <span>Integração Anki</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="w-full min-h-[300px] bg-surface border border-line-subtle shadow-xs rounded-sm p-8 flex flex-col items-center justify-center gap-4">
          <div className="w-8 h-8 border-2 border-accent/20 border-t-accent rounded-full animate-spin" />
          <p className="text-ink-muted font-mono-lab text-xs animate-pulse">Sincronizando seus flashcards...</p>
        </div>
      ) : queue.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-surface border border-line-subtle shadow-xs rounded-sm p-10 max-w-2xl mx-auto w-full text-center flex flex-col items-center"
        >
          <div className="w-16 h-16 bg-normal/10 text-normal rounded-full flex items-center justify-center mx-auto mb-4 border border-normal/20">
            <CheckCircle2 size={32} />
          </div>
          <h2 className="text-xl font-bold text-ink mb-2 tracking-tight">
            {loadError ? "Revisão indisponível" : initialDueCount > 0 ? "Fila diária concluída" : "Nenhuma revisão pendente"}
          </h2>
          <p className="text-ink-muted mb-6 text-sm max-w-md leading-relaxed">
            {loadError ? "Não foi possível verificar suas revisões agora." : initialDueCount > 0
              ? `Você concluiu a revisão de ${initialDueCount} ${initialDueCount === 1 ? "cartão" : "cartões"}.`
              : selectedDeck !== "all"
              ? `Você não tem revisões pendentes no baralho "${selectedDeck}".`
              : subtema ? "Não há flashcards vencidos vinculados a este tema." : "Você está em dia com todas as suas revisões FSRS."}
          </p>
          {loadError && (
            <div className="mb-5 w-full rounded-sm border border-critical/30 bg-critical/5 p-3 text-left text-xs text-critical flex items-center gap-2">
              <AlertTriangle size={16} /> {loadError}
              <button onClick={() => void fetchDue()} className="ml-auto font-bold underline font-mono-lab">Tentar novamente</button>
            </div>
          )}
          {!loadError && initialDueCount > 0 && <button onClick={() => void fetchDue()} className="mb-4 text-accent text-xs font-mono-lab font-semibold underline cursor-pointer">Verificar próximas revisões</button>}
          {!loadError && upcoming[0] && (
            <p className="mb-5 text-xs text-ink-muted flex items-center gap-1.5 font-mono-lab">
              <CalendarClock size={14} /> Próximo cartão: {new Date(upcoming[0].next_review_date).toLocaleDateString("pt-BR")}
            </p>
          )}
          <div className="flex items-center gap-3 flex-wrap justify-center">
            <Link
              href={subtema ? `/estudar?${new URLSearchParams({ subtema, mode: "adaptive", limit: "10" })}` : "/estudar"}
              className="bg-accent hover:opacity-90 text-white font-mono-lab font-bold py-2.5 px-5 rounded-sm transition-opacity shadow-xs flex items-center gap-2 text-xs uppercase tracking-wider"
            >
              <BookOpen size={15} />
              Estudar questões
            </Link>
            <button
              onClick={() => setIsAnkiModalOpen(true)}
              className="bg-surface hover:bg-elevated text-ink font-mono-lab font-semibold py-2.5 px-4 rounded-sm border border-line-subtle transition-colors flex items-center gap-1.5 text-xs"
            >
              <ClinicalIcon name="zap" size={14} />
              Importar Anki (.apkg)
            </button>
          </div>
        </motion.div>
      ) : (
        <>
          <div className="w-full flex items-center justify-between mb-1 flex-wrap gap-2">
            <div className="flex items-center gap-2 text-xs font-mono-lab text-ink-muted">
              <span>Restantes:</span>
              <span className="font-bold text-ink tabular-nums bg-canvas border border-line-subtle px-2 py-0.5 rounded-xs">
                {queue.length} / {initialDueCount}
              </span>
            </div>
          </div>

          {lastScheduled && (
            <div className="w-full rounded-xs border border-normal/25 bg-normal/10 px-3.5 py-1.5 text-xs font-mono-lab text-normal">
              Cartão agendado para {new Date(lastScheduled).toLocaleDateString("pt-BR")}.
            </div>
          )}

          {/* Cartão de Flashcard */}
          {(() => {
            const current = queue[0];
            return (
              <div
                className="w-full min-h-[300px] bg-surface border border-line-subtle shadow-xs rounded-sm p-6 md:p-8 flex flex-col items-center justify-center relative cursor-pointer hover:border-line-strong transition-colors focus:outline-none focus:ring-1 focus:ring-accent"
                onClick={() => !flipped && setFlipped(true)}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && !flipped) {
                    e.preventDefault();
                    setFlipped(true);
                  }
                }}
                role={!flipped ? "button" : "region"}
                tabIndex={!flipped ? 0 : -1}
                aria-label={flipped ? "Flashcard revelado" : "Clique ou pressione Espaço para revelar o flashcard"}
              >
                {/* Badges superiores */}
                <div className="absolute top-3.5 left-3.5 flex items-center gap-1.5 flex-wrap">
                  {current.is_ai_generated ? (
                    <div className="text-[11px] font-mono-lab font-semibold text-accent bg-accent/10 border border-accent/25 px-2 py-0.5 rounded-xs flex items-center gap-1">
                      <Sparkles size={11} /> MedQuest IA
                    </div>
                  ) : (
                    <div className="text-[11px] font-mono-lab font-semibold text-accent bg-accent/10 border border-accent/25 px-2 py-0.5 rounded-xs flex items-center gap-1">
                      <ClinicalIcon name="zap" size={11} /> Anki
                    </div>
                  )}

                  {current.deck_name && current.deck_name !== "Geral" && (
                    <div className="text-[11px] font-mono-lab text-ink-muted bg-canvas border border-line-subtle px-2 py-0.5 rounded-xs flex items-center gap-1">
                      <ClinicalIcon name="stethoscope" size={10} /> {current.deck_name}
                    </div>
                  )}
                </div>

                {/* Conteúdo Frente */}
                <div className="w-full text-base md:text-lg font-normal text-ink text-left leading-relaxed whitespace-pre-line my-6">
                  {renderFrontContent(current.front)}
                </div>

                {/* Conteúdo Verso */}
                {flipped && current.back && (
                  <div className="mt-4 pt-5 border-t border-line-subtle w-full text-left animate-in slide-in-from-bottom-2 fade-in duration-200">
                    <div className="bg-canvas p-4 rounded-xs border border-line-subtle text-sm md:text-base text-ink leading-relaxed font-normal">
                      <FormattedContent content={current.back} />
                    </div>

                    {current.source_context && (
                      <p className="mt-2.5 text-[11px] font-mono-lab text-ink-muted uppercase tracking-wider bg-canvas border border-line-subtle py-0.5 px-2.5 rounded-xs inline-block">
                        Referência: {current.source_context}
                      </p>
                    )}

                    {/* Tags do cartão */}
                    {current.tags && current.tags.length > 0 && (
                      <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
                        {current.tags.map((t, idx) => (
                          <span
                            key={idx}
                            className="text-[10px] font-mono-lab text-ink-muted bg-canvas border border-line-subtle px-2 py-0.5 rounded-xs flex items-center gap-1"
                          >
                            <Tag size={9} /> {t}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs font-mono-lab text-ink-muted">
                      {(current.area || current.subtema) && (
                        <span>{[current.area, current.subtema].filter(Boolean).join(" · ")}</span>
                      )}
                      {current.question_id && (
                        <Link
                          href={`/estudar?id=${current.question_id}`}
                          className="inline-flex items-center gap-1 text-accent hover:underline"
                        >
                          <ExternalLink size={12} /> Ver questão de origem
                        </Link>
                      )}
                    </div>
                  </div>
                )}

                {!flipped && (
                  <div className="absolute bottom-5 text-xs font-mono-lab font-bold text-ink-muted uppercase tracking-wider flex items-center gap-2">
                    <RotateCcw size={13} /> Clique ou pressione <kbd className="bg-canvas border border-line-subtle px-1.5 py-0.5 rounded-xs text-[10px] text-ink">Espaço</kbd> para revelar
                  </div>
                )}

                <div className="absolute top-3 right-3 flex items-center gap-1.5 z-10">
                  {isCurator && (
                    <button
                      type="button"
                      className="min-h-[30px] px-2 py-0.5 text-xs font-mono-lab text-critical hover:bg-critical/10 rounded-xs flex items-center gap-1 transition-colors cursor-pointer border border-transparent hover:border-critical/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-critical"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowDeleteCardConfirm(true);
                      }}
                      title="Excluir Flashcard (Curadoria)"
                      aria-label="Excluir Flashcard"
                    >
                      <Trash2 size={13} /> <span>Excluir</span>
                    </button>
                  )}
                  {flipped && (
                    <button
                      type="button"
                      className="min-h-[30px] px-2 py-0.5 text-xs font-mono-lab text-ink-muted hover:text-critical flex items-center justify-center gap-1 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-critical rounded-xs cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleReport();
                      }}
                      title="Reportar Erro no Flashcard"
                      aria-label="Reportar Erro no Flashcard"
                    >
                      <XCircle size={13} /> <span>Reportar</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Controles de Avaliação FSRS v6 */}
          {flipped && (
            <div className="grid grid-cols-1 sm:grid-cols-3 w-full gap-3 mt-3 animate-in slide-in-from-bottom-2 fade-in duration-200">
              <button
                title="O algoritmo agendará a revisão deste flashcard para amanhã (D+1)."
                onClick={() => handleReview("errei")}
                disabled={submitting}
                className="bg-critical/10 hover:bg-critical/20 text-critical border border-critical/30 font-bold py-3 px-3 rounded-sm transition-colors flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab shadow-xs disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-critical"
              >
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase"><XCircle size={15} /> Errei</div>
                <span className="text-[10px] text-critical/80 font-normal">Volta amanhã (D+1) • [1]</span>
              </button>
              <button
                title="Conceito difícil, retornando em aproximadamente 7 dias (D+7)."
                onClick={() => handleReview("duvida")}
                disabled={submitting}
                className="bg-warning/10 hover:bg-warning/20 text-ink border border-warning/30 font-bold py-3 px-3 rounded-sm transition-colors flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab shadow-xs disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-warning"
              >
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase text-ink"><RotateCcw size={14} className="text-warning" /> Difícil</div>
                <span className="text-[10px] text-ink-muted font-normal">~7 dias (D+7) • [2]</span>
              </button>
              <button
                title="Conceito fixado com firmeza, intervalo estendido para mais de 18 dias."
                onClick={() => handleReview("certeza")}
                disabled={submitting}
                className="bg-normal/10 hover:bg-normal/20 text-normal border border-normal/30 font-bold py-3 px-3 rounded-sm transition-colors flex flex-col items-center justify-center gap-0.5 cursor-pointer font-mono-lab shadow-xs disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-normal"
              >
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase"><CheckCircle2 size={15} /> Fácil</div>
                <span className="text-[10px] text-normal/80 font-normal">~18 dias+ (D+18) • [3]</span>
              </button>
            </div>
          )}

          <div className="w-full border-t border-border pt-5 flex flex-wrap items-center justify-between gap-3 text-sm">
            <button
              type="button"
              onClick={() => setShowUpcoming(value => !value)}
              className="font-semibold text-primary hover:underline"
            >
              {showUpcoming ? "Ocultar próximos cartões" : `Ver próximos cartões${upcoming.length ? ` (${upcoming.length})` : ""}`}
            </button>
            <button
              onClick={() => setIsAnkiModalOpen(true)}
              className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
            >
              <Download size={13} /> Gerenciar / Exportar Anki
            </button>
          </div>
          {showUpcoming && (
            <div className="w-full rounded-xl border border-border bg-muted/20 p-4 text-sm">
              <p className="font-bold text-foreground mb-3">Próximos cartões — consulta apenas</p>
              {upcoming.length ? (
                <ul className="space-y-2 text-muted-foreground">
                  {upcoming.slice(0, 5).map(card => (
                    <li key={card.id} className="flex justify-between gap-3">
                      <span className="truncate">{card.source_context || card.subtema || card.deck_name || "Flashcard"}</span>
                      <span className="shrink-0">{new Date(card.next_review_date).toLocaleDateString("pt-BR")}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground">Não há cartões futuros programados.</p>
              )}
            </div>
          )}
        </>
      )}

      {/* Modal de Integração com Anki */}
      <AnkiIntegrationModal
        isOpen={isAnkiModalOpen}
        onClose={() => setIsAnkiModalOpen(false)}
        onSuccess={() => {
          void fetchDue(undefined, selectedDeck);
          void loadDecks();
        }}
        decks={decks}
      />

      {/* Modal de Confirmação de Exclusão de Flashcard */}
      {showDeleteCardConfirm && queue[0] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div
            className="bg-card border border-destructive/30 rounded-2xl p-6 max-w-md w-full shadow-2xl flex flex-col gap-4 animate-in zoom-in-95 duration-200"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-card-title"
          >
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-full bg-destructive/10 text-destructive shrink-0">
                <Trash2 size={22} />
              </div>
              <div>
                <h3 id="delete-card-title" className="text-base font-bold text-foreground">
                  Excluir Flashcard #{queue[0].id}?
                </h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  Tem certeza de que deseja excluir este flashcard permanentemente? Esta ação removerá o cartão do banco de dados e da sua fila de revisão.
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setShowDeleteCardConfirm(false)}
                disabled={isDeletingCard}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-border text-foreground hover:bg-muted transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleDeleteFlashcard}
                disabled={isDeletingCard}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-all flex items-center gap-1.5 cursor-pointer shadow-sm disabled:opacity-50"
              >
                {isDeletingCard ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    Excluindo...
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    Confirmar Exclusão
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
