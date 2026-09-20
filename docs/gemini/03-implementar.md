# 03 — Biblioteca pessoal por tema

Você trabalha no MedQuest em `/home/wagmoraes/Projetos Prog/MedQuest`.
Leia `docs/jornada-por-tema-2026-09-20.md`, os AGENTS.md aplicáveis e somente os arquivos relevantes. Para frontend, consulte a documentação instalada em `app/frontend/node_modules/next/dist/docs/` antes de editar.

Há alterações locais legítimas: registre o estado inicial e o diff dos arquivos que pretende tocar para distinguir suas mudanças. Preserve o trabalho existente. Não faça commit, deploy, reset, limpeza de arquivos ou alterações de segredos. Testes devem usar bancos temporários, nunca Turso real. Não instale bibliotecas sem necessidade. Migrações devem ser aditivas, com a próxima numeração livre; não edite migrações anteriores.

Estado já implementado: central de temas; estudo teórico concluído por usuário; percursos essencial/completo; flashcards por tema; prioridade adaptativa integrada ao planner com sinais de todos os temas. Não recrie esses recursos. A conclusão de atividades é separada de domínio, acurácia e retenção.

Leia `app/backend/api/themes.py`, o mecanismo de migração, `app/frontend/src/app/temas/ThemeClient.tsx`, os tipos e clientes de API.

Implemente referências pessoais na central de tema: título, URL HTTP/HTTPS, tipo (aula, resumo, fluxograma, outro), duração opcional em minutos inteiros positivos. Permita listar, adicionar, editar e excluir.

Critérios:
- Dados vinculados ao usuário autenticado e ao tema canônico exato. Não aceite identidade de usuário no payload. Edição e exclusão de IDs alheios devem falhar sem revelar o recurso.
- Valide no backend título obrigatório (até 200 caracteres), URL absoluta com host (até 2048 caracteres; apenas HTTP/HTTPS, sem credenciais embutidas), tipo e duração opcional entre 1 e 1440 minutos. Rejeite booleanos como duração. Limite notas/atributos ao contrato, sem campos livres extras.
- Migração aditiva. Não baixe arquivos, busque metadados, renderize HTML externo ou importe materiais dos HARs. Abra links com `rel="noopener noreferrer"` quando usar nova aba.
- Interface com estados vazio, carregando, erro e sucesso; formulários acessíveis, prevenção de envio duplo e confirmação antes da exclusão. Funciona em temas sem questões.
- Não conclua teoria automaticamente ao abrir/adicionar material. Não altere prioridade, carga horária ou FSRS. A duração é informativa e declarada pelo usuário.
- Teste CRUD, persistência, isolamento de leitura e mutação, validação de URLs e tema desconhecido. Decida explicitamente e documente se o reset de progresso preserva referências pessoais; prefira preservar a biblioteca.

Execute testes relevantes e, se alterar frontend, TypeScript e lint dos arquivos afetados. Teste o build quando houver alterações de rotas, dependências ou empacotamento. Se algum comando não puder executar, informe o bloqueio; não afirme sucesso sem execução. Não desabilite testes para obter aprovação.

Ao terminar, entregue um resumo de até 15 linhas com arquivos alterados, comportamento entregue, testes executados e limitações. Registre em `docs/gemini/entregas/03.md` os mesmos dados e decisões necessárias à próxima etapa, sem segredos, logs completos ou conteúdo de banco. Não implemente a tarefa seguinte.
