# 04 — Progresso teórico visível no planner

Você trabalha no MedQuest em `/home/wagmoraes/Projetos Prog/MedQuest`.
Leia `docs/jornada-por-tema-2026-09-20.md`, os AGENTS.md aplicáveis e somente os arquivos relevantes. Para frontend, consulte a documentação instalada em `app/frontend/node_modules/next/dist/docs/` antes de editar.

Há alterações locais legítimas: registre o estado inicial e o diff dos arquivos que pretende tocar para distinguir suas mudanças. Preserve o trabalho existente. Não faça commit, deploy, reset, limpeza de arquivos ou alterações de segredos. Testes devem usar bancos temporários, nunca Turso real. Não instale bibliotecas sem necessidade. Migrações devem ser aditivas, com a próxima numeração livre; não edite migrações anteriores.

Estado já implementado: central de temas; estudo teórico concluído por usuário; percursos essencial/completo; flashcards por tema; prioridade adaptativa integrada ao planner com sinais de todos os temas. Não recrie esses recursos. A conclusão de atividades é separada de domínio, acurácia e retenção.

Leia `app/backend/api/themes.py`, `app/backend/api/plan.py`, `app/backend/api/services/planner.py`, `app/frontend/src/app/planner/PlannerClient.tsx` e os tipos usados pelo planner.

Mostre no planner a conclusão teórica já registrada na central de cada tema, sem confundi-la com o checkbox existente da meta semanal.

Critérios:
- O tema no planner deve exibir um indicador discreto "Teoria concluída" ou "Teoria pendente", derivado de `theme_progress` do usuário atual, com acesso à central para edição.
- Carregue progresso em lote, em no máximo uma consulta extra por geração do plano. Não faça uma consulta ou requisição por tema. Não acople consultas ao banco ao serviço puro de planejamento.
- Tema sem registro = teoria pendente. Faça associação canônica exata e teste isolamento entre usuários.
- Não sincronize automaticamente teoria com conclusão da meta semanal. Não altere acurácia, prioridade, distribuição, horas, taxonomia ou datas de revisão.
- Mantenha os contratos retrocompatíveis e o calendário ICS funcionando. Não inclua informações novas no ICS sem necessidade.
- Ao retornar da central ao planner, a informação deve refletir a gravação confirmada. Verifique política de atualização/cache e não use persistência local como fonte de verdade.
- Teste alteração e reversão da conclusão teórica, ausência de registro, isolamento e preservação do checkbox semanal.

Execute testes relevantes e, se alterar frontend, TypeScript e lint dos arquivos afetados. Teste o build quando houver alterações de rotas, dependências ou empacotamento. Se algum comando não puder executar, informe o bloqueio; não afirme sucesso sem execução. Não desabilite testes para obter aprovação.

Ao terminar, entregue um resumo de até 15 linhas com arquivos alterados, comportamento entregue, testes executados e limitações. Registre em `docs/gemini/entregas/04.md` os mesmos dados e decisões necessárias à próxima etapa, sem segredos, logs completos ou conteúdo de banco. Não implemente a tarefa seguinte.
