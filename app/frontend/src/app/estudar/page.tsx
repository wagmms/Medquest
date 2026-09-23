import Link from "next/link";
import { getSubtemaDetails } from "@/lib/plannerData";
import { isDynamicServerUsageError, serverApi, QuestionMeta } from "@/lib/server-api";
import { QuizClient } from "./QuizClient";

export const dynamic = "force-dynamic";

export default async function EstudarPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  let meta: QuestionMeta | undefined;
  try {
    meta = await serverApi.questions.getMeta();
  } catch (err: unknown) {
    if (isDynamicServerUsageError(err)) {
      throw err;
    }
    console.warn("SSR getMeta fallback to client fetch:", err);
  }
  const rawParams = await searchParams;

  // Convert searchParams to record of strings or string arrays
  const initialFilters: Record<string, string | string[]> = {};
  for (const key in rawParams) {
    const val = rawParams[key];
    if (typeof val === "string" || Array.isArray(val)) {
      initialFilters[key] = val;
    }
  }

  const subtemaStr = typeof initialFilters.subtema === "string" ? initialFilters.subtema : undefined;

  return (
    <div className="animate-in fade-in duration-500 w-full h-full">
      {subtemaStr && getSubtemaDetails(subtemaStr) && (
        <Link href={`/temas?subtema=${encodeURIComponent(subtemaStr)}`} className="inline-block mb-4 text-sm font-semibold text-primary hover:underline">
          ← Voltar ao tema
        </Link>
      )}
      <QuizClient 
        meta={meta} 
        initialFilters={initialFilters}
      />
    </div>
  );
}
