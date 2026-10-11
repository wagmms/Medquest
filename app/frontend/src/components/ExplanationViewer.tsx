"use client";

import React, { useMemo, useState } from "react";
import { 
  Sparkles, 
  Stethoscope, 
  CheckCircle2, 
  XCircle, 
  Award,
  AlertCircle,
  X
} from "lucide-react";
import { FormattedContent, preprocessMarkdown } from "@/components/FormattedContent";
import clsx from "clsx";

interface ExplanationViewerProps {
  explanation: string | null | undefined;
  correctLetter?: string | null;
  questionId?: number;
  userLetter?: string;
  isDiscursive?: boolean;
}

export interface ParsedSection {
  gabarito?: string;
  puloDoGato?: string;
  padraoResposta?: string;
  raciocinioClinico?: string;
  alternativaCorreta?: {
    letter?: string;
    text: string;
  };
  distratores?: Array<{
    letter: string;
    text: string;
  }>;
  fallbackText?: string;
}

function withoutReferenceSection(text: string): string {
  return text
    .replace(
      /(?:^|\n)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?(?:<br\s*\/?\>\s*)?(?:\*\*)?\s*(?:refer[eê]ncias?(?:\s+bibliogr[aá]ficas?)?|bibliografia|fontes?)\s*:?\s*(?:\*\*)?[\s\S]*?(?=\n\s*(?:#{1,6}\s+)?(?:\*\*)?\s*(?:pulo do gato|racioc[ií]nio cl[ií]nico|fundamentação teórica|discussão do caso|comentário do caso|padrão de resposta|resolução detalhada|alternativa correta|por que a letra|análise dos distratores|distratores|alternativas incorretas|gabarito)\b|$)/i,
      ""
    )
    .replace(/(?:\s|<br\s*\/?\>\s*)+$/i, "");
}

/**
 * Guardrail defensivo de sanitização para seções clínicas:
 * Limpa delimitadores residuais órfãos gerados por quebras de cabeçalhos, asteriscos desbalanceados
 * ou pontuações órfãs (ex: '** Incorreta', '**\n', ': ', '- : ') sem mutar ou alterar o conteúdo canônico original.
 */
export function cleanSectionDelimiters(text: string | null | undefined): string {
  if (!text || typeof text !== "string") return "";
  let clean = text.trim();

  // 1. Remove quebras vazias e divisores horizontais residuais no início e no fim
  clean = clean.replace(/^(?:<br\s*\/?>\s*)+/gi, "").trim();
  clean = clean.replace(/^(?:[-*_]{3,}\s*\n+)+/g, "").trim();
  clean = clean.replace(/(?:\s*<br\s*\/?>\s*)+$/gi, "").trim();
  clean = clean.replace(/(?:\n+\s*[-*_]{3,})+$/g, "").trim();

  // 2. Remove delimitadores residuais órfãos no início do bloco:
  // - Linhas que contêm exclusivamente asteriscos ou underscores soltos no topo
  clean = clean.replace(/^[*_]{1,3}\s*\n+/g, "").trim();
  // - Asteriscos duplos/triplos órfãos na mesma linha (ex: '** Incorreta', '** : ')
  clean = clean.replace(/^[*_]{2,3}(?:[^\S\r\n]*[:\-–—])?[^\S\r\n]+/g, "").trim();
  // - Asterisco único órfão com pontuação (ex: '* : ')
  clean = clean.replace(/^[*_](?:[^\S\r\n]*[:\-–—])[^\S\r\n]+/g, "").trim();
  // - Dois-pontos residuais ou traços seguidos de dois-pontos no início (ex: ':', ': ', '- : ')
  clean = clean.replace(/^(?:[:\-–—][^\S\r\n]*[:]+|[:]+)\s*/g, "").trim();

  // 3. Remove delimitadores residuais órfãos no final do bloco:
  clean = clean.replace(/\s+[*_]{1,3}$/g, "").trim();
  clean = clean.replace(/\s*[:]\s*$/g, "").trim();

  return clean;
}

/**
 * Parses structured markdown explanations into distinct semantic sections with defensive sanitization
 */
export function parseExplanation(raw: string | null | undefined, isDiscursive?: boolean): { parsed: ParsedSection; isDiscursiveDetected: boolean } {
  const isDiscursiveDetected = Boolean(isDiscursive);
  if (!raw || typeof raw !== "string" || !raw.trim()) {
    return {
      parsed: { fallbackText: "Nenhum comentário disponível para esta questão." },
      isDiscursiveDetected
    };
  }

  try {
    const clean = withoutReferenceSection(preprocessMarkdown(raw)).trim();
    if (!clean) {
      return {
        parsed: { fallbackText: "Nenhum comentário disponível para esta questão." },
        isDiscursiveDetected
      };
    }

    const detectedDiscursive = Boolean(
      isDiscursive ||
      /DISSERTATIVA|DISCURSIVA|RESPOSTA CURTA/i.test(clean) ||
      /Anote sua principal hipótese/i.test(clean) ||
      /Questão dissertativa/i.test(clean)
    );

    const parsed: ParsedSection = {};

    // 1. Extract Gabarito (tolerante a dois-pontos dentro ou fora de asteriscos e markdown headers)
    const gabaritoMatch = clean.match(/(?:^|\n)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?(?:\*\*)?Gabarito(?:\s+Oficial)?(?:\*\*)?(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)\s*([^\n]+)/i);
    if (gabaritoMatch) {
      const candidate = gabaritoMatch[1].replace(/^[*_~:]+|[*_~:]+$/g, "").trim();
      const isGenericPlaceholder = /^(?:DISSERTATIVA|DISCURSIVA|\(Ver Padrão|Letra\s+[A-E]$|^[A-E]$)/i.test(candidate);
      if (detectedDiscursive) {
        if (!isGenericPlaceholder && !/^(?:DISSERTATIVA|DISCURSIVA)/i.test(candidate)) {
          parsed.gabarito = candidate;
        }
      } else {
        parsed.gabarito = candidate;
      }
    }

    // Helper regex to find header positions (resilient to colons inside/outside asterisks, markdown headers, bullets)
    const distMatch = clean.match(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Análise d[oa]s Distratores(?:[^\n*:]*)?|Distratores|Alternativas Incorretas|Análise das Alternativas Incorretas|Análise das Alternativas Verdadeiras|Alternativas Verdadeiras)(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)\s*/i);
    const corrMatch = clean.match(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Por que a Letra [^\n*:]+|Alternativa Correta(?:\s*\([A-E]\))?|Resposta Correta[^\n*:]*)(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)\s*/i);
    const padraoMatch = clean.match(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:RESPOSTA OBJETIVA(?:[^\n*:]*)?|Padrão de Resposta(?:[^\n*:]*)?|Resposta Esperada|Critérios de Correção)(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)\s*/i);
    const racMatch = clean.match(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Raciocínio Clínico(?:[^\n*:]*)?|Fundamentação Teórica|Discussão do Caso(?:[^\n*:]*)?|Comentário do Caso|Resolução Detalhada(?:[^\n*:]*)?)(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)\s*/i);
    const puloMatch = clean.match(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?(?:💡\s*)?(?:\*\*Pulo[\s_]+do[\s_]+Gato(?:\s*\*\*)?(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?)|Pulo[\s_]+do[\s_]+Gato(?:\*{0,2}\s*:\s*\*{0,2}|:\s*\*{0,2}|\*{0,2}\s*:?))\s*/i);

    // 2. Extract Distratores (Only for Multiple Choice)
    if (!detectedDiscursive && distMatch && distMatch.index !== undefined) {
      const rawDistratores = cleanSectionDelimiters(clean.slice(distMatch.index + distMatch[0].length));
      const isDummyDist = /^[-•*\s]*Revise os critérios que diferenciam as alternativas\.?$/i.test(rawDistratores);
      if (!isDummyDist) {
        const distratorLines = rawDistratores.split(/\n(?=(?:[-•*]\s*(?:\*\*)?Letra\s+[A-E]|(?:\*\*)?Letra\s+[A-E]))/i);

        const distratoresList: Array<{ letter: string; text: string }> = [];
        for (const rawItem of distratorLines) {
          const item = rawItem.trim();
          if (!item || /^[*_:\-–—•\s]+$/.test(item)) continue;

          const m1 = item.match(/^(?:[-•*]\s*)?(?:\*\*)?Letra\s+([A-E](?:\s*(?:,|e)\s*[A-E])?)(?:\*\*)?(?:\s*(\([^)]+\)))?(?:\*{0,2}\s*:\s*\*{0,2}|\*{1,2}|:\s*\*{0,2}|:)?\s*([\s\S]*)$/i);

          if (m1) {
            const letter = m1[1].trim();
            const note = m1[2] ? `**${m1[2].replace(/^[*_()]+|[*_()]+$/g, "")}**: ` : "";
            const text = cleanSectionDelimiters(m1[3]);
            if (text) {
              distratoresList.push({
                letter,
                text: note ? `${note}${text}` : text
              });
            }
          } else if (item.trim() && !/^[-•*\s]*Revise os critérios/i.test(item.trim())) {
            const text = cleanSectionDelimiters(item.replace(/^[-•*]\s*/, ""));
            if (text) {
              distratoresList.push({
                letter: "•",
                text
              });
            }
          }
        }
        if (distratoresList.length > 0) {
          parsed.distratores = distratoresList;
        }
      }
    }

    // 3. Extract Alternativa Correta (Only for Multiple Choice)
    if (!detectedDiscursive && corrMatch && corrMatch.index !== undefined) {
      const endIdx = distMatch && distMatch.index !== undefined && distMatch.index > corrMatch.index ? distMatch.index : clean.length;
      let rawCorr = clean.slice(corrMatch.index + corrMatch[0].length, endIdx).trim();
      rawCorr = rawCorr.replace(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Análise d[oa]s Distratores|Distratores|Alternativas Incorretas)[\s\S]*$/i, "").trim();
      rawCorr = cleanSectionDelimiters(rawCorr);
      const isDummyCorr = /Anote sua principal hipótese|Questão dissertativa|Alternativa indicada no gabarito oficial/i.test(rawCorr);
      if (!isDummyCorr && rawCorr) {
        const letterMatch = corrMatch[0].match(/(?:Letra|\()\s*([A-E](?:\s*(?:,|e)\s*[A-E])*)\b/i) || corrMatch[0].match(/Alternativa\s+Correta\s*([A-E](?:\s*(?:,|e)\s*[A-E])*)\b/i);
        const gabLetter = parsed.gabarito?.match(/(?:Letra|\b)\s*([A-E](?:\s*(?:,|e)\s*[A-E])*)\b/i)?.[1]?.toUpperCase();
        const parsedLetter = letterMatch ? letterMatch[1].toUpperCase() : gabLetter;
        parsed.alternativaCorreta = {
          letter: parsedLetter,
          text: rawCorr
        };
      }
    }

    // 4. Extract Padrão de Resposta Explícito (se presente como seção própria)
    if (padraoMatch && padraoMatch.index !== undefined) {
      let endIdx = clean.length;
      const pIdx = padraoMatch.index;
      const nextCandidates = [corrMatch?.index, distMatch?.index].filter((idx): idx is number => idx !== undefined && idx > pIdx);
      if (nextCandidates.length > 0) {
        endIdx = Math.min(...nextCandidates);
      }
      let padraoText = clean.slice(pIdx + padraoMatch[0].length, endIdx).trim();
      padraoText = cleanSectionDelimiters(padraoText);
      if (padraoText) {
        parsed.padraoResposta = padraoText;
      }
    }

    // 5. Extract Raciocínio Clínico
    if (racMatch && racMatch.index !== undefined) {
      let endIdx = clean.length;
      const rIdx = racMatch.index;
      const nextCandidates = [
        padraoMatch?.index,
        corrMatch?.index,
        distMatch?.index,
      ].filter((idx): idx is number => idx !== undefined && idx > rIdx);
      if (nextCandidates.length > 0) {
        endIdx = Math.min(...nextCandidates);
      }
      let racText = clean.slice(rIdx + racMatch[0].length, endIdx).trim();
      racText = racText.replace(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Por que a Letra [^\n*:]+|Alternativa Correta(?:\s*\([A-E]\))?|Resposta Correta[^\n*:]*|Análise d[oa]s Distratores(?:[^\n*:]*)?|Distratores|Alternativas Incorretas|Padrão de Resposta(?:[^\n*:]*)?)[\s\S]*$/i, "").trim();
      racText = cleanSectionDelimiters(racText);
      if (racText) {
        parsed.raciocinioClinico = racText;
      }
    }

    // 6. Extract Pulo do Gato
    if (puloMatch && puloMatch.index !== undefined) {
      let endIdx = clean.length;
      const puIdx = puloMatch.index;
      const nextCandidates = [
        racMatch?.index,
        padraoMatch?.index,
        corrMatch?.index,
        distMatch?.index,
      ].filter((idx): idx is number => idx !== undefined && idx > puIdx);
      if (nextCandidates.length > 0) {
        endIdx = Math.min(...nextCandidates);
      }
      let puloText = clean.slice(puIdx + puloMatch[0].length, endIdx).trim();
      puloText = cleanSectionDelimiters(puloText);
      if (puloText) {
        parsed.puloDoGato = puloText;
      }
    }

    // Deduplicate: if raciocinioClinico starts with puloDoGato, remove duplicate prefix
    if (parsed.puloDoGato && parsed.raciocinioClinico && parsed.raciocinioClinico.startsWith(parsed.puloDoGato)) {
      parsed.raciocinioClinico = cleanSectionDelimiters(parsed.raciocinioClinico.slice(parsed.puloDoGato.length));
    }

    // Fallback if structure parsing didn't find standard sections or if all extracted sections are empty
    if (!parsed.puloDoGato && !parsed.alternativaCorreta && !parsed.distratores && !parsed.raciocinioClinico && !parsed.padraoResposta) {
      let cleanFallback = clean.replace(/(?:\n|^)\s*(?:[-*+]\s+)?(?:#{1,6}\s+)?\*{0,2}(?:Por que a Letra [^\n*:]+|Alternativa Correta(?:\s*\([A-E]\))?|Resposta Correta[^\n*:]*|Análise d[oa]s Distratores(?:[^\n*:]*)?|Distratores|Alternativas Incorretas)[\s\S]*$/i, "").trim();
      cleanFallback = cleanSectionDelimiters(cleanFallback);
      parsed.fallbackText = cleanFallback || "Nenhum comentário disponível para esta questão.";
    }

    return { parsed, isDiscursiveDetected: detectedDiscursive };
  } catch (err) {
    console.error("Erro defensivo em parseExplanation:", err);
    return {
      parsed: {
        fallbackText: typeof raw === "string" && raw.trim() ? raw.trim() : "Nenhum comentário disponível para esta questão."
      },
      isDiscursiveDetected
    };
  }
}

export function ExplanationViewer({ 
  explanation, 
  correctLetter,
  isDiscursive,
}: ExplanationViewerProps) {
  const [enlargedImage, setEnlargedImage] = useState<string | null>(null);

  const { parsed, isDiscursiveDetected } = useMemo(() => {
    if (!explanation) return { parsed: null, isDiscursiveDetected: Boolean(isDiscursive) };
    return parseExplanation(explanation, isDiscursive);
  }, [explanation, isDiscursive]);

  const renderZoomModal = () => {
    if (!enlargedImage) return null;
    return (
      <div 
        role="dialog"
        aria-modal="true"
        aria-label="Visualização de figura médica ampliada"
        className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
        onClick={() => setEnlargedImage(null)}
      >
        <div className="relative max-w-5xl max-h-[90vh] flex flex-col items-center">
          <button 
            type="button"
            onClick={() => setEnlargedImage(null)}
            className="absolute -top-12 right-0 text-white/80 hover:text-white bg-black/50 p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-full transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            aria-label="Fechar visualização de imagem"
          >
            <X size={24} aria-hidden="true" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img 
            src={enlargedImage} 
            alt="Figura médica explicativa ampliada"
            className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl border border-white/10"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </div>
    );
  };

  if (!explanation || !parsed) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-5 rounded-xl bg-muted/40 border border-border text-muted-foreground">
          <AlertCircle size={18} aria-hidden="true" />
          <span>Nenhum comentário oficial disponível para esta questão.</span>
        </div>
        {renderZoomModal()}
      </div>
    );
  }

  // If structured parsing succeeded
  if (!parsed.fallbackText) {
    return (
      <div className="space-y-5">
        {/* Top Banner: Gabarito Oficial */}
        {parsed.gabarito && (
          <div className={clsx(
            "flex items-start sm:items-center gap-3 px-4 py-3 rounded-2xl shadow-xs transition-all",
            isDiscursiveDetected
              ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-800 dark:text-emerald-200 w-full"
              : "bg-primary/10 border border-primary/20 text-primary w-fit"
          )}>
            <Award size={20} aria-hidden="true" className={clsx("shrink-0 mt-0.5 sm:mt-0", isDiscursiveDetected ? "text-emerald-600 dark:text-emerald-400" : "text-primary")} />
            <div className="flex flex-col sm:flex-row sm:items-baseline sm:gap-2">
              <span className="font-bold text-xs sm:text-sm uppercase tracking-wider opacity-90">
                {isDiscursiveDetected ? "Resposta Esperada pela Banca (Gabarito):" : "Gabarito Oficial:"}
              </span>
              <span className="font-extrabold text-sm sm:text-base underline decoration-2 underline-offset-2 text-foreground">
                {parsed.gabarito}
              </span>
            </div>
          </div>
        )}

        {/* 1. PULO DO GATO (Âncora de Alto Rendimento) */}
        {parsed.puloDoGato && (
          <div className="relative overflow-hidden rounded-2xl bg-amber-500/10 border border-amber-500/25 p-5 md:p-6 text-foreground shadow-sm">
            <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 font-bold text-sm md:text-base uppercase tracking-wider mb-2">
              <Sparkles size={18} aria-hidden="true" className="shrink-0 animate-pulse" />
              <span>Pulo do Gato</span>
            </div>
            <div className="text-foreground text-sm md:text-base leading-relaxed font-medium">
              <FormattedContent content={parsed.puloDoGato} onImageClick={setEnlargedImage} />
            </div>
          </div>
        )}

        {/* 2. PADRÃO DE RESPOSTA DA BANCA (Se seção explícita presente) */}
        {parsed.padraoResposta && (
          <div className="rounded-2xl bg-primary/10 border border-primary/25 p-5 md:p-6 text-foreground shadow-sm">
            <div className="flex items-center gap-2 text-primary font-bold text-sm md:text-base uppercase tracking-wider mb-2">
              <Award size={18} aria-hidden="true" className="shrink-0" />
              <span>Padrão de Resposta Oficial da Banca</span>
            </div>
            <div className="text-foreground text-sm md:text-base leading-relaxed font-medium">
              <FormattedContent content={parsed.padraoResposta} onImageClick={setEnlargedImage} />
            </div>
          </div>
        )}

        {/* 3. RACIOCÍNIO CLÍNICO / RESOLUÇÃO DETALHADA */}
        {parsed.raciocinioClinico && (
          <div className="rounded-2xl bg-blue-500/10 border border-blue-500/20 p-5 md:p-6 text-foreground">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400 font-bold text-sm md:text-base uppercase tracking-wider mb-2">
              <Stethoscope size={18} aria-hidden="true" className="shrink-0" />
              <span>{isDiscursiveDetected ? "Padrão de Resposta da Banca & Comentário" : "Raciocínio Clínico"}</span>
            </div>
            <div className="text-foreground text-sm md:text-base leading-relaxed">
              <FormattedContent content={parsed.raciocinioClinico} onImageClick={setEnlargedImage} />
            </div>
          </div>
        )}

        {/* 4. ALTERNATIVA CORRETA (Apenas questões de múltipla escolha) */}
        {!isDiscursiveDetected && parsed.alternativaCorreta && (
          <div className="rounded-2xl bg-emerald-500/10 border border-emerald-500/25 p-5 md:p-6 text-foreground">
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-bold text-sm md:text-base uppercase tracking-wider mb-2">
              <CheckCircle2 size={18} aria-hidden="true" className="shrink-0" />
              <span>
                Alternativa Correta {parsed.alternativaCorreta.letter ? `(${parsed.alternativaCorreta.letter})` : (correctLetter ? `(${correctLetter})` : "")}
              </span>
            </div>
            <div className="text-foreground text-sm md:text-base leading-relaxed">
              <FormattedContent content={parsed.alternativaCorreta.text} onImageClick={setEnlargedImage} />
            </div>
          </div>
        )}

        {/* 5. ANÁLISE DOS DISTRATORES (Apenas questões de múltipla escolha) */}
        {!isDiscursiveDetected && parsed.distratores && parsed.distratores.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-muted-foreground font-bold text-xs uppercase tracking-wider px-1">
              <XCircle size={14} aria-hidden="true" className="text-rose-500" />
              <span>Análise das Alternativas Incorretas</span>
            </div>
            <div className="grid gap-2.5">
              {parsed.distratores.map((dist, idx) => (
                <div 
                  key={idx} 
                  className="rounded-xl border border-border bg-card/60 p-4 transition-all hover:bg-muted/30"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-6 min-w-6 items-center justify-center rounded-md bg-rose-500/15 text-rose-700 dark:text-rose-400 font-bold text-xs shrink-0 mt-0.5">
                      {dist.letter}
                    </span>
                    <div className="text-sm md:text-base text-foreground leading-relaxed flex-1">
                      <FormattedContent content={dist.text} onImageClick={setEnlargedImage} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {renderZoomModal()}
      </div>
    );
  }

  // Fallback: render formatted raw markdown
  return (
    <div className="space-y-4">
      <div className="text-foreground text-sm md:text-base leading-relaxed">
        <FormattedContent content={parsed.fallbackText || ""} onImageClick={setEnlargedImage} />
      </div>

      {renderZoomModal()}
    </div>
  );
}
