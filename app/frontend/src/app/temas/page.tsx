import { notFound } from "next/navigation";
import { plannerData } from "@/lib/plannerData";
import { serverApi } from "@/lib/server-api";
import { ThemeClient } from "./ThemeClient";

export const dynamic = "force-dynamic";

export default async function TemaPage({ searchParams }: {
  searchParams: Promise<{ subtema?: string | string[] }>;
}) {
  const { subtema } = await searchParams;
  if (typeof subtema !== "string") notFound();
  const group = plannerData.find(area => area.macroThemes.some(theme => theme.dbSubtemas.includes(subtema)));
  const theme = group?.macroThemes.find(item => item.dbSubtemas.includes(subtema));
  if (!group || !theme) notFound();
  const [profile, progress] = await Promise.all([
    serverApi.stats.getLearningProfile(subtema), serverApi.themes.getProgress(subtema),
  ]);
  const topic = profile.topics.find(item => item.topic === subtema);
  return <ThemeClient key={subtema} subtema={subtema} group={{ area: group.area }} theme={{ highYield: theme.highYield, details: theme.details }} topic={topic} initialProgress={progress} />;
}
