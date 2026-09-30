import { AnalysisClient } from "./AnalysisClient";

export default function AnalisePage() {
  return (
    <div className="flex flex-col gap-6 pb-10">
      <header>
        <p className="text-sm font-semibold text-primary mb-2">Análise de aprendizagem</p>
        <h1 className="text-3xl font-bold text-foreground">O que estudar e o que já melhorou</h1>
        <p className="text-muted-foreground mt-3 max-w-3xl">
          Encontre suas próximas prioridades, acompanhe erros e confira o que você consegue lembrar depois.
        </p>
      </header>
      <AnalysisClient />
    </div>
  );
}
