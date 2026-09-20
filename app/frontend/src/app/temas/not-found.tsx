import Link from "next/link";
export default function NotFound() {
  return <div className="p-8 text-center"><h1 className="text-xl font-semibold">Tema não encontrado</h1><p className="my-4 text-muted-foreground">Escolha um tema do catálogo para abrir sua jornada.</p><Link href="/cobertura" className="text-primary underline">Ver todos os temas</Link></div>;
}
