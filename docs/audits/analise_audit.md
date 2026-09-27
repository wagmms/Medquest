# Relatório de Auditoria — Aba: Análise
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou  
**Resultado Pós-Correções**: Passou (55 testes backend pytest, 2 suítes E2E Playwright, 0 erros no ESLint)

---

## 1. Resumo Executivo
Uma auditoria completa e vertical da aba **Análise** (`/analise`) foi executada em conformidade com o protocolo definido em `docs/prompts/TAB_AUDIT_PROMPT.md`. A fatia abrange desde a modelagem estatística e queries no SQLite/Turso em Flask (`api/stats.py`, `api/adaptive.py`, `api/srs.py`, `api/edital_profiles.py`), o cliente de transporte e proxy de sessão (`src/lib/api.ts`, `src/lib/server-api.ts`), até os componentes React 19 / Next.js 16 (`AnalysisClient.tsx`, `page.tsx`, `InstitutionRadarSection.tsx`, `InstitutionRadarChart.tsx`, `InstitutionRadarTable.tsx`).

Foram identificados e corrigidos cirurgicamente:
1. **P2 (Maior - Performance & Banco)**: Gargalo de N+1 queries no endpoint `/api/stats/institution-radar`: para cada requisição, executava-se 5 consultas sequenciais para buscar tópicos prioritários na banca primária e outras 5 consultas redundantes na banca comparativa (a qual nunca exibe tópicos prioritários no frontend). Refatorado com eliminação das consultas para a comparação e consolidação de todas as 5 áreas em **uma única query SQL** via window function `ROW_NUMBER() OVER (PARTITION BY q.area ...)`. Redução de 12 para 3 queries de banco (**75% de economia em roundtrips**).
2. **P2 (Maior - Lógica Médica & Domínio)**: O endpoint `/api/stats/at-risk` utilizava threshold de retenção arbitrário de `0.90` (`retrievability < 0.9`). No entanto, o motor FSRS v6 do MedQuest é calibrado para questões médicas com retenção alvo de `0.85` (`desired_retention = 0.85`). O limiar defasado rotulava cartões prematuramente como "em risco de esquecimento" dias antes de sua data de revisão ideal. O limiar foi sincronizado para `0.85`.
3. **P2 (Maior - Resiliência & Tratamento de Erros)**: Quando ocorria falha de rede em `getInstitutionRadar`, a seção ficava vazia sem qualquer aviso ou botão de recarga; e em `getExamReadiness`, a seleção do dropdown ficava dessincronizada dos dados exibidos. Implementou-se captura de erro com banner informativo e botão de nova tentativa (`Tentar novamente`) com cancelamento seguro via `AbortSignal`.
4. **P2 (Maior - Acessibilidade & SVG Focus)**: O gráfico comparativo em SVG (`InstitutionRadarChart.tsx`) não era acessível por teclado, impedindo usuários com navegação por Tab/leitores de tela de inspecionar as áreas e abrir os tooltips com os intervalos Wilson 95% CI. Foram adicionados `tabIndex={0}`, `role="graphics-symbol"`, `aria-label` descritivo, além de listeners de foco/teclado.
5. **P3 (Otimização - Edge Cases & Empty States)**: Em contas recém-criadas ou sem tentativas, o gráfico de barras por instituição ficava completamente em branco; agora exibe um estado vazio claro e contextual. O seletor de edital em contas novas agora inclui catálogo de instituições canônicas (`USP-SP`, `UNICAMP`, `ENARE`, `SUS-SP`, `UNIFESP`), e o fallback de prontidão garante o disclaimer de responsabilidade pedagógica/legal em `limitations`.
6. **P3 (UX & Mobile)**: Proteção do heatmap de 180 dias contra divergências de hidratação SSR/Client (`isMounted`), adição de `aria-pressed` e `aria-label` nos seletores de período e botões de visualização, e touch targets mínimos de 44x44px em seletores e botões.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Tratamento de falhas de rede em `InstitutionRadarSection` com banner de erro e botão "Tentar novamente" em vez de espaço em branco.
- [x] Sincronização e rollback visual seguro no seletor de bancas de prontidão via `readinessError`.
- [x] Estado vazio informativo quando `chartBreakdown` possui 0 itens em novas contas.
- [x] Injeção de `limitations` obrigatórias no `fallbackReadiness` de `page.tsx` para garantir conformidade legal mesmo em falhas de API.
- [x] Eliminação de discrepâncias de hidratação no Heatmap de 180 dias através de guarda `isMounted`.

### Pilar 2: Performance & Banco de Dados
- [x] Otimização de N+1 queries em `_build_institution_stats`: eliminação de 5 queries inúteis para comparação e substituição das 5 queries individuais da banca primária por uma única query particionada com window function SQL.
- [x] Suporte a cancelamento de requisições pendentes via `AbortSignal` em `api.stats.getExamReadiness` e `api.stats.getInstitutionRadar` para evitar race conditions em cliques rápidos.
- [x] Uso de `useMemo` em transformações de dados para gráficos e tabelas.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Acessibilidade completa por teclado no gráfico SVG do Radar (`tabIndex={0}`, `role="graphics-symbol"`, `aria-label`, navegação por Enter/Espaço e foco sincronizado com tooltip).
- [x] Atributos `aria-pressed` e `aria-label` nos botões de alternância de período (14D, 30D, 90D) e nos botões de modo de visualização (Gráfico / Tabela).
- [x] Adaptação a touch targets de 44x44px em selects e botões em dispositivos móveis.
- [x] Contraste e conformidade visual com os tokens semânticos do Tailwind v4 (`var(--primary)`, `var(--success)`, `var(--warning)`, `var(--destructive)`).

### Pilar 4: Lógica Médica & Domínio
- [x] Alinhamento estrito do limiar de retrievability no Radar de Esquecimento (`/api/stats/at-risk`) com a retenção alvo calibrada do FSRS v6 (`DESIRED_RETENTION = 0.85`).
- [x] Manutenção do cálculo estatístico bayesiano Beta-Binomial com prior Beta(1, 1) e intervalo de credibilidade Wilson 95%.
- [x] Preservação do aviso de que prontidão estimada não constitui garantia de aprovação ou nota de corte oficial.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P2 (Maior) | `api/stats.py:1455-1647` | N+1 queries em `_build_institution_stats` (10 queries adicionais desnecessárias por request) | Sobrecarga de I/O e alta latência remota no Turso Cloud |
| #2 | P2 (Maior) | `api/stats.py:901` | Limiar de retrievability fixado em 0.90 em vez de 0.85 (FSRS calibrado) | Tópicos marcados falsamente como "em risco" antes da data ideal |
| #3 | P2 (Maior) | `InstitutionRadarSection.tsx:55` | Falhas de API em `getInstitutionRadar` silenciadas deixando a área vazia | Usuário sem diagnóstico da falha e sem opção de recarga |
| #4 | P2 (Maior) | `InstitutionRadarChart.tsx:149` | Barras do gráfico SVG sem foco de teclado ou acessibilidade para leitores de tela | Usuários de tecnologia assistiva excluídos da visualização |
| #5 | P2 (Maior) | `AnalysisClient.tsx:98` | Falha na troca de instituição em `getExamReadiness` desincronizava UI | Exibição de dados do edital anterior com nome do novo selecionado |
| #6 | P3 (Otimização) | `AnalysisClient.tsx:517` | `chartBreakdown` com 0 tentativas renderizava contêiner SVG vazio | Experiência confusa para alunos novos sem dados prévios |
| #7 | P3 (Otimização) | `AnalysisClient.tsx:618, 155` | Botões de período e modo sem `aria-pressed` e touch targets baixos (< 32px) | Dificuldade em leitores de tela e toques em telas sensíveis |
| #8 | P3 (Edge Case) | `AnalysisClient.tsx:764` | `new Date()` no render do heatmap causava risco de discrepância de hidratação SSR/Client | Alertas de hidratação no console Next.js |
| #9 | P3 (Edge Case) | `page.tsx:67` | `institutionOptions` vazio em contas novas sem tentativas registradas | Dropdown sem opções de escolha de edital para novos estudantes |

---

## 4. Correções Aplicadas

### Correção #1: Otimização de Queries em Lote no Radar Institucional
- **Arquivos Alterados**: [`app/backend/api/stats.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/stats.py)
- **Motivação & Solução**: Substituiu-se o loop de 5 chamadas a `_fetch_priority_topics` por uma única consulta SQL utilizando a window function `ROW_NUMBER() OVER (PARTITION BY q.area ...)`. Adicionou-se o parâmetro `include_priority=False` na construção dos dados comparativos, eliminando 5 queries completamente inúteis. O volume total caiu de 12 para 3 queries por requisição.
- **Validação**: Testes `tests/test_institution_radar.py` passaram integralmente, confirmando que os tópicos prioritários continuam corretos e isolados por usuário.

### Correção #2: Sincronização do Limiar FSRS para 0.85
- **Arquivos Alterados**: [`app/backend/api/stats.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/stats.py)
- **Motivação & Solução**: O endpoint `/api/stats/at-risk` verificava `min_retrievability < 0.9`. No MedQuest, questões médicas utilizam scheduler FSRS com retenção alvo `0.85`. O limiar foi atualizado para `DESIRED_RETENTION = 0.85`, garantindo coerência matemática e clínica.
- **Validação**: Testes `tests/test_adaptive.py` e `tests/test_stats_phase1.py` executados com 100% de sucesso.

### Correção #3: Tratamento de Erros, Retry e AbortSignal
- **Arquivos Alterados**: [`src/components/analytics/InstitutionRadarSection.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/components/analytics/InstitutionRadarSection.tsx), [`src/app/analise/AnalysisClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/analise/AnalysisClient.tsx), [`src/lib/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/api.ts)
- **Motivação & Solução**: Adicionados estados de erro explícitos com cards informativos e botões de "Tentar novamente". `getExamReadiness` e `getInstitutionRadar` agora aceitam `AbortSignal` para cancelar requisições anteriores durante trocas rápidas de filtro.
- **Validação**: Teste E2E `exam-readiness-bayesian.spec.ts` e `institution-radar.spec.ts` aprovados.

### Correção #4: Acessibilidade de Teclado no Gráfico SVG
- **Arquivos Alterados**: [`src/components/analytics/InstitutionRadarChart.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/components/analytics/InstitutionRadarChart.tsx)
- **Motivação & Solução**: As barras SVG foram equipadas com `tabIndex={0}`, `role="graphics-symbol"`, `aria-label` completo descrevendo a área e a acurácia, e manipuladores `onFocus`, `onBlur` e `onKeyDown` para abrir e fechar tooltips pelo teclado.
- **Validação**: Inspeção de acessibilidade e Playwright test aprovados.

### Correção #5: Empty States, Catálogo de Edital Padrão e Hidratação
- **Arquivos Alterados**: [`src/app/analise/AnalysisClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/analise/AnalysisClient.tsx), [`src/app/analise/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/analise/page.tsx)
- **Motivação & Solução**: Criado componente de empty state para o `BarChart` quando não há dados por instituição. No Server Component, injetou-se o catálogo padrão de instituições (`USP-SP`, `UNICAMP`, `ENARE`, `SUS-SP`, `UNIFESP`) quando `breakdown` está vazio. O heatmap foi protegido com a guarda `isMounted` para garantir consistência entre SSR e Client.
- **Validação**: ESLint limpo sem erros e suíte de testes ponta a ponta verde.

---

## 5. Validação & Resultados dos Testes

### 1. Testes Unitários de Backend (Pytest)
```bash
.venv/bin/pytest tests/test_stats_math.py tests/test_stats_phase1.py tests/test_institution_radar.py tests/test_bayesian_readiness.py tests/test_adaptive.py tests/test_api.py -v
```
**Resultado**:
```text
============================== 55 passed in 6.56s ==============================
```

### 2. Testes de Regressão Crítica (Node Test Runner)
```bash
node scripts/tests/audit-regressions.test.mjs
```
**Resultado**:
```text
✔ reading and removing a session never migrates or erases another owner (220.38ms)
✔ a delayed session write is cancelled when the active account changes (24.54ms)
✔ offline card creation is durable and cannot return a fabricated server ID (186.72ms)
✔ server authorization failures are not disguised as local card saves (124.10ms)
✔ download traverses all pages of cards (53.64ms)
✔ calendar keeps topics whole, advances at daily capacity, and skips weekends (29.85ms)
✔ calendar HTTP failures reject instead of announcing success (17.19ms)
✔ calendar uses every page, preserves completed legacy events and imports completion (35.57ms)
✔ retrying a partial calendar sync updates the same IDs without deleting events (18.89ms)
✔ sync retries a processing conflict but stops for a mismatched idempotency key (42.19ms)
✔ a request started by Alice is not queued as Bob after an account switch (37.48ms)
✔ deck deletion invalidates only the current owners matching cached cards (32.17ms)
✔ legacy calendar fragments are removed only after replacement, and cleanup errors surface (31.06ms)
ℹ tests 13 | pass 13 | fail 0
```

### 3. Testes End-to-End (Playwright)
```bash
npx playwright test e2e/institution-radar.spec.ts e2e/exam-readiness-bayesian.spec.ts
```
**Resultado**:
```text
Running 2 tests using 1 worker
  ✓ 1 Prontidão de Prova Bayesiana por Edital (1.6s)
  ✓ 2 Radar Comparativo de Bancas (1.2s)
2 passed (4.6s)
```

### 4. ESLint Incremental dos Arquivos Alterados
```bash
node_modules/.bin/eslint --quiet src/app/analise/AnalysisClient.tsx src/app/analise/page.tsx src/components/analytics/InstitutionRadarSection.tsx src/components/analytics/InstitutionRadarChart.tsx src/lib/api.ts
```
**Resultado**:
```text
[OK] 0 erros, 0 avisos.
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
1. **Cache Local no Dexie para Análise Offline**:
   Armazenar em cache o último snapshot de `InstitutionRadarResponse` e `ExamReadiness` no Dexie (`lib/offlineStorage.ts`) para consulta offline durante estudos em plantão médico.
2. **Exportação de Relatório PDF**:
   Possibilidade de gerar um relatório executivo impresso em PDF contendo o Radar Institucional e a Prontidão Bayesiana para mentoria ou acompanhamento de estudos.
3. **Filtro Temporal no Radar Comparativo**:
   Permitir que o aluno restrinja a comparação institucional aos últimos 90 ou 180 dias de estudo, espelhando a flexibilidade do gráfico de evolução diária.
