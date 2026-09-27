import { FlashcardClient } from "./FlashcardClient";
import { getSubtemaDetails } from "@/lib/plannerData";
import { notFound } from "next/navigation";

export default async function RevisaoAtivaPage({ searchParams }: {
  searchParams: Promise<{ subtema?: string | string[] }>;
}) {
  const { subtema: rawSubtema } = await searchParams;
  const subtema = typeof rawSubtema === "string" ? rawSubtema : undefined;
  if (rawSubtema !== undefined && (!subtema || !getSubtemaDetails(subtema))) notFound();
  return <div className="animate-in fade-in duration-500 w-full h-full"><FlashcardClient key={subtema || "all"} subtema={subtema} /></div>;
}
