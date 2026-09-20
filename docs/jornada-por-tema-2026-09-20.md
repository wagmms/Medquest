# Jornada por tema — implementação local

A central `/temas?subtema=…` reúne diagnóstico, estudo, prática e revisão. O planner e a cobertura abrem essa central; questões e flashcards oferecem retorno ao tema.

## Etapa 2

- Estudo teórico com conclusão explícita, reversível e salva por usuário e tema.
- Percursos essencial (até 10 questões por sessão) e completo (até 20). Ambos preservam revisões vencidas; a diferença não promete materiais que o produto ainda não oferece.
- Próxima ação: questões vencidas, flashcards vencidos, diagnóstico restante, teoria pendente e prática adaptativa, nessa ordem.
- Flashcards filtrados por tema na API, na interface e no fallback offline. Contagens consideram somente cartões vinculados a questões do tema e não reportados. Cartões Anki sem vínculo permanecem na revisão geral.
- Atividade declarada não altera acurácia, cobertura ou memória estimada. O checkbox do planner continua sendo um registro separado de conclusão da meta semanal.
- Em falha de gravação, a teoria mantém o valor anterior; em falha de revisão, o flashcard volta à fila.

## Persistência e implantação

A migração aditiva `011_theme_progress.sql` cria a tabela de progresso. Os testes usam bancos temporários; nenhuma migração foi aplicada manualmente ao Turso. O bootstrap local aplica migrações quando habilitado, e o entrypoint de produção já executa o migrador antes do servidor. Publicar requer implantar backend e frontend compatíveis.

Backup original preservado em `backups/medquest-before-theme-hub-20260920.tar.gz`, com checksum no arquivo `.sha256` ao lado. Esse backup contém o workspace local da primeira etapa, não um snapshot do banco Turso remoto.

## Continuidade

Integração da prioridade adaptativa no plano semanal, orçamento de tempo e biblioteca de materiais permanecem como próximas etapas. Não há equivalência automática entre estudo teórico concluído e domínio do tema.
