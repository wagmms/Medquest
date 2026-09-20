# 05 — Testes de navegação e falhas da jornada

Você trabalha no MedQuest em `/home/wagmoraes/Projetos Prog/MedQuest`.
Leia `docs/jornada-por-tema-2026-09-20.md`, os AGENTS.md aplicáveis e somente os arquivos relevantes. Para frontend, consulte a documentação instalada em `app/frontend/node_modules/next/dist/docs/` antes de editar.

Há alterações locais legítimas: registre o estado inicial e o diff dos arquivos que pretende tocar para distinguir suas mudanças. Preserve o trabalho existente. Não faça commit, deploy, reset, limpeza de arquivos ou alterações de segredos. Testes devem usar bancos temporários, nunca Turso real. Não instale bibliotecas sem necessidade. Migrações devem ser aditivas, com a próxima numeração livre; não edite migrações anteriores.

Estado já implementado: central de temas; estudo teórico concluído por usuário; percursos essencial/completo; flashcards por tema; prioridade adaptativa integrada ao planner com sinais de todos os temas. Não recrie esses recursos. A conclusão de atividades é separada de domínio, acurácia e retenção.

Execute esta etapa depois das implementações e revisões 02, 03 e 04. Leia `app/frontend/playwright.config.ts`, testes E2E existentes, `app/frontend/src/app/temas`, `app/frontend/src/app/revisao-ativa`, `app/frontend/src/lib/themeJourney.ts` e o comportamento de `server-api.ts` em testes.

Crie testes de navegador reproduzíveis para a jornada entregue. Faça correções de produto apenas para defeitos comprovados por esses testes; não redesenhe nem amplie funcionalidades.

Cenários mínimos:
1. Abrir tema pelo planner e pela cobertura; preservar nome com acentos e caracteres especiais nos links.
2. Marcar/desmarcar teoria, trocar percurso e confirmar persistência após recarregar; falha de gravação deve manter o estado anterior e mostrar erro.
3. Revisões de questões precedem flashcards; flashcards precedem diagnóstico/teoria/prática. O diagnóstico solicita apenas questões restantes e cada percurso usa seu limite.
4. Entrar em flashcards do tema sem misturar outros temas, retornar à central e tratar tema sem cartões. Uma revisão que falha deve recolocar o cartão na fila.
5. Biblioteca: criar/editar referência, cancelar exclusão, confirmar exclusão e tratar falha de rede sem falso sucesso.
6. Desktop e viewport móvel: controles acessíveis por teclado, rótulos dos campos e ausência de rolagem horizontal involuntária.

Use fixtures e APIs locais de teste; não use contas, segredos ou banco de produção. O projeto tem bypass de fetch SSR em `PLAYWRIGHT_TEST`; inspecione isso antes de escolher mocks. Use um ambiente isolado que teste a renderização real sem introduzir endpoint público de teste ou enfraquecer autenticação em produção. Caso não consiga executar, registre o bloqueio e entregue os testes sem alegar que passaram. Salve screenshots em diretório ignorado pelo Git; não faça snapshots frágeis de páginas inteiras sem necessidade.

Execute testes relevantes e, se alterar frontend, TypeScript e lint dos arquivos afetados. Teste o build quando houver alterações de rotas, dependências ou empacotamento. Se algum comando não puder executar, informe o bloqueio; não afirme sucesso sem execução. Não desabilite testes para obter aprovação.

Ao terminar, entregue um resumo de até 15 linhas com arquivos alterados, comportamento entregue, testes executados e limitações. Registre em `docs/gemini/entregas/05.md` os mesmos dados e decisões necessárias à próxima etapa, sem segredos, logs completos ou conteúdo de banco. Não implemente a tarefa seguinte.
