"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export interface WakeLockHook {
  isSupported: boolean;
  isActive: boolean;
  requestWakeLock: () => Promise<boolean>;
  releaseWakeLock: () => Promise<void>;
  toggleWakeLock: () => Promise<void>;
}

export function useWakeLock(autoAcquire: boolean = false): WakeLockHook {
  const isSupported = typeof navigator !== "undefined" && "wakeLock" in navigator;
  const [isActive, setIsActive] = useState(false);
  const wakeLockSentinelRef = useRef<WakeLockSentinel | null>(null);
  const shouldBeActiveRef = useRef<boolean>(autoAcquire);

  const releaseWakeLock = useCallback(async () => {
    shouldBeActiveRef.current = false;
    if (wakeLockSentinelRef.current) {
      try {
        await wakeLockSentinelRef.current.release();
      } catch (err) {
        console.warn("[WakeLock] Erro ao liberar Screen Wake Lock:", err);
      } finally {
        wakeLockSentinelRef.current = null;
        setIsActive(false);
      }
    }
  }, []);

  const requestWakeLock = useCallback(async (): Promise<boolean> => {
    if (typeof navigator === "undefined" || !("wakeLock" in navigator)) {
      return false;
    }

    try {
      shouldBeActiveRef.current = true;
      if (wakeLockSentinelRef.current && !wakeLockSentinelRef.current.released) {
        setIsActive(true);
        return true;
      }

      const sentinel = await navigator.wakeLock.request("screen");
      wakeLockSentinelRef.current = sentinel;
      setIsActive(true);

      sentinel.addEventListener("release", () => {
        if (!shouldBeActiveRef.current) {
          wakeLockSentinelRef.current = null;
          setIsActive(false);
        }
      });

      return true;
    } catch (err) {
      console.warn("[WakeLock] Falha ao solicitar Screen Wake Lock:", err);
      wakeLockSentinelRef.current = null;
      setIsActive(false);
      return false;
    }
  }, []);

  const toggleWakeLock = useCallback(async () => {
    if (isActive) {
      await releaseWakeLock();
    } else {
      await requestWakeLock();
    }
  }, [isActive, releaseWakeLock, requestWakeLock]);

  // Re-acquire wake lock if tab was blurred/minimized and comes back to visible
  useEffect(() => {
    if (!isSupported) return;

    const handleVisibilityChange = async () => {
      if (document.visibilityState === "visible" && shouldBeActiveRef.current) {
        await requestWakeLock();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isSupported, requestWakeLock]);

  // Auto-acquire on mount if requested
  useEffect(() => {
    shouldBeActiveRef.current = autoAcquire;
    if (!autoAcquire || typeof navigator === "undefined" || !("wakeLock" in navigator)) {
      return;
    }

    let cancelled = false;
    const acquire = async () => {
      try {
        const sentinel = await navigator.wakeLock.request("screen");
        if (cancelled) {
          void sentinel.release().catch(() => {});
          return;
        }
        wakeLockSentinelRef.current = sentinel;
        setIsActive(true);

        sentinel.addEventListener("release", () => {
          if (!shouldBeActiveRef.current) {
            wakeLockSentinelRef.current = null;
            setIsActive(false);
          }
        });
      } catch (err) {
        console.warn("[WakeLock] Falha ao auto-solicitar Screen Wake Lock:", err);
      }
    };

    void acquire();

    return () => {
      cancelled = true;
      if (wakeLockSentinelRef.current) {
        void wakeLockSentinelRef.current.release().catch(() => {});
        wakeLockSentinelRef.current = null;
      }
    };
  }, [autoAcquire]);

  return {
    isSupported,
    isActive,
    requestWakeLock,
    releaseWakeLock,
    toggleWakeLock,
  };
}
