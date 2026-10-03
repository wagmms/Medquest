import { notFound } from "next/navigation";
import { serverApi } from "@/lib/server-api";
import { OsceRoomClient } from "./OsceRoomClient";

export const dynamic = "force-dynamic";

export default async function OsceRoomPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { id } = await params;
  const stationId = parseInt(id, 10);
  if (isNaN(stationId)) {
    notFound();
  }

  let station;
  try {
    station = await serverApi.osce.getStation(stationId);
  } catch (err) {
    console.error("Failed to fetch OSCE station:", err);
    notFound();
  }

  if (!station) {
    notFound();
  }

  const rawQuery = await searchParams;
  const circuitId = typeof rawQuery.circuit === "string" ? rawQuery.circuit : undefined;
  const step = typeof rawQuery.step === "string" ? parseInt(rawQuery.step, 10) : 1;

  return (
    <div className="flex-1 flex flex-col min-h-0 w-full overflow-hidden bg-background">
      <OsceRoomClient station={station} circuitId={circuitId} step={step} />
    </div>
  );
}
