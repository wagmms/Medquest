"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useUser } from "@clerk/nextjs";
import { AccountModal } from "./AccountModal";
import { OfflineModal } from "./OfflineModal";
import { ThemeToggle } from "./ThemeToggle";
import { useZenMode } from "@/hooks/useZenMode";
import { isDeviceOffline, isForcedOffline } from "@/lib/db";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";
import Image from "next/image";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/buscar", label: "Busca Clínica", icon: "search" },
  { href: "/estudar", label: "Estudar", icon: "menu_book" },
  { href: "/revisao-ativa", label: "Revisão Ativa", icon: "psychology" },
  { href: "/osce", label: "OSCE (2ª Fase)", icon: "stethoscope" },
  { href: "/simulado", label: "Simulados", icon: "description" },
  { href: "/cobertura", label: "Cobertura", icon: "my_location" },
  { href: "/analise", label: "Análise", icon: "analytics" },
  { href: "/planner", label: "Planner", icon: "calendar_month" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, isLoaded } = useUser();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isOfflineOpen, setIsOfflineOpen] = useState(false);
  const [isOffline, setIsOffline] = useState(false);
  const [forcedOffline, setForcedOffline] = useState(false);
  const { isZenMode, toggleZenMode } = useZenMode();

  useEffect(() => {
    const updateOnline = () => {
      setIsOffline(isDeviceOffline());
      setForcedOffline(isForcedOffline());
    };
    updateOnline();
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    window.addEventListener("forced-offline-changed", updateOnline);
    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
      window.removeEventListener("forced-offline-changed", updateOnline);
    };
  }, []);

  return (
    <>
      <aside className="app-sidebar hidden md:flex flex-col bg-surface h-full left-0 w-60 border-r border-line-subtle p-3 gap-3 z-10 select-none">
        {/* LOGO & TITULO CLINICO */}
        <div className="flex items-center gap-2.5 px-3 py-3 border-b border-line-subtle/80">
          <div className="w-8 h-8 rounded-xs bg-ink-primary text-surface flex items-center justify-center shadow-2xs">
            <ClinicalIcon name="local_hospital" className="w-4 h-4 text-canvas" strokeWidth={2.2} />
          </div>
          <div className="flex flex-col">
            <h1 className="font-bold text-sm text-ink-primary tracking-tight">MedQuest</h1>
            <span className="text-[10px] font-mono-lab uppercase tracking-wider text-ink-muted">Clinical Workspace</span>
          </div>
        </div>

        {/* NAVEGACAO PRINCIPAL */}
        <nav className="flex-1 flex flex-col gap-1 overflow-y-auto px-1 py-1" aria-label="Navegação principal">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-2.5 py-2 px-2.5 rounded-xs transition-colors text-xs font-medium",
                  isActive 
                    ? "bg-elevated text-ink-primary font-semibold border border-line-subtle shadow-2xs" 
                    : "text-ink-secondary hover:bg-elevated/60 hover:text-ink-primary"
                )}
              >
                <ClinicalIcon 
                  name={item.icon} 
                  className={clsx("w-4 h-4 shrink-0", isActive ? "text-accent" : "text-ink-muted")} 
                  strokeWidth={isActive ? 2.1 : 1.75} 
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* TELEMETRIA & RODAPE */}
        <div className="mt-auto flex flex-col gap-2 pt-2 border-t border-line-subtle/80">
          <div className="flex items-center justify-between gap-1 px-1">
            <button
              onClick={() => setIsOfflineOpen(true)}
              className={clsx(
                "flex items-center gap-1.5 px-2 py-1.5 rounded-xs border transition-colors text-left flex-1 cursor-pointer",
                isOffline || forcedOffline
                  ? "bg-warning/15 border-warning/40 text-warning font-semibold"
                  : "border-line-subtle text-ink-secondary hover:bg-elevated hover:text-ink-primary"
              )}
              title={forcedOffline ? "Modo Plantão Forçado Ativo" : isOffline ? "Modo Plantão (Offline Ativo)" : "Abrir Modo Plantão (Offline)"}
              aria-label={forcedOffline ? "Modo Plantão Forçado Ativo" : isOffline ? "Modo Plantão Offline Ativo" : "Abrir Modo Plantão"}
            >
              <ClinicalIcon name={isOffline || forcedOffline ? "cloud_off" : "cloud_download"} className="w-3.5 h-3.5 shrink-0" />
              <span className="text-[11px] font-mono-lab font-medium truncate">
                {forcedOffline ? "Plantão (F)" : isOffline ? "Offline" : "Plantão"}
              </span>
            </button>

            <button
              onClick={toggleZenMode}
              className="flex items-center justify-center p-1.5 rounded-xs border border-line-subtle text-ink-secondary hover:bg-elevated hover:text-ink-primary transition-colors cursor-pointer"
              title={isZenMode ? "Sair do Modo Zen (Z)" : "Entrar no Modo Zen (Z)"}
              aria-label={isZenMode ? "Sair do modo Zen" : "Entrar no modo Zen"}
              aria-pressed={isZenMode}
            >
              <ClinicalIcon name={isZenMode ? "fullscreen_exit" : "fullscreen"} className="w-3.5 h-3.5" />
            </button>

            <div className="scale-90 opacity-85 hover:opacity-100 transition-opacity">
              <ThemeToggle />
            </div>
          </div>
          
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-2.5 py-2 rounded-xs border border-line-subtle hover:bg-elevated transition-colors justify-between w-full text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-accent"
            aria-label="Minha Conta"
          >
            <div className="flex items-center gap-2 min-w-0">
              {isLoaded && user?.imageUrl ? (
                <div className="relative w-5 h-5 rounded-full overflow-hidden flex-shrink-0 ring-1 ring-line-subtle">
                  <Image src={user.imageUrl} alt="Avatar" fill sizes="20px" className="object-cover" />
                </div>
              ) : (
                <div className="w-5 h-5 rounded-full bg-elevated border border-line-subtle flex items-center justify-center flex-shrink-0">
                  <ClinicalIcon name="person" className="w-3 h-3 text-ink-muted" />
                </div>
              )}
              <span className="text-xs font-medium text-ink-primary truncate">
                {isLoaded ? (user?.firstName || "Conta") : "Conta"}
              </span>
            </div>
            <ClinicalIcon name="more_horiz" className="w-3.5 h-3.5 text-ink-muted opacity-60" />
          </button>
        </div>
      </aside>
      
      <AccountModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      <OfflineModal isOpen={isOfflineOpen} onClose={() => setIsOfflineOpen(false)} />
    </>
  );
}
