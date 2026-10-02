import { SearchClient } from "./SearchClient";

interface SearchPageProps {
  searchParams: Promise<{
    q?: string;
    area?: string;
    institution?: string;
  }>;
}

export default async function BuscarPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  return (
    <SearchClient
      initialQuery={params.q || ""}
      initialArea={params.area || "Todas"}
      initialInstitution={params.institution || "Todas"}
    />
  );
}
