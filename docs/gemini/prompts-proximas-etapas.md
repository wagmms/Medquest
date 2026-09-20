# Prompts para o Gemini — MedQuest

Use um prompt por vez, em ordem. Cada bloco abaixo já contém o contexto mínimo. Após cada entrega, peça ao Codex para revisar o diff e os testes antes de iniciar a próxima. Pressupõe Gemini com acesso ao workspace; no chat sem acesso a arquivos, forneça somente os arquivos citados e peça um patch, sem afirmar que testes foram executados.

## Prompt 1 — prioridade adaptativa no planner

Você trabalhará no MedQuest, em `/home/wagmoraes/Projetos Prog/MedQuest`. Implemente a integração do perfil adaptativo na prioridade dos temas do planner, preservando o currículo canônico de 170 temas, os critérios de alto rendimento e o modo intensivo existentes.

Leia primeiro `docs/jornada-por-tema-2026-09-20.md`, `app/backend/api/services/planner.py`, `app/backend/api/adaptive.py`, `app/backend/api/plan.py` e os testes relacionados. A central de temas, conclusão manual da teoria, percursos essencial/completo e flashcards por tema já existem: não recrie esses recursos.

Requisitos:
- Reutilize os sinais do motor adaptativo: desempenho com tamanho da amostra, cobertura e retenção. Não crie uma fórmula concorrente sem necessidade.
- Os sinais devem pertencer ao usuário autenticado e ser associados por nome canônico exato. O perfil atual retorna somente os 15 primeiros temas: não use essa lista truncada como se fosse o catálogo completo.
- Sem histórico, preserve o comportamento de priorização anterior. A opção de sinais adaptativos deve ser retrocompatível para chamadas existentes do planejador.
- Não altere a carga horária, a distribuição semanal, a taxonomia, o algoritmo FSRS ou a política de instituições nesta tarefa.
- Inclua motivos curtos de prioridade nos dados de cada tema; atualize os tipos e apresente esses motivos de forma discreta no planner, sem inventar recomendações.
- Teste isolamento por usuário, ausência de histórico, tema fora do top 15 e aumento de prioridade de tema com evidências de dificuldade. Preserve os testes existentes.

Antes de editar, registre o estado inicial do Git: há mudanças locais legítimas de outras tarefas. Não reverta, sobrescreva, faça commit global ou publique. Não leia/exiba segredos e não execute testes contra o Turso real. Leia os AGENTS.md aplicáveis e a documentação local do Next antes de alterar frontend. Altere somente os arquivos necessários; evite refatorações amplas.

Entregue código, testes e resumo de até 15 linhas com arquivos alterados, critérios usados, comandos e resultados reais. Se não conseguir testar, declare a limitação. Não escreva um relatório longo nem reproduza arquivos completos na resposta.

## Prompt 2 — orçamento diário de questões e revisões

Você trabalhará no MedQuest, em `/home/wagmoraes/Projetos Prog/MedQuest`, após a revisão da etapa anterior pelo Codex. Leia `docs/jornada-por-tema-2026-09-20.md`, `app/backend/api/adaptive.py`, os consumidores de `LearningProfile.goal` no frontend e os testes correspondentes.

Problema: a meta diária do perfil adaptativo usa `max(meta_configurada, revisoes_vencidas)`, podendo crescer muito quando há acúmulo. Implemente uma distribuição diária limitada pela meta configurada de questões, preservando visibilidade do atraso.

Contrato pretendido:
- Com meta diária N, sugerir no máximo N questões no total, priorizando revisões vencidas até esse limite. O restante do orçamento pode ser destinado à prática nova.
- Informar separadamente total de revisões vencidas, revisões sugeridas hoje, prática sugerida hoje e revisões que excedem o orçamento. Não ocultar o atraso e não alterar vencimentos FSRS para fazê-lo desaparecer.
- Manter o campo da meta configurada e os consumidores existentes compatíveis. Revisões de flashcards não devem ser somadas a questões como se fossem a mesma unidade.
- A interface deve explicar o excedente em linguagem simples. O aluno continua livre para estudar além da sugestão.
- Essa primeira versão usa quantidade de questões, não minutos. Não invente estimativas de duração nem implemente redistribuição automática do calendário.
- Testar meta menor/maior que o atraso, nenhuma revisão, configuração ausente e isolamento entre usuários.

Preserve todas as alterações locais existentes. Não publique, não faça commits, não altere segredos nem execute testes no banco remoto. Leia AGENTS.md e documentação local do Next quando necessário. Faça a menor mudança coerente.

Entregue código, testes e resumo de até 15 linhas: arquivos, comportamento antes/depois, comandos executados e limitações. Não afirme testes não executados.

## Prompt 3 — referências de estudo por tema

Você trabalhará no MedQuest, em `/home/wagmoraes/Projetos Prog/MedQuest`, após a revisão da etapa anterior pelo Codex. Leia `docs/jornada-por-tema-2026-09-20.md`, `app/backend/api/themes.py`, o fluxo de migrações, `app/frontend/src/app/temas/ThemeClient.tsx` e os clientes de API.

Implemente uma primeira biblioteca pessoal de referências por tema, dentro da central já existente. Cada referência terá título, URL HTTP/HTTPS, tipo (aula, resumo, fluxograma ou outro) e duração opcional em minutos inteiros positivos. Permita listar, adicionar, editar e excluir apenas referências do usuário autenticado.

Requisitos:
- Associe a referência ao nome canônico exato do tema e ao usuário autenticado. Não aceite user_id fornecido no corpo. Valide tema, URL, tipo, duração e limites de tamanho no backend.
- Use migração aditiva nova; descubra a próxima numeração disponível sem editar migrações anteriores. A biblioteca deve funcionar também quando não houver questões no tema.
- Não baixe, faça scraping, incorpore HTML externo, importe conteúdo dos HARs nem busque metadados automaticamente. São links pessoais, abertos com proteção adequada em outra aba.
- A página deve oferecer estado vazio, formulário acessível, validações e mensagens claras de erro. A exclusão deve ter confirmação local explícita.
- Não altere prioridade, FSRS, horários do planner ou conclusão da teoria ao adicionar/abrir um link. Duração é informação declarada pelo usuário.
- Teste CRUD, isolamento entre usuários em leitura e mutações, URLs inválidas, tema inexistente e persistência. Use apenas bancos temporários.

Preserve mudanças locais existentes; não publique, não faça commits e não toque em segredos ou no Turso real. Leia AGENTS.md e a documentação local do Next antes de escrever frontend. Não crie biblioteca global, uploads ou outras funções fora deste escopo.

Entregue implementação e testes com resumo de até 15 linhas, informando arquivos alterados, migração, verificações realmente executadas e limitações.
