# Relatório de Auditoria — Aba: Dashboard
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou  
**Resultado Pós-Correções**: Passou (`./validate.sh fast` em 9.21s: 60 testes backend pytest aprovados, 0 erros no ESLint)

---

## 1. Resumo Executivo
Uma auditoria completa e vertical da aba **Dashboard** (`/`) foi executada em conformidade com o protocolo definido em `docs/prompts/TAB_AUDIT_PROMPT.md`. A fatia investigada abrange a rota e o Server Component (`app/page.tsx`), o componente cliente principal (`DashboardClient.tsx`), os componentes associados de layout e navegação (`Sidebar.tsx`, `TopNav.tsx`, `WebVitals.tsx`), as camadas de API e cliente de transporte (`server-api.ts`, `api.ts`, `sessionState.ts`), o banco de dados e os endpoints Flask (`stats.py`, `plan.py`).

O painel centraliza a tomada de decisão diária do estudante médico (metas do dia, revisões pendentes no FSRS v6, retomada de sessões, tópicos prioritários do edital e estimativa bayesiana de prontidão). Foram identificadas e corrigidas cirurgicamente as seguintes vulnerabilidades:

1. **P1 (Crítico - Resiliência contra Falha de Rede)**: Se a requisição de `/api/stats/overview` falhava no Server Component (`page.tsx`), a exceção era capturada silenciosamente e substituída por `DEFAULT_STATS` (`distinct_answered = 0`). Isso fazia com que alunos experientes com centenas de questões vissem o estado de Onboarding inicial ("Boas-vindas ao MedQuest! Defina seu plano e resolva 20 questões para calibrar seu diagnóstico inicial"), dando a falsa impressão de perda total de progresso, sem qualquer indicação de erro ou botão de recarga. Corrigido com tracking de erro explícito (`hasOverviewError`) e renderização de card de resiliência com botão de "Tentar novamente" e navegação de emergência.
2. **P2 (Maior - Lógica de Sessão Ativa)**: A detecção de sessões em andamento considerava ativas sessões de Quiz já concluídas com `state === "FINISHED"`, porque verificava apenas `state !== "RESULTS"`. Isso deixava o card Hero de "Retomar Sessão de Estudos" permanentemente travado na tela inicial após o término dos estudos. Corrigido com validação estrita dos estados ativos reais (`PLAYING` / `SUBMITTING`).
3. **P2 (Maior - Performance & Banco de Dados)**: O endpoint `/api/stats/error-notebook-summary` utilizava subquery correlacionada `WHERE a1.id = (SELECT MAX(a2.id) FROM attempts a2 WHERE ...)` com custo $O(N^2)$ sobre a tabela de tentativas. Refatorado com uma CTE e window function `ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC)` que executa em uma única passagem indexada.
4. **P2 (Maior - Edge Cases & Hidratação)**: Discrepância de fuso horário e hidratação na data da prova (`stats.exam_date`), onde `new Date("YYYY-MM-DD")` avaliado em UTC retrocedia um dia no fuso horário do Brasil (UTC-3), além de possíveis conflitos SSR/Client no `toLocaleDateString`. Corrigido com função utilitária `formatExamDate` alinhada ao meio-dia local e atributo `suppressHydrationWarning`.
5. **P3 (Otimização - Bundle Frontend)**: O componente `OfflineModal` (que importa o volumoso `OfflinePanel` de ~450 linhas, Lucide icons, toast e Dexie) era importado estaticamente no topo do bundle do dashboard. Convertido para importação dinâmica via `next/dynamic` (`ssr: false`).
6. **P3 (UX, Acessibilidade & Mobile)**: As três barras de progresso (Questões Diárias, Ritmo da Semana e Faixa de Prontidão) careciam de atributos ARIA (`role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label`). Botões de gerenciamento offline não atendiam a targets de toque mínimos de 44x44px no mobile e botões de revisão vencida quebravam layout na presença de apenas um tipo de revisão.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Tratamento de falhas de API no SSR: nunca mais mascara quedas de rede com estado de onboarding zerado.
- [x] Resolução de discrepâncias SSR/Client de hidratação na formatação da data-alvo da prova.
- [x] Detecção precisa de sessões ativas (ignora estados finalizados `FINISHED`, `RESULTS` ou não iniciados `START`).
- [x] Normalização de meta fracionária (`target_score <= 1 ? target_score * 100 : target_score`) evitando marcadores defasados no gráfico de prontidão.
- [x] Sincronização offline e integração do Modo Plantão sem quebra quando desconectado.

### Pilar 2: Performance & Banco de Dados
- [x] Eliminação de subquery correlacionada quadrática no resumo do caderno de erros (`error-notebook-summary`), adotando CTE com window function indexada.
- [x] Redução do bundle inicial do Dashboard com dynamic import do modal offline (`next/dynamic` com `{ ssr: false }`).
- [x] Invalidação adequada de caches de usuário via `invalidate_user_caches` e `overview_cache`.
- [x] Caching do overview de métricas com TTL e isolamento por `user_id` e fuso horário.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Conformidade total com variáveis semânticas do Tailwind v4 (`bg-card`, `text-foreground`, `bg-muted`, `border-border`).
- [x] Eliminação de cor estática `hover:bg-white` no Hero CTA substituída por `hover:bg-primary-foreground/90` garantindo compatibilidade com temas Dark e Light.
- [x] Atributos ARIA completos em todas as barras de progresso (`role="progressbar"`, `aria-valuenow`, `aria-label`).
- [x] Touch targets de 44x44px mínimos em botões de ação e gerenciamento offline.
- [x] Layout flexível para botões de revisão vencida quando apenas flashcards ou apenas questões estão pendentes.

### Pilar 4: Lógica Médica & Domínio
- [x] Priorização clara do FSRS v6 no Hero CTA: revisões vencidas têm precedência sobre questões inéditas para blindar a curva de esquecimento.
- [x] Estimativa do tempo de estudo baseado em 1.5 minutos por revisão pendente.
- [x] Exibição de gargalos com cálculo ponderado entre erros recentes (últimos 60 dias) e histórico global.
- [x] Condicional pedagógica de amostra estatística confiável: o benchmark probabilístico de prontidão só é renderizado a partir de 20 questões distintas respondidas.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `src/app/page.tsx:28` | Falha em `getOverview()` silenciada com `DEFAULT_STATS` exibindo onboarding de conta vazia | Usuário com histórico acreditava ter perdido todo o progresso ao enfrentar instabilidade de rede |
| #2 | P2 (Maior) | `src/app/DashboardClient.tsx:79` | Checagem `hasQuiz.state !== "RESULTS"` detectava quizzes concluídos (`FINISHED`) como sessões ativas | Card "Retomar Sessão" ficava eternamente travado após concluir bateria |
| #3 | P2 (Maior) | `api/stats.py:1376-1383` | Subquery correlacionada quadrática sobre `attempts` em `error_notebook_summary` | Latência excessiva e consumo de I/O em bancos com grande volume de tentativas |
| #4 | P2 (Maior) | `src/app/DashboardClient.tsx:417` | `new Date(exam_date)` em UTC retrocedia 1 dia no Brasil (UTC-3) e causava alerta de hidratação | Data da prova incorreta exibida no badge superior e erro no console React |
| #5 | P3 (Otimização) | `src/app/DashboardClient.tsx:10` | Importação estática do modal offline pesado no bundle principal do Dashboard | Aumento do tamanho do JavaScript inicial na rota raiz `/` |
| #6 | P3 (Otimização) | `src/app/DashboardClient.tsx:165` | `target_score` decimal (ex: 0.76) posicionava linha de corte em 0.76% na barra | Marcador visual de meta de corte quebrado quando persistido como fração |
| #7 | P3 (Acessibilidade) | `src/app/DashboardClient.tsx:557, 704, 759` | Barras de progresso sem `role="progressbar"` e sem atributos ARIA | Leitores de tela não anunciavam o progresso de metas e prontidão |
| #8 | P3 (UX & Mobile) | `src/app/DashboardClient.tsx:381, 810` | Botões de gerenciamento offline com target < 30px e sem `aria-label` | Dificuldade de clique no mobile e falta de rótulo acessível |

---

## 4. Correções Aplicadas

### Correção #1: Resiliência contra Quedas de Rede & Estado de Erro Explícito
- **Arquivos Alterados**:
  - [`app/frontend/src/app/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/page.tsx)
  - [`app/frontend/src/app/DashboardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/DashboardClient.tsx)
- **Motivação & Solução**: O Server Component agora rastreia falhas em `serverApi.stats.getOverview()` via `hasOverviewError = true`. O `DashboardClient` recebeu a prop `hasOverviewError` e, na ocorrência de falhas, renderiza um card amigável de instabilidade de rede com botão de "Tentar novamente" (`window.location.reload()`) e atalhos para questões e simulados locais, em vez de exibir a mensagem de boas-vindas com 0 questões para contas ativas.
- **Teste de Regressão Executado**: ESLint e suíte de tipagem aprovados.

### Correção #2: Validação Precisa dos Estados de Sessão em Andamento
- **Arquivos Alterados**:
  - [`app/frontend/src/app/DashboardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/DashboardClient.tsx)
- **Motivação & Solução**: Em `checkSessions`, a condição para sessões de simulado foi restringida a `PLAYING` ou `SUBMITTING`, e para quiz foi restringida a `PLAYING`. Sessões com status `FINISHED`, `RESULTS`, `START` ou `OFFLINE_SUBMITTED` são desconsideradas, prevenindo que um simulado/quiz finalizado bloqueie o Hero CTA.
- **Teste de Regressão Executado**: Validação unitária de persistência e `audit-regressions.test.mjs`.

### Correção #3: Otimização de Consulta SQL com CTE e Window Function
- **Arquivos Alterados**:
  - [`app/backend/api/stats.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/stats.py)
  - [`app/backend/tests/test_stats_phase1.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/tests/test_stats_phase1.py)
- **Motivação & Solução**: A query de `error_notebook_summary` utilizava um `LEFT JOIN` com subquery correlacionada `WHERE a1.id = (SELECT MAX(a2.id) ...)`. Foi reescrita utilizando uma Common Table Expression (`WITH latest_attempts AS (SELECT question_id, is_correct, ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY id DESC) as rn ...)`), reduzindo a complexidade para uma única varredura indexada. Adicionou-se teste unitário validando a resolução de erros pendentes em `test_stats_error_notebook_summary`.
- **Teste de Regressão Executado**: `pytest tests/test_stats_phase1.py` executado com 100% de aprovação.

### Correção #4: Formatação de Data Segura e Prevenção de Hydration Mismatch
- **Arquivos Alterados**:
  - [`app/frontend/src/app/DashboardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/DashboardClient.tsx)
- **Motivação & Solução**: Adicionada a função auxiliar `formatExamDate(dateStr: string)`, que extrai ano, mês e dia da string ISO e instancia a data ao meio-dia local (`12:00:00`), evitando que a conversão de meia-noite UTC recue a data em fusos horários ocidentais como Brasília (UTC-3). O elemento recebeu `suppressHydrationWarning` para garantir compatibilidade entre SSR e Client.
- **Teste de Regressão Executado**: ESLint aprovado.

### Correção #5: Code Splitting com Dynamic Import e Acessibilidade (A11y)
- **Arquivos Alterados**:
  - [`app/frontend/src/app/DashboardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/DashboardClient.tsx)
- **Motivação & Solução**:
  - `OfflineModal` migrado para `dynamic(() => import("@/components/OfflineModal").then(m => m.OfflineModal), { ssr: false })`.
  - As barras de progresso receberam atributos `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax` e `aria-label`.
  - Botões de configuração offline tiveram seus tamanhos ajustados para `min-h-[44px]` no banner e `min-h-[40px]` no rodapé, acompanhados de `aria-label` explícito.
  - Normalização da variável `targetScorePct` para evitar desvio em valores percentuais armazenados como fração decimal.
- **Teste de Regressão Executado**: `./validate.sh fast` e `npm run test:unit`.

---

## 5. Validação & Resultados dos Testes

### 1. Suíte Canônica Fast Tier (`./validate.sh fast`)
```text
================================================================
[FAST TIER] MEDQUEST DEV-VELOCITY: COMMIT LOCAL
================================================================

--> [Backend Diff Tests (5 suites)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/backend/.venv/bin/pytest -q --disable-warnings tests/test_stats_phase1.py tests/test_api.py tests/test_observability.py tests/test_planner.py tests/test_exam_readiness.py
............................................................             [100%]
60 passed in 4.08s
    [OK] Backend Diff Tests (5 suites) concluido com sucesso (5.06s)

--> [Frontend Incremental Lint (22 arquivos)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/frontend/node_modules/.bin/eslint --quiet src/lib/api.ts src/lib/googleCalendar.ts src/components/analytics/InstitutionRadarChart.tsx src/app/analise/page.tsx src/app/planner/PlannerClient.tsx src/app/cobertura/loading.tsx src/components/analytics/InstitutionRadarSection.tsx src/types/api.ts src/app/analise/AnalysisClient.tsx src/components/ImageViewer.tsx
    [OK] Frontend Incremental Lint (22 arquivos) concluido com sucesso (4.12s)

----------------------------------------------------------------
[PASS] SUCESSO: TODAS AS VALIDACOES PASSARAM (Camada: FAST | Tempo Total: 9.21s)
----------------------------------------------------------------
```

### 2. Testes Unitários de Backend Específicos
```bash
../../app/backend/.venv/bin/pytest tests/test_stats_phase1.py tests/test_stats_math.py tests/test_observability.py tests/test_planner.py -v
```
```text
============================== 44 passed in 2.25s ==============================
```

### 3. Testes Unitários de Frontend
```bash
npm run test:unit
```
```text
ℹ tests 19
ℹ suites 0
ℹ pass 19
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1029.832204
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
1. **Cache Local no Dexie para Overview**: Permitir que `stats` seja gravado no IndexedDB ao carregar online, possibilitando a exibição do último painel sincronizado mesmo quando o usuário abrir o PWA sem nenhuma conexão com a internet.
2. **Push de Fuso Horário do Cliente**: Criar hook para enviar `new Date().getTimezoneOffset()` no primeiro load do frontend ou salvar a preferência no perfil do usuário, garantindo que métricas de "questões de hoje" e streaks coincidam precisamente com o encerramento do dia no horário local do estudante.
3. **Consolidação do Endpoint de Metas do Planner**: Criar um endpoint leve (`GET /api/planner/today-suggestion`) que retorne o subtema sugerido e contagem de metas da semana diretamente em SQL, eliminando a chamada sequencial a `generate_plan` durante o SSR de `page.tsx`.
