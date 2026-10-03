import { serverApi } from "@/lib/server-api";
import { OsceStation } from "@/types/api";
import { OsceHubClient } from "./OsceHubClient";

export const dynamic = "force-dynamic";

export default async function OscePage() {
  let initialStations: OsceStation[] = [];
  try {
    const res = await serverApi.osce.getStations();
    initialStations = res.stations || [];
  } catch (err) {
    console.warn("SSR getStations fallback to client:", err);
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 w-full p-4 md:p-6 overflow-y-auto">
      <OsceHubClient initialStations={initialStations} />
    </div>
  );
}
