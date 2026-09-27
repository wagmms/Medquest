"use client";

import { useSyncExternalStore, useCallback } from "react";

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt(): Promise<void>;
}

let deferredPrompt: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();

function emitChange() {
  listeners.forEach((listener) => listener());
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e: Event) => {
    e.preventDefault();
    deferredPrompt = e as BeforeInstallPromptEvent;
    emitChange();
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    emitChange();
  });
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

function checkIsStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

// Server snapshot
const serverSnapshot = {
  isInstallable: false,
  isInstalled: false,
};

let lastSnapshot = serverSnapshot;
function getCachedSnapshot() {
  const isInstalled = checkIsStandalone();
  const isInstallable = deferredPrompt !== null && !isInstalled;

  if (
    isInstallable !== lastSnapshot.isInstallable ||
    isInstalled !== lastSnapshot.isInstalled
  ) {
    lastSnapshot = { isInstallable, isInstalled };
  }
  return lastSnapshot;
}

export function usePwaInstall() {
  const state = useSyncExternalStore(subscribe, getCachedSnapshot, () => serverSnapshot);

  const installApp = useCallback(async (): Promise<boolean> => {
    if (!deferredPrompt) return false;

    try {
      await deferredPrompt.prompt();
      const choiceResult = await deferredPrompt.userChoice;
      if (choiceResult.outcome === "accepted") {
        deferredPrompt = null;
        emitChange();
        return true;
      }
      return false;
    } catch (err) {
      console.warn("[PWA] Erro ao disparar prompt de instalação:", err);
      return false;
    }
  }, []);

  return {
    isInstallable: state.isInstallable,
    isInstalled: state.isInstalled,
    installApp,
  };
}
