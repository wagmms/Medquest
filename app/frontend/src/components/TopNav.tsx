"use client";

import { useEffect, useRef, useState } from "react";
import { useUser } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AccountModal } from "./AccountModal";
import { OfflineModal } from "./OfflineModal";
import { ThemeToggle } from "./ThemeToggle";
import { useZenMode } from "@/hooks/useZenMode";
import Image from "next/image";
import clsx from "clsx";
import { isDeviceOffline, isForcedOffline } from "@/lib/db";
import { usePwaInstall } from "@/hooks/usePwaInstall";

import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

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

export default function TopNav() {
  const { user, isLoaded } = useUser();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isOfflineOpen, setIsOfflineOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { isZenMode, toggleZenMode } = useZenMode();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  const handleNavClick = (e: React.MouseEvent, href: string) => {
    e.preventDefault();
    setIsMobileMenuOpen(false);
    router.push(href);
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isMobileMenuOpen && event.key === "Escape") {
        setIsMobileMenuOpen(false);
        return;
      }

      const tag = (event.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (event.key.toLowerCase() === "z" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        toggleZenMode();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleZenMode, isMobileMenuOpen]);

  // Focus trap, focus restoration and background scroll lock.
  useEffect(() => {
    if (!isMobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    const opener = menuButtonRef.current;
    document.body.style.overflow = "hidden";
    const drawer = drawerRef.current;
    const controls = () => Array.from(drawer?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])') || []);
    controls()[0]?.focus();
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = controls();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", trapFocus);
    return () => {
      document.removeEventListener("keydown", trapFocus);
      document.body.style.overflow = previousOverflow;
      opener?.focus();
    };
  }, [isMobileMenuOpen]);

  const [isOffline, setIsOffline] = useState(false);
  const [forcedOffline, setForcedOffline] = useState(false);
  const { isInstallable, installApp } = usePwaInstall();

  useEffect(() => {
    const updateOnlineStatus = () => {
      setIsOffline(isDeviceOffline());
      setForcedOffline(isForcedOffline());
    };
    updateOnlineStatus();
    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    window.addEventListener("forced-offline-changed", updateOnlineStatus);
    return () => {
      window.removeEventListener("online", updateOnlineStatus);
      window.removeEventListener("offline", updateOnlineStatus);
      window.removeEventListener("forced-offline-changed", updateOnlineStatus);
    };
  }, []);

  return (
    <>
      <header className="app-top-nav md:hidden flex justify-between items-center w-full px-3.5 sm:px-4 py-2 h-14 bg-surface border-b border-line-subtle z-10 sticky top-0 transition-colors max-w-full overflow-hidden select-none">
        <h1 className="font-semibold text-base text-ink-primary tracking-tight flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-xs bg-ink-primary text-surface flex items-center justify-center shadow-2xs shrink-0">
            <ClinicalIcon name="local_hospital" className="w-3.5 h-3.5 text-canvas" strokeWidth={2.2} />
          </div>
          <span className="truncate">MedQuest</span>
        </h1>
        <div className="flex items-center gap-1.5 shrink-0">
          {isInstallable && (
            <button
              onClick={() => void installApp()}
              className="flex items-center justify-center p-1.5 rounded-xs text-accent hover:bg-elevated transition-colors cursor-pointer shrink-0"
              title="Instalar MedQuest no Android"
              aria-label="Instalar MedQuest no dispositivo"
            >
              <ClinicalIcon name="cloud_download" className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => setIsOfflineOpen(true)}
            className={clsx(
              "flex items-center gap-1 px-2 py-1 rounded-xs text-xs font-mono-lab font-semibold transition-colors cursor-pointer shrink-0 border",
              isOffline || forcedOffline
                ? "bg-warning/20 border-warning/40 text-warning animate-pulse"
                : "border-line-subtle text-ink-secondary hover:bg-elevated hover:text-ink-primary"
            )}
            title={forcedOffline ? "Modo Plantão Forçado Ativo" : isOffline ? "Você está no Modo Plantão (Offline)" : "Abrir Modo Plantão (Offline)"}
            aria-label={forcedOffline ? "Modo Plantão Forçado Ativo" : isOffline ? "Modo Plantão Offline Ativo" : "Abrir Modo Plantão"}
          >
            <ClinicalIcon name={isOffline || forcedOffline ? "cloud_off" : "cloud_download"} className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[11px] hidden min-[360px]:inline">{forcedOffline ? "Plantão" : isOffline ? "Offline" : "Plantão"}</span>
          </button>
          <button 
            ref={menuButtonRef}
            onClick={() => setIsMobileMenuOpen(true)}
            className="text-ink-secondary hover:bg-elevated rounded-xs p-1.5 transition-colors flex items-center justify-center cursor-pointer shrink-0 border border-line-subtle"
            aria-label="Abrir menu principal"
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-navigation-drawer"
          >
            <ClinicalIcon name="menu" className="w-4 h-4" />
          </button>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="relative w-7 h-7 rounded-full bg-elevated border border-line-subtle overflow-hidden shadow-2xs flex items-center justify-center cursor-pointer hover:opacity-85 transition-opacity focus:outline-none focus:ring-1 focus:ring-accent shrink-0 ml-0.5"
            aria-label="Abrir minha conta"
          >
            {isLoaded && user?.imageUrl ? (
              <Image src={user.imageUrl} alt="Avatar" fill sizes="28px" className="object-cover" />
            ) : (
              <ClinicalIcon name="person" className="w-3.5 h-3.5 text-ink-muted" />
            )}
          </button>
        </div>
      </header>
      
      {/* Mobile Drawer Overlay */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 md:hidden transition-opacity"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}
      
      {/* Mobile Drawer */}
      {isMobileMenuOpen && <div
        ref={drawerRef}
        id="mobile-navigation-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-menu-title"
        className="fixed top-0 left-0 h-full w-[min(20rem,85vw)] bg-surface border-r border-line-subtle z-50 shadow-2xl md:hidden flex flex-col pt-[env(safe-area-inset-top,0px)] pb-[env(safe-area-inset-bottom,0px)]"
      >
        <div className="flex items-center justify-between p-3.5 border-b border-line-subtle">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-xs bg-ink-primary text-surface flex items-center justify-center shadow-2xs">
              <ClinicalIcon name="local_hospital" className="w-3.5 h-3.5 text-canvas" strokeWidth={2.2} />
            </div>
            <h2 id="mobile-menu-title" className="font-semibold text-base text-ink-primary tracking-tight">Menu Clínico</h2>
          </div>
          <button 
            id="mobile-menu-close"
            onClick={() => setIsMobileMenuOpen(false)}
            className="p-1.5 rounded-xs hover:bg-elevated transition-colors text-ink-secondary cursor-pointer"
            aria-label="Fechar menu"
          >
            <ClinicalIcon name="close" className="w-4 h-4" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto p-3 space-y-1" aria-label="Navegação principal">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link 
                key={item.href} 
                href={item.href}
                onClick={(e) => handleNavClick(e, item.href)}
                aria-current={isActive ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-2.5 px-3 py-2 rounded-xs transition-colors text-xs font-medium",
                  isActive 
                    ? "bg-elevated text-ink-primary font-semibold border border-line-subtle shadow-2xs" 
                    : "text-ink-secondary hover:bg-elevated hover:text-ink-primary"
                )}
              >
                <ClinicalIcon name={item.icon} className={clsx("w-4 h-4", isActive ? "text-accent" : "text-ink-muted")} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        {/* Controles secundários movidos para o rodapé do menu mobile */}
        <div className="p-3 border-t border-line-subtle flex items-center justify-between gap-2 bg-elevated/40">
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button
              onClick={toggleZenMode}
              className="text-ink-secondary hover:bg-elevated rounded-xs p-1.5 text-xs font-mono-lab flex items-center gap-1.5 cursor-pointer border border-line-subtle"
              title={isZenMode ? "Sair do Modo Zen" : "Entrar no Modo Zen (Z)"}
            >
              <ClinicalIcon name={isZenMode ? "fullscreen_exit" : "fullscreen"} className="w-3.5 h-3.5" />
              <span>{isZenMode ? "Sair Zen" : "Modo Zen"}</span>
            </button>
          </div>
          <button
            onClick={() => {
              setIsMobileMenuOpen(false);
              setIsOfflineOpen(true);
            }}
            className="flex items-center gap-1 text-xs text-accent font-mono-lab font-bold px-2.5 py-1.5 rounded-xs border border-line-subtle hover:bg-elevated transition-colors cursor-pointer"
          >
            <ClinicalIcon name="cloud_download" className="w-3.5 h-3.5" />
            <span>Plantão</span>
          </button>
        </div>
      </div>}

      <AccountModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      <OfflineModal isOpen={isOfflineOpen} onClose={() => setIsOfflineOpen(false)} />
    </>
  );
}
