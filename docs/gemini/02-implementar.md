# 02 — Orçamento diário de questões

Você trabalha no MedQuest em `/home/wagmoraes/Projetos Prog/MedQuest`.
Leia `docs/jornada-por-tema-2026-09-20.md`, os AGENTS.md aplicáveis e somente os arquivos relevantes. Para frontend, consulte a documentação instalada em `app/frontend/node_modules/next/dist/docs/` antes de editar.

Há alterações locais legítimas: registre o estado inicial e o diff dos arquivos que pretende tocar para distinguir suas mudanças. Preserve o trabalho existente. Não faça commit, deploy, reset, limpeza de arquivos ou alterações de segredos. Testes devem usar bancos temporários, nunca Turso real. Não instale bibliotecas sem necessidade. Migrações devem ser aditivas, com a próxima numeração livre; não edite migrações anteriores.

Estado já implementado: central de temas; estudo teórico concluído por usuário; percursos essencial/completo; flashcards por tema; prioridade adaptativa integrada ao planner com sinais de todos os temas. Não recrie esses recursos. A conclusão de atividades é separada de domínio, acurácia e retenção.

Leia `app/backend/api/adaptive.py`, seus testes e todos os consumidores de `LearningProfile.goal`.

Problema: `questions_today` usa o maior valor entre meta configurada e revisões vencidas, ampliando a meta quando há atraso. Implemente um orçamento de questões que respeite a meta configurada.

Critérios:
- Para meta N, revisões sugeridas hoje = min(revisões vencidas, N); prática sugerida = N menos revisões sugeridas; excedente = revisões vencidas menos revisões sugeridas.
- Preserve `configured_daily_questions`, exponha esses três valores separadamente e mantenha visível o total vencido. `questions_today` deve representar a sugestão total limitada por N.
- Reutilize a validação de configuração existente e preserve o padrão quando a configuração estiver ausente. Não misture flashcards com questões nem invente conversões para minutos.
- Não altere datas FSRS, o histórico, o currículo, a distribuição semanal ou o agendamento de notificações.
- Atualize tipos e consumidores do dashboard com linguagem simples. Nenhuma ação diária pode continuar usando o total vencido ilimitado como limite da sugestão. O aluno pode iniciar outras sessões por vontade própria.
- Teste N=30 com 0, 10 e 100 revisões: sugestões (revisão/prática/excedente) devem ser (0/30/0), (10/20/0) e (30/0/70). Teste configuração ausente e isolamento de usuários.

Execute testes relevantes e, se alterar frontend, TypeScript e lint dos arquivos afetados. Teste o build quando houver alterações de rotas, dependências ou empacotamento. Se algum comando não puder executar, informe o bloqueio; não afirme sucesso sem execução. Não desabilite testes para obter aprovação.

Ao terminar, entregue um resumo de até 15 linhas com arquivos alterados, comportamento entregue, testes executados e limitações. Registre em `docs/gemini/entregas/02.md` os mesmos dados e decisões necessárias à próxima etapa, sem segredos, logs completos ou conteúdo de banco. Não implemente a tarefa seguinte.
