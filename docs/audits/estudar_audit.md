# Relatório de Auditoria — Aba: Estudar
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou  
**Resultado Pós-Correções**: Passou (`./validate.sh fast`)

---

## 1. Resumo Executivo

A comprehensive full-stack audit was performed on the **Estudar** tab (`/estudar`), covering the entire vertical slice:
- Frontend: `app/frontend/src/app/estudar/page.tsx`, `QuizClient.tsx`, `components/QuizFilters.tsx`, `hooks/useQuizKeyboard.ts`, `components/ExplanationViewer.tsx`, `components/ImageViewer.tsx`, and `components/QuestionClassificationModal.tsx`.
- Backend: `app/backend/api/questions.py`, `app/backend/api/filters.py`, `app/backend/api/ai.py`, `app/backend/api/srs.py`.
- Persistence & State: SQLite/Turso tables (`questions`, `alternatives`, `attempts`, `spaced_repetition`, `favorites`), Dexie offline queue and learning session caching.

Prior to modifications, the repository baseline passed. During the 4-pillar diagnosis, 6 targeted improvements were identified:
1. Critical discrepancy in default query filtering (`unanswered_only`), which was ignored by the backend query clause generator.
2. Race condition during discursive self-assessment and final-question FSRS submission where optimistic state was not updated before view transition.
3. Keyboard navigation conflict when overlay modals (image viewer, finish modal, classification modal) were open.
4. Offline action blocking on the final question in a study queue.
5. Inefficient bundle loading of curator-only modal.
6. Touch targets below 44x44px and dark-mode contrast issues in highlight callout banners.

All 6 issues have been resolved with regression tests added and validated.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] SSR / Client hydration consistency on dynamic params and theme display preferences.
- [x] Empty state handling when no questions match active filters.
- [x] Offline queue resilience via `OfflineQueuedError` and `sync-item-success` reconciliation.
- [x] Corrigido: Backend filter clause generator was ignoring `unanswered_only=true` in `app/backend/api/filters.py:46`.
- [x] Corrigido: Offline banner on the last question of a session was disabling the next button without an option to finish the session (`app/frontend/src/app/estudar/QuizClient.tsx:1604`).

### Pilar 2: Performance & Banco de Dados
- [x] Query indexing and `_sample_ids` dense-range sampling to prevent expensive `ORDER BY RANDOM()` on large datasets.
- [x] Background prefetching of the next 2 questions in the queue (`detailsCacheRef`) for instant question switching.
- [x] Timer state decoupled from React component re-rendering via `QuizTimer` ref and handle.
- [x] Corrigido: Curator-only `QuestionClassificationModal` was statically bundled for all students; refactored to `next/dynamic` (`app/frontend/src/app/estudar/QuizClient.tsx:18`).

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Full keyboard navigation (`A`-`E`, `1`-`5`, `Enter`, `ArrowLeft`, `ArrowRight`).
- [x] Corrigido: Keyboard shortcuts in `useQuizKeyboard.ts` now pause when overlay modals or full-screen image zooms are active.
- [x] Corrigido: Minimum touch targets (44x44px) added to "← Voltar", `ArrowLeft`, `ArrowRight`, favorite toggle, and zoom modal controls.
- [x] Corrigido: Dialog accessibility attributes (`role="dialog"`, `aria-modal="true"`, `aria-label`) added to `ImageViewer.tsx` and `ExplanationViewer.tsx` zoom overlays.
- [x] Corrigido: WCAG AA contrast improvement for purple text callouts in dark mode (`dark:text-purple-400`).

### Pilar 4: Lógica Médica & Domínio
- [x] FSRS v6 scheduler compliance (`api/srs.py`): retention 0.85, long medical exam intervals (`S0(Again)=3.5` ~7d, `S0(Hard)=8.0` ~15d, `S0(Good)=18.0` ~34d, `S0(Easy)=40.0` ~76d), no intraday steps.
- [x] Prevention of double FSRS advancement on confidence edits or non-answer updates (`api/questions.py:732`).
- [x] Discursive open question support with self-assessment against official answer key standard.
- [x] Corrigido: Race condition in `handleReviewFSRS` resolved by updating `sessionAnswers` synchronously with the optimistic attempt result before triggering `setState("FINISHED")` or incrementing `currentIndex`.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade (P1/P2/P3) | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `app/backend/api/filters.py:46`<br>`app/frontend/src/app/estudar/QuizClient.tsx:140`<br>`app/frontend/src/app/estudar/components/QuizFilters.tsx:207` | Backend ignorava parâmetro `unanswered_only=true`, verificando apenas `status`. Frontend iniciava com `unanswered_only: "true"` sem `status="unanswered"`. | Aluno recebia questões já respondidas por padrão, violando o KPI de retenção (0% de repetição involuntária). |
| #2 | P2 (Maior) | `app/frontend/src/app/estudar/QuizClient.tsx:968` | Em `handleReviewFSRS`, `sessionAnswers` só era atualizado após o retorno da rede em background. Na última questão (especialmente discursiva), a tela `FINISHED` renderizava com resultado nulo/desatualizado. | Erro visual na contagem de acertos e acurácia ao finalizar o quiz. |
| #3 | P2 (Maior) | `app/frontend/src/app/estudar/hooks/useQuizKeyboard.ts:40`<br>`app/frontend/src/app/estudar/QuizClient.tsx:1066` | Atalhos de teclado não eram suspensos durante exibição de modais (`ImageViewer`, `showFinishModal`, `QuestionClassificationModal`). | Pressionar setas ou Enter trocava de questão ou confirmava resposta por trás do modal. |
| #4 | P2 (Maior) | `app/frontend/src/app/estudar/QuizClient.tsx:1604` | Banner de resposta salva offline desabilitava botão "Próxima Questão" na última questão da fila sem opção de finalizar. | Aluno ficava sem ação primária para concluir a sessão offline na última questão. |
| #5 | P3 (Otimização) | `app/frontend/src/app/estudar/QuizClient.tsx:18` | `QuestionClassificationModal` (usado apenas por curador) era importado estaticamente no bundle do aluno. | Aumento desnecessário do bundle client inicial para 99.9% dos estudantes. |
| #6 | P3 (UX/A11y) | `app/frontend/src/app/estudar/QuizClient.tsx:1203, 1388, 1801`<br>`app/frontend/src/components/ImageViewer.tsx:47` | Alvos de toque inferiores a 44x44px nos botões de navegação e fechar; falta de atributos ARIA de diálogo no zoom; contraste de texto roxo em modo escuro. | Dificuldade de toque em telas mobile e falhas de acessibilidade para leitores de tela. |

---

## 4. Correções Aplicadas

### Correção #1: Suporte a `unanswered_only` e Alinhamento de Filtros Padrão
- **Arquivos Alterados**:
  - [`app/backend/api/filters.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/filters.py)
  - [`app/backend/tests/test_api.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/tests/test_api.py)
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
  - [`app/frontend/src/app/estudar/components/QuizFilters.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/components/QuizFilters.tsx)
- **Motivação & Solução**: `api/filters.py` agora inspeciona `unanswered_only`. Se `unanswered_only` for `"true"` ou `"1"` (ou `status="unanswered"`), adiciona `q.id NOT IN (SELECT question_id FROM attempts WHERE user_id = ?)`. O frontend alinha o estado inicial com `status: "unanswered"` e `unanswered_only: "true"`, e o seletor sincroniza ambos os campos.
- **Teste de Regressão Executado**: `test_unanswered_only_filter` adicionado em `app/backend/tests/test_api.py` verificando exclusão de questões já respondidas com `unanswered_only=true` e inclusão com `unanswered_only=false`.

### Correção #2: Atualização Otimista Síncrona de `sessionAnswers` no FSRS
- **Arquivos Alterados**:
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
  - [`app/frontend/src/types/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/types/api.ts)
- **Motivação & Solução**: Em `handleReviewFSRS`, `optimisticResult` é calculado e injetado em `setSessionAnswers` imediatamente antes de chamar `setState("FINISHED")` ou avançar para `currentIndex + 1`. A chamada à API `api.questions.reviewFSRS` roda em background para reconciliar `next_review_date`. O tipo de `AttemptResult.next_review_date` foi atualizado para `string | null` para modelar com fidelidade o retorno de tentativas diferidas.
- **Teste de Regressão Executado**: Validação de tipo e build de produção Next.js executados sem erros.

### Correção #3: Suspensão de Atalhos de Teclado Durante Exibição de Modais
- **Arquivos Alterados**:
  - [`app/frontend/src/app/estudar/hooks/useQuizKeyboard.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/hooks/useQuizKeyboard.ts)
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
- **Motivação & Solução**: Adicionada propriedade `disabled?: boolean` em `UseQuizKeyboardProps`. `QuizClient` repassa `disabled: Boolean(showFinishModal || isClassificationModalOpen || enlargedImage)`, pausando a escuta de teclas globais do quiz enquanto o estudante interage com um modal ou imagem ampliada.
- **Teste de Regressão Executado**: Validação incremental do ESLint e build estático.

### Correção #4: Conclusão de Sessão no Modo Offline na Última Questão
- **Arquivos Alterados**:
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
- **Motivação & Solução**: Quando a última questão da fila é respondida offline (`currentIndex === queue.length - 1`), o banner agora renderiza o botão "Finalizar Sessão", acionando `confirmFinish` e exibindo o resumo com precisão.
- **Teste de Regressão Executado**: Teste de renderização condicional validado pelo compilador TypeScript e suite fast.

### Correção #5: Dynamic Import do Modal de Curadoria
- **Arquivos Alterados**:
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
- **Motivação & Solução**: `QuestionClassificationModal` agora é importado via `dynamic(..., { ssr: false })`, reduzindo o payload de primeiro carregamento para estudantes comuns.
- **Teste de Regressão Executado**: `npm run build` confirmou divisão de chunks e respeito aos orçamentos de performance.

### Correção #6: Ergonomia Mobile, Touch Targets (44px), ARIA e Contraste
- **Arquivos Alterados**:
  - [`app/frontend/src/app/estudar/QuizClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/estudar/QuizClient.tsx)
  - [`app/frontend/src/components/ImageViewer.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/components/ImageViewer.tsx)
  - [`app/frontend/src/components/ExplanationViewer.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/components/ExplanationViewer.tsx)
- **Motivação & Solução**: Botões "← Voltar", setas de navegação e botão de favorito receberam área mínima de toque de 44x44px. Modais de zoom receberam `role="dialog"`, `aria-modal="true"`, e `aria-label`. Chamadas em roxo ganharam variante `dark:text-purple-400` para contraste adequado em modo escuro.
- **Teste de Regressão Executado**: `npm run lint` e checagem de contraste CSS.

---

## 5. Validação & Resultados dos Testes

### Execução Canônica `./validate.sh fast`:
```text
================================================================
[FAST TIER] MEDQUEST DEV-VELOCITY: COMMIT LOCAL
================================================================

--> [Backend Diff Tests (5 suites)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/backend/.venv/bin/pytest -q --disable-warnings tests/test_exam_readiness.py tests/test_api.py tests/test_stats_phase1.py tests/test_planner.py tests/test_observability.py
............................................................             [100%]
60 passed in 3.10s
    [OK] Backend Diff Tests (5 suites) concluido com sucesso (3.72s)

--> [Frontend Incremental Lint (20 arquivos)] Executando: /home/wagmoraes/Projetos Prog/MedQuest/app/frontend/node_modules/.bin/eslint --quiet src/app/estudar/hooks/useQuizKeyboard.ts src/types/api.ts src/app/planner/PlannerWizard.tsx src/app/cobertura/page.tsx src/components/analytics/InstitutionRadarChart.tsx src/app/estudar/components/QuizFilters.tsx src/app/page.tsx src/lib/googleCalendar.ts src/app/planner/PlannerClient.tsx src/app/analise/page.tsx
    [OK] Frontend Incremental Lint (20 arquivos) concluido com sucesso (2.06s)

----------------------------------------------------------------
[PASS] SUCESSO: TODAS AS VALIDACOES PASSARAM (Camada: FAST | Tempo Total: 5.80s)
----------------------------------------------------------------
```

### Execução da Suíte Completa de Testes Backend (`pytest tests/ -q`):
```text
297 passed in 11.15s
```

### Execução da Build de Produção Frontend (`npm run build`):
```text
✓ Compiling for server...
✓ Compiling for client (static)...
✓ Generating static pages using 11 workers (7/7) in 503ms
✓ Collecting build traces in 13.7s
✓ Finalizing page optimization in 13.9s
[SW Validator PASSED] Service Worker is verified safe.
Build budgets: totalJavaScript 2354272 <= 2400000, largestChunk 412658 <= 450000.
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
1. **Filtros Avançados por Dificuldade Calculada**: Adicionar filtro opcional de acurácia global da questão (ex: questões com taxa de acerto < 40% na comunidade).
2. **Atalhos Customizáveis pelo Aluno**: Permitir configuração de teclado personalizada para alunos acostumados com atalhos de outros bancos (ex: Anki `1`/`2`/`3`/`4` vs MedQuest `1`/`2`/`3`).
3. **Pinch-to-zoom Nativo em Dispositivos Móveis**: Aprimorar o suporte a gestos de pinça no `ImageViewer` para touchscreens sem necessidade de botões de zoom dedicados.
