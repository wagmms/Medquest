"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

interface AuthSyncProps {
  ssrAuthenticated: boolean;
  children: React.ReactNode;
}

export function AuthSync({ ssrAuthenticated, children }: AuthSyncProps) {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const hasRefreshedRef = useRef(false);
  const [, setIsSyncing] = useState(false);

  useEffect(() => {
    // If the server thought we were logged out, but the Clerk client SDK has loaded
    // and confirmed an active session, trigger an immediate refresh to re-evaluate SSR.
    if (!ssrAuthenticated && isLoaded && isSignedIn && !hasRefreshedRef.current) {
      hasRefreshedRef.current = true;
      setIsSyncing(true);
      router.refresh();

      // Fallback in case router.refresh doesn't re-render the root layout,
      // guarded against infinite reload loops across continuous renders:
      const alreadyReloaded = typeof window !== "undefined" && sessionStorage.getItem("medquest_auth_synced") === "1";
      if (!alreadyReloaded) {
        const timer = setTimeout(() => {
          if (typeof window !== "undefined") {
            sessionStorage.setItem("medquest_auth_synced", "1");
            window.location.reload();
          }
        }, 1500);
        return () => clearTimeout(timer);
      }
    }
  }, [ssrAuthenticated, isLoaded, isSignedIn, router]);

  useEffect(() => {
    if (ssrAuthenticated && typeof window !== "undefined") {
      sessionStorage.removeItem("medquest_auth_synced");
    }
  }, [ssrAuthenticated]);

  // If the client is already confirmed signed-in while SSR rendered the sign-in form,
  // show a clean loading state instead of a confusing stuck sign-in card.
  if (!ssrAuthenticated && isLoaded && isSignedIn) {
    return (
      <div className="flex w-full h-full items-center justify-center p-8 bg-background relative">
        <div
          className="absolute inset-0 bg-primary/5"
          style={{
            backgroundImage: "radial-gradient(circle, var(--primary) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
            opacity: 0.2,
          }}
        />
        <div className="relative z-10 flex flex-col items-center max-w-md w-full bg-card p-8 md:p-12 rounded-2xl shadow-xl border border-border text-center animate-in fade-in duration-300">
          <div className="w-16 h-16 bg-primary/20 text-primary rounded-2xl flex items-center justify-center mb-6 shadow-sm animate-pulse">
            <span className="material-symbols-outlined text-4xl" data-icon="stethoscope">
              stethoscope
            </span>
          </div>
          <h2 className="text-xl font-bold mb-2">Entrando no MedQuest...</h2>
          <p className="text-sm text-muted-foreground">Sincronizando sua sessão com o servidor.</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
