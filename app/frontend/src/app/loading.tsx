export default function Loading() {
  return <div className="mx-auto w-full max-w-6xl space-y-5 pb-10" role="status" aria-label="Carregando painel">
    <span className="sr-only">Carregando seu painel de aprendizagem…</span>
    <div aria-hidden="true" className="space-y-5 animate-pulse motion-reduce:animate-none">
      <div className="h-16 w-2/3 rounded-xl bg-muted" />
      <div className="h-44 rounded-2xl bg-muted" />
      <div className="grid gap-3 md:grid-cols-3">{[1, 2, 3].map(i => <div key={i} className="h-56 rounded-2xl bg-muted" />)}</div>
      <div className="h-40 rounded-2xl bg-muted" />
    </div>
  </div>;
}
