# MedQuest — Protocolo & Prompt de Auditoria Modular por Aba
# (Tab-by-Tab Full-Stack Audit & Optimization Protocol)

Este documento define o protocolo oficial e o prompt executável para auditar, corrigir bugs, otimizar performance e aprimorar a experiência de cada aba do **MedQuest** individualmente.

---

## 1. Como Usar

Para iniciar a auditoria de qualquer aba, envie a seguinte mensagem para o agente no chat:

```markdown
Por favor, execute uma auditoria completa na aba {{TAB_NAME}} seguindo rigorosamente as diretrizes e o protocolo definidos em `docs/prompts/TAB_AUDIT_PROMPT.md`.
```

*(Substitua `{{TAB_NAME}}` por uma das abas do [Catálogo de Arquitetura por Aba](#5-catálogo-de-arquitetura-por-aba), como `Dashboard`, `Planner`, `Simulado`, `Estudar`, `Revisão Ativa`, `Cobertura`, `Análise`, ou `Temas`).*

---

## 2. Prompt Mestre de Execução (Autonomous Agent Prompt)

Copie e use o bloco abaixo quando desejar um prompt autocontido e explícito para o agente:

```text
Você é um Engenheiro de Software Full-Stack Sênior e Especialista em EdTech Médica auditando a aba [{{TAB_NAME}}] do MedQuest.

Seu objetivo é investigar a fundo a fatia vertical completa desta aba (Frontend, State/Dexie, APIs Flask, Queries Turso/SQLite e Lógica Médica/FSRS), identificar bugs e gargalos, implementar correções cirúrgicas e registrar um relatório detalhado.

Siga rigorosamente estas fases:

### FASE 0: Linha de Base (Baseline)
1. Execute `./validate.sh fast` para validar a integridade atual do repositório antes de alterar qualquer arquivo.
2. Se houver falhas prévias, registre-as como referência para não confundi-las com novas alterações.

### FASE 1: Diagnóstico dos 4 Pilares
Consulte os arquivos mapeados para [{{TAB_NAME}}] no catálogo de `docs/prompts/TAB_AUDIT_PROMPT.md` e inspecione o código através dos 4 Pilares:
1. Correção & Edge Cases:
   - Erros de hidratação e discrepâncias SSR/Client (React 19 / Next.js 16).
   - Estados vazios (conta recém-criada, 0 questões, 0 dados no filtro selecionado).
   - Comportamento offline (fila do Dexie em `lib/sync.ts`, reconexão, tratamento de `OfflineQueuedError`).
   - Resiliência contra falhas de API: nunca exibir 0 em vez de estado de erro/retry se a requisição falhar.
   - Sessão de visitante vs Clerk (`medquest_guest_session`, `x-internal-guest-id`).
2. Performance & Banco de Dados:
   - Eficiência de queries no endpoint backend: eliminação de N+1, uso de índices compostos, paginação ou limites de payload.
   - Respeito à camada `app/backend/api/db.py` (reconexão automática Turso, não mascarar erros de stream expirado).
   - Otimização do bundle frontend: dynamic imports para componentes pesados (gráficos, modais, editores).
   - Prevenção de re-renderizações desnecessárias e loops em useEffects.
3. UX, Acessibilidade & Mobile:
   - Conformidade com Tailwind CSS v4 (uso de variáveis semânticas de cores/superfícies de `globals.css`).
   - Contraste e compatibilidade com temas Dark/Light.
   - Responsividade mobile: tabelas largas, gavetas vs sidebars, touch targets mínimos (44x44px).
   - Acessibilidade: atributos ARIA (`aria-current`, `aria-expanded`, `aria-controls`, `aria-pressed`, `aria-label`), acessibilidade por teclado sem armadilhas de foco.
4. Lógica Médica & Domínio:
   - Se a aba envolve repetição espaçada: conformidade com o FSRS v6 (`api/srs.py`, retention 0.85, intervalos longos, sem passos intradia, prevenção de avanço duplo).
   - Se a aba envolve simulados: persistência segura do cronômetro, recuperação de recarregamento, gabarito correto e idempotência no envio.
   - Se a aba envolve cronograma/planner: datas ISO sem quebra com horários UTC, deduplicação de tópicos concluídos.

### FASE 2: Execução Segura e Cirúrgica
1. Priorize os problemas encontrados por severidade:
   - P1 (Crítico): Perda de progresso, dados incorretos, quebra de navegação ou atalhos bloqueados.
   - P2 (Maior): Erros de estado em falhas de rede, dados defasados após filtros, contagens inconsistentes, acessibilidade que prejudica navegação.
   - P3 (Otimização): Micro-interações, layout mobile, pequenos ganhos de payload ou renderização.
2. Aplique as correções estritamente no escopo da aba [{{TAB_NAME}}]. NÃO altere esquemas de banco globais ou componentes de outras abas sem extrema necessidade.
3. Para cada correção aplicada, rode os testes específicos ou `./validate.sh fast` para garantir ausência de regressões.

### FASE 3: Validação Final
1. Execute `./validate.sh fast` para garantir que toda a suíte rápida permaneça verde.
2. Se a aba tiver testes unitários ou E2E dedicados, execute-os explicitamente.

### FASE 4: Documentação
Crie ou atualize o arquivo de log em `docs/audits/{{TAB_SLUG}}_audit.md` utilizando o modelo padronizado definido em `docs/prompts/TAB_AUDIT_PROMPT.md`.
```

---

## 3. Diretrizes Críticas de Execução & Regras do MedQuest

Todo agente executando esta auditoria **deve** respeitar as regras canônicas do projeto (`GEMINI.md`):

1. **Camada de Abstração do Banco**:
   - Todas as operações em Turso/LibSQL devem usar `app/backend/api/db.py` (`get_db()`, `TursoConnection`).
   - Nunca compartilhe conexões nativas do `libsql` entre threads.
   - Nunca capture erros de `stream not found`, `baton`, `hrana`, `404/408` de forma a impedir a reconexão automática segura de `_execute_with_reconnect`.
2. **Algoritmo FSRS v6 (`api/srs.py`)**:
   - `desired_retention = 0.85`.
   - `learning_steps = ()` e `relearning_steps = ()` (sem passos de minutos intradia; erro agenda para D+7 em questões e D+1 em flashcards).
   - Nunca avance o estado FSRS repetidamente se o usuário apenas alterar anotações sem submeter nova resposta.
3. **Frontend & Tailwind v4**:
   - Next.js 16 App Router + React 19 + Tailwind v4. Não utilize `tailwind.config.js` legado.
   - Não confie em cabeçalhos de identidade vindos diretamente do navegador; use o contexto de sessão autenticada ou guest sanitizado pelo proxy.
4. **Comando de Testes Canônico**:
   - Sempre valide via `./validate.sh fast`.

---

## 4. Matriz dos 4 Pilares de Avaliação

| Pilar | Foco Principal | Verificações Chave |
| :--- | :--- | :--- |
| **1. Correção & Edge Cases** | Robustez funcional e resiliência | • Erros de hidratação / console Next.js.<br>• Falhas de API retornam estado com retry (não mascarar com 0/vazio).<br>• Estado offline via Dexie (`lib/offlineStorage.ts`) e tratamento de `OfflineQueuedError`.<br>• Sessões de usuário autenticado (Clerk) e visitante (`x-internal-guest-id`). |
| **2. Performance & Dados** | Latência e consumo de recursos | • Eliminação de N+1 queries no Flask.<br>• Paginação e limite em consultas grandes.<br>• Reutilização de conexões Turso.<br>• Divisão de código com dynamic imports (`next/dynamic`) em componentes pesados.<br>• Memoização de filtros e listas no cliente (`useMemo`, `useCallback`). |
| **3. UX, A11y & Mobile** | Ergonomia, design system e acessibilidade | • Variáveis semânticas de cor do tema (`bg-surface`, `text-foreground`, etc.).<br>• Contraste adequado em Dark e Light mode.<br>• Tabelas e layouts com adaptação mobile sem overflow horizontal indesejado.<br>• Atributos `aria-*` em botões, toggles, abas e modais.<br>• Navegação completa por teclado sem traps de foco. |
| **4. Lógica Médica & Domínio** | Regras de negócio e aprendizado adaptativo | • FSRS v6 calibrado para questões médicas longas.<br>• Temporizador do simulado persistente contra refresh/queda de conexão.<br>• Normalização de datas no Planner (evitar concatenação inválida com `T00:00:00`).<br>• Deduplicação de tópicos concluídos (evitar progresso > 100%). |

---

## 5. Catálogo de Arquitetura por Aba

Utilize este catálogo para identificar exatamente quais arquivos, componentes, endpoints e tabelas pertencem a cada aba:

### 1. Dashboard (`/`)
* **Slug**: `dashboard`
* **Rota Frontend**: `app/frontend/src/app/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/DashboardClient.tsx`
* **Componentes Associados**: `src/components/Sidebar.tsx`, `src/components/TopNav.tsx`, `src/components/WebVitals.tsx`
* **Endpoints Backend**:
  * `GET /api/stats/overview`
  * `GET /api/stats/user-streak`
  * `GET /api/stats/benchmark`
  * `GET /api/stats/bottlenecks`
  * `GET /api/stats/domain-summary`
  * `GET /api/stats/error-notebook-summary`
  * `GET /api/plan/config`
  * `GET /api/plan/progress`
* **Arquivos Backend**: `app/backend/api/stats.py`, `app/backend/api/plan.py`
* **Tabelas do Banco**: `attempts`, `spaced_repetition`, `planner_progress`, `planner_config`, `telemetry_daily_aggregates`

### 2. Planner (`/planner`)
* **Slug**: `planner`
* **Rota Frontend**: `app/frontend/src/app/planner/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/planner/PlannerClient.tsx`
* **Componentes Associados**: `app/frontend/src/app/planner/PlannerWizard.tsx`, `app/frontend/src/lib/googleCalendar.ts`, `app/frontend/src/lib/plannerData.ts`
* **Endpoints Backend**:
  * `GET /api/plan/config`
  * `POST /api/plan/config`
  * `POST /api/plan/generate`
  * `GET /api/plan/progress`
  * `POST /api/plan/progress`
  * `POST /api/plan/reset`
  * `GET /api/plan/topic-progress`
  * `POST /api/plan/topic-progress`
* **Arquivos Backend**: `app/backend/api/plan.py`
* **Tabelas do Banco**: `planner_config`, `planner_schedule`, `planner_progress`, `planner_topic_progress`

### 3. Simulado (`/simulado`)
* **Slug**: `simulado`
* **Rota Frontend**: `app/frontend/src/app/simulado/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/simulado/SimuladoClient.tsx`
* **Componentes Associados**: `app/frontend/src/components/QuizTimer.tsx`, `app/frontend/src/lib/simuladoPackage.ts`, `app/frontend/src/lib/sessionState.ts`
* **Endpoints Backend**:
  * `GET /api/questions/institutions`
  * `GET /api/questions/simulado-years`
  * `POST /api/questions/simulado-package`
  * `POST /api/simulado/sessions`
  * `GET /api/simulado/sessions`
  * `POST /api/questions/attempt`
* **Arquivos Backend**: `app/backend/api/questions.py`, `app/backend/api/sessions.py`
* **Tabelas do Banco**: `simulado_sessions`, `questions`, `alternatives`, `attempts`

### 4. Estudar / Caderno de Questões (`/estudar`)
* **Slug**: `estudar`
* **Rota Frontend**: `app/frontend/src/app/estudar/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/estudar/QuizClient.tsx`
* **Componentes Associados**: 
  * `app/frontend/src/app/estudar/components/QuizFilters.tsx`
  * `app/frontend/src/app/estudar/hooks/useQuizKeyboard.ts`
  * `app/frontend/src/components/ExplanationViewer.tsx`
  * `app/frontend/src/components/ImageViewer.tsx`
  * `app/frontend/src/components/QuestionClassificationModal.tsx`
  * `app/frontend/src/components/SubjectTreeSelector.tsx`
* **Endpoints Backend**:
  * `GET /api/questions/list`
  * `POST /api/questions/attempt`
  * `POST /api/questions/favorite`
  * `POST /api/questions/ai-explain`
  * `GET /api/questions/filters`
* **Arquivos Backend**: `app/backend/api/questions.py`, `app/backend/api/ai.py`, `app/backend/api/srs.py`
* **Tabelas do Banco**: `questions`, `alternatives`, `explanations`, `question_images`, `attempts`, `favorites`, `spaced_repetition`

### 5. Revisão Ativa / Flashcards (`/revisao-ativa`)
* **Slug**: `revisao-ativa`
* **Rota Frontend**: `app/frontend/src/app/revisao-ativa/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/revisao-ativa/FlashcardClient.tsx`
* **Componentes Associados**:
  * `app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx`
  * `app/frontend/src/lib/ankiConnect.ts`
  * `app/frontend/src/lib/flashcardCache.ts`
  * `app/frontend/src/lib/normalizeFlashcard.ts`
* **Endpoints Backend**:
  * `GET /api/flashcards/due`
  * `POST /api/flashcards/review`
  * `POST /api/flashcards/sync`
  * `POST /api/flashcards/create`
* **Arquivos Backend**: `app/backend/api/flashcards.py`, `app/backend/api/srs.py`, `app/backend/api/anki.py`
* **Tabelas do Banco**: `flashcards`, `spaced_repetition`

### 6. Cobertura de Edital (`/cobertura`)
* **Slug**: `cobertura`
* **Rota Frontend**: `app/frontend/src/app/cobertura/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/cobertura/CoverageClient.tsx`
* **Endpoints Backend**:
  * `GET /api/stats/coverage`
  * `GET /api/stats/heatmaps`
  * `GET /api/edital-profiles`
* **Arquivos Backend**: `app/backend/api/stats.py`, `app/backend/api/edital_profiles.py`
* **Tabelas do Banco**: `questions`, `attempts`, `planner_topic_progress`

### 7. Análise de Desempenho (`/analise`)
* **Slug**: `analise`
* **Rota Frontend**: `app/frontend/src/app/analise/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/analise/AnalysisClient.tsx`
* **Componentes Associados**:
  * `app/frontend/src/components/analytics/InstitutionRadarChart.tsx`
  * `app/frontend/src/components/analytics/InstitutionRadarSection.tsx`
  * `app/frontend/src/components/analytics/InstitutionRadarTable.tsx`
* **Endpoints Backend**:
  * `GET /api/stats/analytics`
  * `GET /api/stats/performance`
  * `GET /api/adaptive/profile`
* **Arquivos Backend**: `app/backend/api/stats.py`, `app/backend/api/adaptive.py`
* **Tabelas do Banco**: `attempts`, `spaced_repetition`, `questions`

### 8. Jornada por Temas (`/temas`)
* **Slug**: `temas`
* **Rota Frontend**: `app/frontend/src/app/temas/page.tsx`
* **Componente Cliente**: `app/frontend/src/app/temas/ThemeClient.tsx`
* **Componentes Associados**: `app/frontend/src/lib/themeJourney.ts`
* **Endpoints Backend**:
  * `GET /api/themes/list`
  * `GET /api/themes/topics`
  * `GET /api/adaptive/theme-diagnostic`
* **Arquivos Backend**: `app/backend/api/themes.py`, `app/backend/api/adaptive.py`
* **Tabelas do Banco**: `questions`, `attempts`, `planner_topic_progress`

### 9. Recursos Globais & Modais Compartilhados
* **Modo Plantão / Offline**: `app/frontend/src/components/OfflineModal.tsx`, `app/frontend/src/components/OfflinePanel.tsx`, `app/frontend/src/lib/sync.ts`, `app/frontend/src/lib/db.ts`
* **Minha Conta / Perfil**: `app/frontend/src/components/AccountModal.tsx`
* **Tour de Onboarding**: `app/frontend/src/components/OnboardingTour.tsx`
* **Notificações & WebPush**: `app/backend/api/notifications.py`, `app/backend/api/webpush.py`

---

## 6. Modelo de Relatório de Auditoria (`docs/audits/<tab_name>_audit.md`)

Ao concluir a auditoria de qualquer aba, crie ou atualize o arquivo correspondente em `docs/audits/{{TAB_SLUG}}_audit.md` utilizando exatamente a estrutura abaixo:

```markdown
# Relatório de Auditoria — Aba: {{TAB_NAME}}
**Data**: AAAA-MM-DD  
**Status da Linha de Base**: [Passou / Falhou]  
**Resultado Pós-Correções**: [Passou / Falhou] (`./validate.sh fast`)

---

## 1. Resumo Executivo
Breve descrição do estado geral da aba, principais pontos fortes e vulnerabilidades críticas identificadas.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Item verificado e saudável
- [ ] Item com problema identificado: descrição do erro, arquivo e linha.

### Pilar 2: Performance & Banco de Dados
- [x] Item verificado e saudável
- [ ] Gargalo identificado: tempo de resposta, N+1 queries, re-renderizações excessivas.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Conformidade visual e tokens Tailwind v4
- [ ] Problemas de contraste, overflow horizontal ou quebra em telas mobile.

### Pilar 4: Lógica Médica & Domínio
- [x] Integridade do FSRS / agendamento / temporizador
- [ ] Divergência identificada com os requisitos de estudo médico.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade (P1/P2/P3) | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `path/to/file.tsx:42` | Descrição sucinta | Perda de dados ou crash |
| #2 | P2 (Maior) | `path/to/file.py:105` | Descrição sucinta | Estado inconsistente |
| #3 | P3 (Otimização) | `path/to/file.tsx:18` | Descrição sucinta | Melhora de UX ou layout |

---

## 4. Correções Aplicadas

### Correção #1: [Título do Problema]
- **Arquivos Alterados**: `[Nome do Arquivo](file:///path/to/file)`
- **Motivação & Solução**: Explicação da causa raiz e como o código foi ajustado.
- **Teste de Regressão Adicionado/Executado**: Como a correção foi validada.

*(Repita para cada correção aplicada)*

---

## 5. Validação & Resultados dos Testes

\`\`\`bash
# Saída do comando ./validate.sh fast
...
\`\`\`

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
Lista de melhorias recomendadas que ultrapassam o escopo imediato da fatia vertical (ex: redesign de tela, novas features, refatorações maiores).
```
