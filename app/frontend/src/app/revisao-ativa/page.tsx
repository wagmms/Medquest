import { FlashcardClient } from "./FlashcardClient";
import { getSubtemaDetails } from "@/lib/plannerData";
import { notFound } from "next/navigation";

export default async function RevisaoAtivaPage({ searchParams }: {
  searchParams: Promise<{ subtema?: string | string[] }>;
}) {
  const { subtema } = await searchParams;
  if (subtema !== undefined && (typeof subtema !== "string" || !getSubtemaDetails(subtema))) notFound();
  return <div className="animate-in fade-in duration-500 w-full h-full"><FlashcardClient key={subtema || "all"} subtema={subtema} /></div>;
}
