/**
 * Módulo de Pré-carregamento e Sincronização Transacional Offline de Questões.
 *
 * Viabiliza o download em segundo plano e persistência atômica no Dexie (IndexedDB)
 * das próximas questões do caderno / tema adaptativo, assegurando transição com
 * latência 0ms entre questões mesmo em conexões hospitalares lentas ou intermitentes.
 */

import { api } from "./api";
import { localDb, syncQuestions, getCachedQuestionIds, getLocalOwnerId, isDeviceOffline } from "./db";
import type { QuestionDetail, QuestionListItem } from "@/types/api";

export interface PrefetchResult {
  prefetched: number;
  cached: number;
  total: number;
}

export interface PrefetchOptions {
  force_4_options?: boolean;
  signal?: AbortSignal;
  area?: string;
  ownerId?: string;
}

// Bloqueios em memória para prevenção de chamadas duplicadas concorrentes
const activePrefetchPromises = new Map<string, Promise<PrefetchResult>>();
const activeIdPrefetches = new Set<number>();

/**
 * Pré-carrega no Dexie os detalhes completos (enunciado, alternativas, metadados)
 * de uma lista de IDs de questões específicas de forma transacional e atômica.
 *
 * @param ids Lista de IDs numéricos de questões
 * @param options Opções de carregamento (ownerId, force_4_options, signal)
 */
export async function prefetchQuestionsByIds(
  ids: number[],
  options?: PrefetchOptions
): Promise<PrefetchResult> {
  if (typeof window === "undefined" || !localDb || !ids || !Array.isArray(ids) || ids.length === 0) {
    return { prefetched: 0, cached: 0, total: 0 };
  }

  // 1. Sanitiza e desduplica IDs válidos
  const uniqueIds = Array.from(
    new Set(
      ids.filter((id) => typeof id === "number" && !isNaN(id) && id > 0)
    )
  );

  if (uniqueIds.length === 0) {
    return { prefetched: 0, cached: 0, total: 0 };
  }

  const ownerId = options?.ownerId || getLocalOwnerId();

  // 2. Consulta em lote quais IDs já estão persistidos no Dexie
  const alreadyCached = await getCachedQuestionIds(uniqueIds, ownerId);

  // 3. Isola os IDs ausentes que não estão sendo pré-carregados no momento
  const missingIds = uniqueIds.filter(
    (id) => !alreadyCached.has(id) && !activeIdPrefetches.has(id)
  );

  if (missingIds.length === 0) {
    return {
      prefetched: 0,
      cached: alreadyCached.size,
      total: uniqueIds.length,
    };
  }

  // 4. Se o dispositivo estiver offline ou em modo plantão forçado, evita requisições de rede
  if (isDeviceOffline() || (typeof navigator !== "undefined" && !navigator.onLine)) {
    return {
      prefetched: 0,
      cached: alreadyCached.size,
      total: uniqueIds.length,
    };
  }

  // 5. Registra IDs em andamento para evitar sobreposição
  missingIds.forEach((id) => activeIdPrefetches.add(id));

  try {
    // 6. Busca os detalhes das questões faltantes em lote (POST /api/questions/batch)
    const batchResult = await api.questions.getBatch(missingIds, options?.force_4_options);
    const questionsToCache: QuestionDetail[] = batchResult?.questions || [];

    if (questionsToCache.length === 0) {
      return {
        prefetched: 0,
        cached: alreadyCached.size,
        total: uniqueIds.length,
      };
    }

    // 7. Persistência atômica transacional no Dexie com rollback e recuperação de cota
    const savedCount = await syncQuestions(questionsToCache, ownerId);

    // 8. Emissão de evento customizado para notificar componentes de UI
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      try {
        window.dispatchEvent(
          new CustomEvent("questions-prefetched", {
            detail: { count: savedCount, ids: missingIds, ownerId },
          })
        );
      } catch {
        // Silencia erros de dispatch em ambientes restritos
      }
    }

    return {
      prefetched: savedCount,
      cached: alreadyCached.size + savedCount,
      total: uniqueIds.length,
    };
  } catch (err) {
    console.warn("[syncQueue] Falha durante prefetch transacional em segundo plano:", err);
    return {
      prefetched: 0,
      cached: alreadyCached.size,
      total: uniqueIds.length,
    };
  } finally {
    // Libera a trava dos IDs processados
    missingIds.forEach((id) => activeIdPrefetches.delete(id));
  }
}

/**
 * Pré-carrega em segundo plano as próximas N questões da fila adaptativa/caderno do aluno
 * para um determinado subtema ou área, armazenando-as atomicamente no Dexie.
 *
 * @param themeId Identificador do tema/subtema (ex: 'Hipertensão Arterial Sistêmica')
 * @param limit Quantidade de questões a pré-carregar (padrão: 10)
 * @param options Opções adicionais de filtro e execução
 */
export async function prefetchUpcomingQuestions(
  themeId?: string | number,
  limit: number = 10,
  options?: PrefetchOptions
): Promise<PrefetchResult> {
  if (typeof window === "undefined" || !localDb) {
    return { prefetched: 0, cached: 0, total: 0 };
  }

  const safeLimit = Math.max(1, Math.min(50, limit));
  const prefetchKey = `${themeId || "all"}_${options?.area || ""}_${safeLimit}`;

  // Se já houver um prefetch idêntico em andamento, retorna a promessa ativa para evitar duplicações
  const existingPromise = activePrefetchPromises.get(prefetchKey);
  if (existingPromise) {
    return existingPromise;
  }

  const promise = (async (): Promise<PrefetchResult> => {
    try {
      if (isDeviceOffline() || (typeof navigator !== "undefined" && !navigator.onLine)) {
        return { prefetched: 0, cached: 0, total: 0 };
      }

      // Monta filtros para consulta das próximas questões da fila
      const filters: Record<string, string> = {
        limit: String(safeLimit),
      };

      if (themeId !== undefined && themeId !== null && themeId !== "") {
        filters.subtema = String(themeId);
      }

      if (options?.area) {
        filters.area = options.area;
      }

      // Busca a lista de IDs das questões recomendadas
      const list: QuestionListItem[] = await api.questions.getList(filters);
      if (!list || !Array.isArray(list) || list.length === 0) {
        return { prefetched: 0, cached: 0, total: 0 };
      }

      const candidateIds = list.map((q) => q.id);
      return await prefetchQuestionsByIds(candidateIds, options);
    } catch (err) {
      console.warn(`[syncQueue] Falha ao pré-carregar fila para o tema ${themeId}:`, err);
      return { prefetched: 0, cached: 0, total: 0 };
    } finally {
      activePrefetchPromises.delete(prefetchKey);
    }
  })();

  activePrefetchPromises.set(prefetchKey, promise);
  return promise;
}
