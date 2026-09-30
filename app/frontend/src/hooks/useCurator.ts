"use client";

import { useEffect, useState } from "react";
import { useUser } from "@clerk/nextjs";
import { api } from "@/lib/api";
import { AuthMeResponse } from "@/types/api";

let cachedResult: { userId: string | null; data: AuthMeResponse } | null = null;
let pendingPromise: Promise<AuthMeResponse> | null = null;

export function useCurator() {
  const { user, isLoaded } = useUser();
  const currentUserId = user?.id ?? null;

  const [data, setData] = useState<{ isCurator: boolean; email: string | null } | null>(() => {
    if (cachedResult && cachedResult.userId === currentUserId) {
      return { isCurator: cachedResult.data.is_curator, email: cachedResult.data.email };
    }
    return null;
  });

  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (!isLoaded) return true;
    if (!user) return false;
    if (cachedResult && cachedResult.userId === currentUserId) return false;
    return true;
  });

  useEffect(() => {
    if (!isLoaded || !user) {
      return;
    }

    if (cachedResult && cachedResult.userId === currentUserId) {
      return;
    }

    let isMounted = true;

    const promise = pendingPromise || (pendingPromise = api.auth.getMe()
      .then((res) => {
        cachedResult = { userId: currentUserId, data: res };
        pendingPromise = null;
        return res;
      })
      .catch((err) => {
        pendingPromise = null;
        console.warn("[useCurator] Falha ao verificar papel de curador:", err);
        return { user_id: currentUserId || "", email: null, is_curator: false };
      }));

    promise.then((res) => {
      if (isMounted) {
        setData({ isCurator: res.is_curator, email: res.email });
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [user, isLoaded, currentUserId]);

  if (!isLoaded) {
    return { isCurator: false, isLoading: true, email: null };
  }

  if (!user) {
    return { isCurator: false, isLoading: false, email: null };
  }

  if (cachedResult && cachedResult.userId === currentUserId) {
    return {
      isCurator: cachedResult.data.is_curator,
      isLoading: false,
      email: cachedResult.data.email,
    };
  }

  return {
    isCurator: data?.isCurator ?? false,
    isLoading: isLoading && data === null,
    email: data?.email ?? null,
  };
}
