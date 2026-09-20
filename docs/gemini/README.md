# Lote de trabalho para Gemini

O prompt 01 (prioridade adaptativa) já foi revisado pelo Codex: 38 testes de backend passaram, além de TypeScript e lint. Uma descrição incorreta de acurácia "recente" foi corrigida para histórico de tentativas.

Execute um arquivo por vez na ordem abaixo. Cada implementação tem revisão independente correspondente. As etapas compartilham arquivos; não execute simultaneamente no mesmo checkout.

| Ordem | Implementação | Revisão |
| --- | --- | --- |
| 02 — Orçamento diário | [Implementar](02-implementar.md) | [Revisar](02-revisar.md) |
| 03 — Biblioteca pessoal | [Implementar](03-implementar.md) | [Revisar](03-revisar.md) |
| 04 — Progresso no planner | [Implementar](04-implementar.md) | [Revisar](04-revisar.md) |
| 05 — Testes de navegador | [Implementar](05-implementar.md) | [Revisar](05-revisar.md) |

Estes arquivos substituem os prompts 2 e 3 do documento anterior `prompts-proximas-etapas.md`. Não execute as duas versões.

Cole o conteúdo completo do arquivo no Gemini com acesso ao projeto. Sem acesso ao workspace, forneça os arquivos citados e solicite um patch; o Gemini não poderá comprovar execução de testes.

Depois de cada par, os relatórios estarão em `docs/gemini/entregas/`. Preferencialmente use outra conversa para a revisão, fornecendo o prompt original e acesso ao código resultante. A autorrevisão ajuda a encontrar problemas, mas não substitui a auditoria final pelo Codex.

Ao concluir o lote, diga ao Codex: "Revise o lote 02–05 do Gemini, confira os relatórios em docs/gemini/entregas e corrija as regressões". Se alguma revisão registrar bloqueio ou falha importante, traga esse resultado antes de prosseguir.
