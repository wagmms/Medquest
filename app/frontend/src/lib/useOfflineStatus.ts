"use client";

import { useEffect, useState } from "react";
import { isDeviceOffline, isForcedOffline } from "@/lib/db";

export interface OfflineStatus {
  isOffline: boolean;
  forcedOffline: boolean;
  isAnyOffline: boolean;
}

/**
 * Hook compartilhado para monitorar estado de rede e Modo Plantão forçado.
 * Centraliza os listeners de `online`, `offline` e `forced-offline-changed`.
 */
export function useOfflineStatus(): OfflineStatus {
  const [isOffline, setIsOffline] = useState(false);
  const [forcedOffline, setForcedOffline] = useState(false);

  useEffect(() => {
    const updateStatus = () => {
      setIsOffline(isDeviceOffline());
      setForcedOffline(isForcedOffline());
    };

    updateStatus();
    window.addEventListener("online", updateStatus);
    window.addEventListener("offline", updateStatus);
    window.addEventListener("forced-offline-changed", updateStatus);

    return () => {
      window.removeEventListener("online", updateStatus);
      window.removeEventListener("offline", updateStatus);
      window.removeEventListener("forced-offline-changed", updateStatus);
    };
  }, []);

  return {
    isOffline,
    forcedOffline,
    isAnyOffline: isOffline || forcedOffline,
  };
}
