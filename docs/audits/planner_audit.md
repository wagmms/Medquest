# Relatório de Auditoria — Aba: Planner
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou (`./validate.sh fast`)  
**Resultado Pós-Correções**: Passou (`./validate.sh fast`)

---

## 1. Resumo Executivo
Uma auditoria completa e vertical da aba **Planner** (`/planner`) foi executada em conformidade com o protocolo definido em `docs/prompts/TAB_AUDIT_PROMPT.md`. A fatia abrange desde a persistência em banco SQLite/Turso (`planner_config`, `planner_schedule`, `planner_progress`, `planner_topic_progress`), os serviços em Flask (`api/plan.py`, `api/services/planner.py`, `api/stats.py`), até os componentes Next.js / React 19 (`PlannerClient.tsx`, `PlannerWizard.tsx`, `page.tsx`, `lib/googleCalendar.ts`).

Foram identificados e corrigidos cirurgicamente:
1. **P1 (Crítico)**: Na sincronização com o Google Calendar, datas de prova em formato ISO (`2026-11-15T12:00:00.000Z`) causavam `Invalid Date` no cálculo de deadline devido à concatenação direta com `T00:00:00`, ignorando silenciosamente a data limite da prova e agendando blocos para depois do exame.
2. **P2 (Maior)**: A contagem global de tópicos concluídos duplicava (`2x`, podendo ultrapassar 100%), pois `/api/planner/topics` retorna duas chaves por tópico (`week:subtema` e `subtema`), e o cliente contava todos os valores booleanos do mapa em vez de avaliar os tópicos do plano ativo.
3. **P2 (Maior)**: Ações de estudo offline no Planner disparavam `OfflineQueuedError`, que eram capturadas como falhas comuns no frontend, revertendo visualmente o progresso embora estivessem enfileiradas no IndexedDB. Paralelamente, a rota destrutiva `/api/planner/config/reset` caía na fila de mutações offline idempotentes, arriscando apagamento inadvertido ao reconectar.
4. **P2 (Maior)**: A seleção de múltiplas bancas (`USP-SP, USP-RP`) ou `"Todas as Bancas"` era gravada como string descritiva única em `target_institution`, quebrando as rotas de `exam-readiness` e `institution-radar` na aba Análise ao buscar códigos literais inexistentes.
5. **P2 (Maior)**: Ausência de barreira de resiliência e estado de retry em `app/planner/page.tsx` no caso de indisponibilidade da API do servidor.
6. **P3 (Otimização & A11y)**: Falta de memoização em memória dos arquivos estáticos `plannerData.json` e `katomartCourseDurations.json` em `_load_catalogs`, ausência de listeners `Escape` nos modais, e carência de atributos `aria-pressed`, `aria-label` e `role="dialog"`.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Resiliência a falhas de rede no Server Component: implementado fallback com banner informativo e ação de retry.
- [x] Tratamento de `OfflineQueuedError` nos toggles de tópicos e fechamento de semana sem reversão equivocada da UI otimista.
- [x] Remoção do endpoint destrutivo `/reset` da fila de mutações offline automáticas.
- [x] Proteção contra drift de timezone UTC em `weekDate` adicionando normalização local segura.

### Pilar 2: Performance & Banco de Dados
- [x] Cache em memória com `@lru_cache(maxsize=1)` em `_load_catalogs()`, eliminando I/O síncrono e parse de JSON a cada geração de plano e exportação ICS.
- [x] Consultas com uso dos índices `idx_planner_schedule_lookup` e chaves primárias compostas.
- [x] Memoização refinada de `completedTopics` derivada estritamente dos tópicos visíveis no plano.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Fechamento de todos os modais (Configurações, Calendário, Confirmação de Reset) ao pressionar a tecla `Escape`.
- [x] Atributos `role="dialog"`, `aria-modal="true"` e `aria-labelledby` em todos os modais.
- [x] Atributos `aria-pressed` e `aria-label` em botões de seleção de bancas no `PlannerWizard`.
- [x] Atributos `aria-haspopup="dialog"` e `aria-expanded` nos botões de disparo de modal.
- [x] Labels acessíveis (`aria-label`) nos checkboxes de tópicos e semanas.

### Pilar 4: Lógica Médica & Domínio
- [x] Normalização de formato de data de prova (`YYYY-MM-DD`) para cálculo exato de capacidade antes da prova no Google Calendar.
- [x] Extração de instituição canônica primária (`primary_institution`) para alimentar os relatórios de Prontidão Bayesiana e Radar Institucional sem conflito de strings compostas.
- [x] Preservação da lógica pedagógica com base na matriz curricular Katomart + 2.0h de prática por subtema e Focos de Alta Incidência.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `src/lib/googleCalendar.ts:52` | Datas ISO geravam `Invalid Date` no cálculo de deadline | Ignorava data da prova e agendava blocos após a prova |
| #2 | P2 (Maior) | `src/app/planner/PlannerClient.tsx:303` | Contagem de tópicos concluídos duplicada (`Object.values`) | Progresso de conclusão inflado em até 200% |
| #3 | P2 (Maior) | `src/app/planner/PlannerClient.tsx:240` & `src/lib/api.ts:54` | `OfflineQueuedError` causava rollback falso; `/reset` entrava na fila offline | Usuário achava que falhou e tinha progresso desincronizado |
| #4 | P2 (Maior) | `api/plan.py:102`, `api/stats.py:763,1618` | String composta `"USP-SP, USP-RP"` ou `"Todas as Bancas"` em queries SQL | Análise e Radar com 0 questões disponíveis |
| #5 | P2 (Maior) | `src/app/planner/page.tsx:6` | Falta de tratamento de erro no Server Component | Crash 500 no carregamento do Planner em falhas de API |
| #6 | P3 (Otimização) | `api/services/planner.py:70` | Leitura síncrona de arquivos JSON a cada requisição | Latência desnecessária no backend |
| #7 | P3 (UX / A11y) | `PlannerClient.tsx`, `PlannerWizard.tsx` | Falta de suporte a `Escape` e atributos ARIA nos modais e inputs | Dificuldade de navegação para usuários de teclado/leitores de tela |

---

## 4. Correções Aplicadas

### Correção #1: Normalização de Data Limite no Google Calendar
- **Arquivos Alterados**: [`app/frontend/src/lib/googleCalendar.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/googleCalendar.ts)
- **Motivação & Solução**: O wizard grava a data em formato ISO completo (`2026-11-15T12:00:00.000Z`). Ao concatenar `T00:00:00`, o objeto `Date` resultava em `Invalid Date` (`NaN`), tornando `cursor >= deadline` sempre falso. Foi implementado corte seguro `slice(0, 10)` antes de construir o deadline local, validando com `!Number.isNaN(deadline.getTime())`.
- **Teste de Regressão Executado**: Suíte de testes `audit-regressions.test.mjs` com assertiva específica para ISO string.

### Correção #2: Predicado Canônico de Conclusão de Tópicos
- **Arquivos Alterados**: [`app/frontend/src/app/planner/PlannerClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/planner/PlannerClient.tsx)
- **Motivação & Solução**: Em vez de fazer `Object.values(topicProgress).filter(Boolean).length` (que somava tanto a chave composta quanto a simples retornadas pela API), calculou-se a soma dos tópicos do plano atual avaliados com `topicProgress[\`${week.week}:${t.subtema}\`] || topicProgress[t.subtema]`.
- **Teste de Regressão Executado**: Verificação do cálculo de porcentagem no client e testes do backend.

### Correção #3: Resiliência Offline e Bloqueio de Reset Enfileirado
- **Arquivos Alterados**: [`app/frontend/src/lib/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/api.ts), [`app/frontend/src/app/planner/PlannerClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/planner/PlannerClient.tsx)
- **Motivação & Solução**: No `api.ts`, `/reset` foi explicitamente excluído de mutações offline. No `PlannerClient.tsx`, `OfflineQueuedError` é tratado mantendo o estado otimista e exibindo feedback de sincronização pendente.
- **Teste de Regressão Executado**: Execução da suíte de offline sync em `audit-regressions.test.mjs`.

### Correção #4: Resolução de Instituição Primária Canônica
- **Arquivos Alterados**: [`app/backend/api/plan.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/plan.py), [`app/backend/api/stats.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/stats.py), [`app/frontend/src/app/analise/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/analise/page.tsx), [`app/frontend/src/types/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/types/api.ts)
- **Motivação & Solução**: A API agora expõe `primary_institution`, extraindo o código singular prioritário (ex.: `"USP-SP"`) e tratando `"Todas as Bancas"` como busca global desprovida de filtro de código. As rotas `/stats/exam-readiness` e `/stats/institution-radar` normalizam parâmetros compostos com vírgula ou labels nacionais.
- **Teste de Regressão Executado**: `tests/test_planner.py::test_planner_config_returns_primary_institution_and_list` e `test_exam_readiness_and_radar_with_composite_and_national_institutions`.

### Correção #5: Resiliência a Falhas do Servidor em `PlannerPage`
- **Arquivos Alterados**: [`app/frontend/src/app/planner/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/planner/page.tsx)
- **Motivação & Solução**: Envolvimento das chamadas de servidor em bloco `try/catch` com renderização de tela de erro graciosa e botão para recarregar.
- **Teste de Regressão Executado**: Validação de build e typechecking sem erros.

### Correção #6: Memoização dos Catálogos Pedagógicos em Memória
- **Arquivos Alterados**: [`app/backend/api/services/planner.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/services/planner.py)
- **Motivação & Solução**: Aplicação de `@lru_cache(maxsize=1)` em `_load_catalogs()`.
- **Teste de Regressão Executado**: `tests/test_planner.py::test_load_catalogs_is_memoized`.

### Correção #7: Acessibilidade (A11y), Teclado e Tokens Tailwind
- **Arquivos Alterados**: [`app/frontend/src/app/planner/PlannerClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/planner/PlannerClient.tsx), [`app/frontend/src/app/planner/PlannerWizard.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/planner/PlannerWizard.tsx)
- **Motivação & Solução**: Inclusão de `useEffect` com listener `Escape` para fechar modais, inclusão de `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-pressed`, `aria-expanded` e `aria-label` nos botões e checkboxes.
- **Teste de Regressão Executado**: Eslint incremental em todos os arquivos modificados.

---

## 5. Validação & Resultados dos Testes

```bash
$ ./validate.sh fast
================================================================
[FAST TIER] MEDQUEST DEV-VELOCITY: COMMIT LOCAL
================================================================

Arquivos alterados detectados (28):
  - app/frontend/src/components/ExplanationViewer.tsx
  - app/frontend/src/app/DashboardClient.tsx
  - app/frontend/src/app/planner/PlannerWizard.tsx
  - docs/prompts/
  - app/frontend/src/types/api.ts
  - app/backend/tests/test_planner.py
  - app/backend/api/plan.py
  - app/frontend/scripts/tests/audit-regressions.test.mjs
  ... e mais 20 arquivos.

--> [Backend Diff Tests (5 suites)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/backend/.venv/bin/pytest -q --disable-warnings tests/test_api.py tests/test_planner.py tests/test_observability.py tests/test_exam_readiness.py tests/test_stats_phase1.py
............................................................             [100%]
60 passed in 2.93s
    [OK] Backend Diff Tests (5 suites) concluido com sucesso (3.58s)

--> [Frontend Incremental Lint (15 arquivos)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/frontend/node_modules/.bin/eslint --quiet src/components/ExplanationViewer.tsx src/app/DashboardClient.tsx src/app/planner/PlannerWizard.tsx src/types/api.ts src/lib/googleCalendar.ts src/lib/api.ts src/app/page.tsx src/components/ImageViewer.tsx src/app/estudar/hooks/useQuizKeyboard.ts src/app/planner/page.tsx
    [OK] Frontend Incremental Lint (15 arquivos) concluido com sucesso (1.95s)

----------------------------------------------------------------
[PASS] SUCESSO: TODAS AS VALIDACOES PASSARAM (Camada: FAST | Tempo Total: 5.55s)
----------------------------------------------------------------
```

```bash
$ node app/frontend/scripts/tests/audit-regressions.test.mjs
✔ reading and removing a session never migrates or erases another owner (71.52602ms)
✔ a delayed session write is cancelled when the active account changes (11.857368ms)
✔ offline card creation is durable and cannot return a fabricated server ID (45.672541ms)
✔ server authorization failures are not disguised as local card saves (38.038274ms)
✔ download traverses all pages of cards (36.99074ms)
✔ calendar keeps topics whole, advances at daily capacity, and skips weekends (15.851225ms)
✔ calendar HTTP failures reject instead of announcing success (10.289142ms)
✔ calendar uses every page, preserves completed legacy events and imports completion (20.676275ms)
✔ retrying a partial calendar sync updates the same IDs without deleting events (10.79586ms)
✔ sync retries a processing conflict but stops for a mismatched idempotency key (24.465151ms)
✔ a request started by Alice is not queued as Bob after an account switch (22.244076ms)
✔ deck deletion invalidates only the current owners matching cached cards (19.30048ms)
✔ legacy calendar fragments are removed only after replacement, and cleanup errors surface (11.653258ms)
ℹ tests 13
ℹ pass 13
ℹ fail 0
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
1. **Edição Granular de Tópicos por Semana**: Permitir que o aluno arraste tópicos entre semanas adjacentes via drag-and-drop quando houver semanas com carga desigual.
2. **Matrizes de Ponderação Específicas por Banca**: Atualmente o cronograma utiliza a matriz nacional ponderada de referência (USP); expandir para matrizes dedicadas (ex.: ENARE, SUS-SP) quando pesos históricos por subtema estiverem disponíveis para cada edital.
3. **Indicador de Conclusão Teórica Integrado**: Conectar os dados de `theme_progress` da Central de Temas para exibir a pill de "Teoria concluída" diretamente no item de cada tema na listagem do Planner.
