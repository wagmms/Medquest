"use client";

import React from "react";
import { Maximize } from "lucide-react";
import clsx from "clsx";
import { normalizeImageSrc } from "@/components/FormattedContent";

export interface AlternativeContentProps {
  content: string;
  isEliminated?: boolean;
  onImageClick?: (url: string) => void;
  className?: string;
}

/**
 * Retorna uma versão em texto puro e amigável da alternativa para leitores de tela e aria-labels,
 * substituindo tags HTML/Markdown de imagem por descrições legíveis.
 */
export function getAlternativePlainText(content: string | null | undefined): string {
  if (!content) return "";
  const clean = content
    .replace(/<img\b[^>]*\balt=['"]([^'"]+)['"][^>]*>/gi, " [Imagem: $1] ")
    .replace(/<img\b[^>]*>/gi, " [Imagem] ")
    .replace(/!\[(.*?)\]\(.*?\)/gi, (_, alt) => (alt ? ` [Imagem: ${alt}] ` : " [Imagem] "))
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&gt;/gi, ">")
    .replace(/&lt;/gi, "<")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
  return clean || "Alternativa com imagem médica";
}

/**
 * Renderiza trechos inline de texto da alternativa com suporte a formatação médica simples
 * (negrito, itálico, entidades HTML).
 */
function renderInlineText(text: string): React.ReactNode {
  if (!text) return null;

  // Substitui entidades HTML comuns
  let sanitized = text
    .replace(/&nbsp;/gi, " ")
    .replace(/&gt;/gi, ">")
    .replace(/&lt;/gi, "<")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&amp;/gi, "&");

  // Normaliza tags HTML de negrito e itálico para Markdown
  sanitized = sanitized
    .replace(/<(?:strong|b)\b[^>]*>([\s\S]*?)<\/(?:strong|b)>/gi, "**$1**")
    .replace(/<(?:em|i)\b[^>]*>([\s\S]*?)<\/(?:em|i)>/gi, "*$1*")
    .replace(/<\/?(?:span|p|div|font)[^>]*>/gi, "");

  // Quebra por negrito (**...**) ou itálico (*...*)
  const tokens = sanitized.split(/(\*\*.*?\*\*|\*[^\*]+\*)/g);

  return tokens.map((part, idx) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      return (
        <strong key={idx} className="font-bold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      return (
        <em key={idx} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

/**
 * Componente unificado para renderizar o conteúdo de alternativas do MedQuest.
 * Suporta perfeitamente:
 * 1. Imagens puras ou embutidas em HTML (<img src="...">) e Markdown (![](url))
 * 2. Visualização clínica com zoom em modal (ImageViewer)
 * 3. Estado riscado/eliminado com opacidade e filtro monocromático suave
 * 4. Texto puro e formatado com tipografia médica precisa
 */
export const AlternativeContent: React.FC<AlternativeContentProps> = ({
  content,
  isEliminated = false,
  onImageClick,
  className = "",
}) => {
  if (!content) return null;

  // Detecta se há imagens (HTML ou Markdown)
  const tokenRegex = /(<img\b[^>]*\bsrc\s*=\s*['"][^'"]+['"][^>]*>|!\[.*?\]\(.*?\))/gi;
  const parts = content.split(tokenRegex);

  // Se for texto simples sem imagem
  if (parts.length === 1 && !/<img\b/i.test(content) && !/!\[.*?\]\(.*?\)/.test(content)) {
    return (
      <span className={clsx("inline-block", isEliminated && "line-through text-ink-muted/70 decoration-ink-muted/50", className)}>
        {renderInlineText(content)}
      </span>
    );
  }

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>, originalSrc: string) => {
    const target = e.currentTarget;
    if (!target.dataset.triedFallback && originalSrc.includes("medcof-assets")) {
      target.dataset.triedFallback = "true";
      const filename = originalSrc.split("/").pop();
      if (filename) {
        target.src = `/api/images/medcof/usp_sp/${filename}`;
      }
    }
  };

  return (
    <div className={clsx("flex flex-col gap-1.5 w-full", className)}>
      {parts.map((part, idx) => {
        if (!part) return null;

        // Caso 1: Imagem HTML (<img src="..." ...>)
        const htmlMatch = part.match(/<img\b[^>]*\bsrc\s*=\s*['"]([^'"]+)['"][^>]*>/i);
        if (htmlMatch) {
          const rawSrc = htmlMatch[1];
          const normalizedSrc = normalizeImageSrc(rawSrc);
          const altMatch = part.match(/alt\s*=\s*['"]([^'"]+)['"]/i);
          const altText = altMatch ? altMatch[1] : "Figura médica da alternativa";

          return (
            <div
              key={idx}
              className={clsx(
                "relative group inline-block max-w-full my-0.5 rounded-sm border border-line-subtle/60 bg-canvas/50 overflow-hidden shadow-2xs self-start",
                isEliminated && "opacity-40 grayscale hover:opacity-70 transition-opacity"
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={normalizedSrc}
                alt={altText}
                loading="lazy"
                onError={(e) => handleImageError(e, normalizedSrc)}
                className="max-h-40 sm:max-h-48 md:max-h-56 w-auto max-w-full object-contain p-1 transition-transform duration-200 group-hover:scale-[1.01]"
              />

              {onImageClick && (
                <button
                  type="button"
                  title="Ampliar imagem da alternativa"
                  aria-label="Ampliar imagem da alternativa"
                  onClick={(e) => {
                    e.stopPropagation();
                    onImageClick(normalizedSrc);
                  }}
                  className="absolute top-1.5 right-1.5 p-1 rounded-xs bg-surface/90 hover:bg-surface text-ink-muted hover:text-ink shadow-xs border border-line-subtle opacity-80 group-hover:opacity-100 transition-opacity cursor-zoom-in focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                >
                  <Maximize size={14} aria-hidden="true" />
                </button>
              )}
            </div>
          );
        }

        // Caso 2: Imagem Markdown (![alt](url))
        const mdMatch = part.match(/^!\[(.*?)\]\((.*?)\)$/);
        if (mdMatch) {
          const altText = mdMatch[1] || "Figura médica da alternativa";
          const rawSrc = mdMatch[2];
          const normalizedSrc = normalizeImageSrc(rawSrc);

          return (
            <div
              key={idx}
              className={clsx(
                "relative group inline-block max-w-full my-0.5 rounded-sm border border-line-subtle/60 bg-canvas/50 overflow-hidden shadow-2xs self-start",
                isEliminated && "opacity-40 grayscale hover:opacity-70 transition-opacity"
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={normalizedSrc}
                alt={altText}
                loading="lazy"
                onError={(e) => handleImageError(e, normalizedSrc)}
                className="max-h-40 sm:max-h-48 md:max-h-56 w-auto max-w-full object-contain p-1 transition-transform duration-200 group-hover:scale-[1.01]"
              />

              {onImageClick && (
                <button
                  type="button"
                  title="Ampliar imagem da alternativa"
                  aria-label="Ampliar imagem da alternativa"
                  onClick={(e) => {
                    e.stopPropagation();
                    onImageClick(normalizedSrc);
                  }}
                  className="absolute top-1.5 right-1.5 p-1 rounded-xs bg-surface/90 hover:bg-surface text-ink-muted hover:text-ink shadow-xs border border-line-subtle opacity-80 group-hover:opacity-100 transition-opacity cursor-zoom-in focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                >
                  <Maximize size={14} aria-hidden="true" />
                </button>
              )}
            </div>
          );
        }

        // Caso 3: Texto acompanhante
        const trimmed = part.trim();
        if (!trimmed) return null;

        return (
          <span
            key={idx}
            className={clsx(
              "leading-relaxed",
              isEliminated && "line-through text-ink-muted/70 decoration-ink-muted/50"
            )}
          >
            {renderInlineText(part)}
          </span>
        );
      })}
    </div>
  );
};
