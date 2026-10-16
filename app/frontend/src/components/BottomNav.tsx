"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { 
  LayoutDashboard, 
  BookOpen, 
  BrainCircuit, 
  Stethoscope, 
  Menu as MenuIcon, 
  X, 
  Search, 
  FileText, 
  Target, 
  BarChart3, 
  Calendar,
  CloudOff,
  CloudDownload,
  Moon,
  Sun,
  Maximize2,
  Minimize2
} from "lucide-react";
import { useZenMode } from "@/hooks/useZenMode";
import { ThemeToggle } from "./ThemeToggle";
import { OfflineModal } from "./OfflineModal";
import { AccountModal } from "./AccountModal";
import { isDeviceOffline, isForcedOffline } from "@/lib/db";

const PRIMARY_BOTTOM_ITEMS = [
  { href: "/", label: "Cockpit", icon: LayoutDashboard },
  { href: "/estudar", label: "Estudar", icon: BookOpen },
  { href: "/revisao-ativa", label: "FSRS", icon: BrainCircuit },
  { href: "/osce", label: "OSCE", icon: Stethoscope },
];

const MORE_NAV_ITEMS = [
  { href: "/buscar", label: "Busca Clínica", icon: Search },
  { href: "/simulado", label: "Simulados", icon: FileText },
  { href: "/cobertura", label: "Matriz de Cobertura", icon: Target },
  { href: "/analise", label: "Análise de Desempenho", icon: BarChart3 },
  { href: "/planner", label: "Planner Anual", icon: Calendar },
];

export function BottomNav() {
  const pathname = usePathname();
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [isOfflineOpen, setIsOfflineOpen] = useState(false);
  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const { isZenMode, toggleZenMode } = useZenMode();

  const isOffline = typeof window !== "undefined" ? isDeviceOffline() : false;
  const forcedOffline = typeof window !== "undefined" ? isForcedOffline() : false;

  return (
    <>
      {/* DRAWER "MAIS" PARA ROTAS COMPLEMENTARES NO MOBILE */}
      {isMoreOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 md:hidden animate-in fade-in duration-150"
          onClick={() => setIsMoreOpen(false)}
        />
      )}

      {isMoreOpen && (
        <aside
          role="dialog"
          aria-modal="true"
          aria-label="Menu complementar"
          className="fixed bottom-16 left-0 right-0 max-h-[70vh] bg-surface border-t border-line-subtle z-50 md:hidden flex flex-col shadow-xl animate-in slide-in-from-bottom duration-200"
        >
          <div className="flex items-center justify-between p-3.5 border-b border-line-subtle">
            <span className="text-xs font-mono-lab font-bold uppercase tracking-wider text-ink-secondary">
              Navegação Completa
            </span>
            <button
              onClick={() => setIsMoreOpen(false)}
              className="p-1 rounded text-ink-muted hover:text-ink-primary hover:bg-elevated"
              aria-label="Fechar"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="overflow-y-auto p-2 space-y-1">
            {MORE_NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setIsMoreOpen(false)}
                  className={clsx(
                    "flex items-center gap-3 px-3 py-2.5 rounded-sm text-xs font-medium transition-colors",
                    isActive
                      ? "bg-elevated text-accent font-semibold border-l-2 border-accent"
                      : "text-ink-secondary hover:bg-elevated hover:text-ink-primary"
                  )}
                >
                  <Icon className="w-4 h-4 shrink-0" strokeWidth={1.8} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="p-3 border-t border-line-subtle flex items-center justify-between gap-2 bg-elevated/50">
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={toggleZenMode}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-xs border border-line-subtle text-[11px] font-mono-lab text-ink-secondary hover:text-ink-primary"
              >
                {isZenMode ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                <span>{isZenMode ? "Sair Zen" : "Zen"}</span>
              </button>
            </div>

            <button
              onClick={() => {
                setIsMoreOpen(false);
                setIsOfflineOpen(true);
              }}
              className={clsx(
                "flex items-center gap-1.5 px-2.5 py-1.5 rounded-xs border text-[11px] font-mono-lab font-semibold",
                isOffline || forcedOffline
                  ? "bg-warning/15 border-warning/40 text-warning"
                  : "border-line-subtle text-ink-secondary hover:text-ink-primary"
              )}
            >
              {isOffline || forcedOffline ? <CloudOff className="w-3.5 h-3.5" /> : <CloudDownload className="w-3.5 h-3.5" />}
              <span>Plantão</span>
            </button>
          </div>
        </aside>
      )}

      {/* BARRA FIXA DE POLEGAR INFERIOR (THUMB-ZONE) */}
      <nav
        aria-label="Navegação móvel"
        className="fixed bottom-0 left-0 right-0 z-30 md:hidden bg-surface/95 backdrop-blur-md border-t border-line-subtle pb-[env(safe-area-inset-bottom,0px)] shadow-lg"
      >
        <div className="flex items-center justify-around h-14 px-1 max-w-lg mx-auto">
          {PRIMARY_BOTTOM_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex flex-col items-center justify-center flex-1 h-full py-1 gap-0.5 text-[10px] font-medium transition-colors relative",
                  isActive
                    ? "text-accent font-semibold"
                    : "text-ink-muted hover:text-ink-primary"
                )}
              >
                {isActive && (
                  <span className="absolute top-0 w-8 h-0.5 bg-accent rounded-full" />
                )}
                <Icon className="w-4 h-4" strokeWidth={isActive ? 2.2 : 1.75} />
                <span className="tracking-tight">{item.label}</span>
              </Link>
            );
          })}

          {/* BOTÃO MAIS */}
          <button
            onClick={() => setIsMoreOpen(!isMoreOpen)}
            className={clsx(
              "flex flex-col items-center justify-center flex-1 h-full py-1 gap-0.5 text-[10px] font-medium transition-colors cursor-pointer",
              isMoreOpen || MORE_NAV_ITEMS.some((i) => i.href === pathname)
                ? "text-accent font-semibold"
                : "text-ink-muted hover:text-ink-primary"
            )}
            aria-label="Mais opções"
            aria-expanded={isMoreOpen}
          >
            <MenuIcon className="w-4 h-4" strokeWidth={1.75} />
            <span className="tracking-tight">Mais</span>
          </button>
        </div>
      </nav>

      <OfflineModal isOpen={isOfflineOpen} onClose={() => setIsOfflineOpen(false)} />
      <AccountModal isOpen={isAccountOpen} onClose={() => setIsAccountOpen(false)} />
    </>
  );
}
