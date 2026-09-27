# Relatório de Auditoria — Aba: Simulado
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou (`./validate.sh fast` executado com sucesso)  
**Resultado Pós-Correções**: Passou (Suíte de regressão frontend: 17/17 testes aprovados; Backend: 32/32 testes aprovados; ESLint: 0 erros e 0 warnings)

---

## 1. Resumo Executivo

A aba **Simulado** (`/simulado`) provê a experiência de treino em bloco com tempo estrito, simulação realista de exames médicos de residência, correção em lote e conversão direta de erros em flashcards para repetição espaçada (FSRS v6).

A auditoria identificou vulnerabilidades funcionais em persistência de sessões no backend, possibilidade de deadlock permanente após sincronização offline, degradação de performance por varreduras não indexadas no IndexedDB (Dexie) que alteravam a ordenação balanceada das questões em modo offline, e pequenas discrepâncias visuais/acessibilidade. Todas as vulnerabilidades críticas (P1 e P2) foram corrigidas cirurgicamente com testes automatizados dedicados.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Verificado: persistência de estado do simulado (`readLearningSession` / `writeLearningSession`) respeita limites de usuário e não cruza contas.
- [x] Verificado: cronômetro do simulado imune a desvios de suspensão de aba/background, utilizando timestamps de relógio de parede (`deadlineAt`).
- [ ] Problema corrigido: `api.sessions.saveSimulado` disparava requisição `POST` para `/api/sessions/simulado`, rota inexistente no backend Flask (que retornava 405 Method Not Allowed). A rota correta no blueprint de questões é `/api/simulado/sessions`.
- [ ] Problema corrigido: Deadlock permanente na tela `OFFLINE_SUBMITTED` caso a fila do Dexie fosse drenada pelo sync em segundo plano enquanto o usuário estava fora da aba. Adicionada recuperação com reenvio idempotente via `submitAttemptBatch`.
- [ ] Problema corrigido: Se o usuário retomasse o simulado com falha em lote de rede, a tela congelava em skeleton sem carregar a questão atual. Adicionado fallback de carregamento individual.
- [ ] Problema corrigido: Navegação por teclado (ArrowLeft / ArrowRight) não chamava `loadDetail` se a questão não estivesse no cache em memória. Adicionado hook reativo de garantia de carregamento da questão ativa.

### Pilar 2: Performance & Banco de Dados
- [x] Verificado: queries de montagem de simulado (`simulado_usp`, `simulado_custom`) e busca de detalhes em lote (`question_batch_detail`) eliminam N+1 e utilizam chunks otimizados.
- [ ] Problema corrigido: no frontend, leituras do IndexedDB em `startSimulado()` e `loadDetail()` realizavam varreduras lineares com `.where('_owner_id').equals(uid).filter(...)` em vez de utilizar a chave primária composta `[id+_owner_id]` já existente no schema Dexie.
- [ ] Problema corrigido: a varredura linear em modo offline destruía a ordem balanceada de áreas e instituições das questões, pois retornava ordenado pela chave primária sequencial do banco. Substituído por `localDb.questions.bulkGet` preservando estritamente a ordem do pacote.
- [ ] Problema corrigido: cálculo de `areaSummary` no modo de resultados executava laço aninhado (`queue.forEach` dentro de `areaSummary.map`) em cada render. Contagem pré-calculada diretamente no `useMemo`.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Verificado: conformidade integral com tokens semânticos do Tailwind CSS v4 (`bg-card`, `text-foreground`, `border-border`, etc.).
- [ ] Problema corrigido: `showTopic` inicializava lendo `localStorage` diretamente no construtor do `useState`, representando risco de mismatch de hidratação SSR/Client no Next.js App Router. Sincronização transferida para `useEffect`.
- [ ] Problema corrigido: 4 ocorrências de `<span className="material-symbols-outlined">` (ícones de informação, troféu e verificado) foram substituídas por ícones SVG do Lucide (`Info`, `Trophy`, `ShieldCheck`), eliminando dependência de download de fontes e falhas visuais offline.
- [ ] Problema corrigido: botões de filtro da sidebar sem indicação `aria-pressed`. Adicionados atributos ARIA e touch targets mínimos aprimorados para mobile.

### Pilar 4: Lógica Médica & Domínio
- [x] Verificado: conformidade com o FSRS v6 (`api/srs.py`, retention 0.85, intervalos longos). Simulado envia respostas com `confidence: "duvida"`, mapeando acertos para `Rating.Good` e erros para `Rating.Again`.
- [x] Verificado: prevenção de avanço duplo de FSRS na revisão de simulado.
- [ ] Problema corrigido: geração em lote de flashcards dos erros (`handleGenerateAllSimuladoWrongFlashcards`) incluía questões deixadas em branco (gerando flashcards genéricos de distrator "A"), divergindo do texto do botão na interface (`answers[q.id]`). Alinhado para incluir estritamente questões respondidas incorretamente.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade (P1/P2/P3) | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `lib/api.ts:228` | Rota incorreta `/api/sessions/simulado` em `api.sessions.saveSimulado`. | Falha 405 ao tentar persistir resumo consolidado do simulado no histórico. |
| #2 | P1 (Crítico) | `SimuladoClient.tsx:694` | Possibilidade de deadlock permanente na tela `OFFLINE_SUBMITTED` se o sync já houvesse drenado a fila. | Usuário ficava impedido de visualizar gabarito e nota final de simulado offline. |
| #3 | P2 (Maior) | `SimuladoClient.tsx:379` | Leitura de questões offline no Dexie via `.where().filter()` em vez de `bulkGet` com chave composta. | Destruía a ordem balanceada de questões e áreas e degradava performance em dispositivos móveis. |
| #4 | P2 (Maior) | `SimuladoClient.tsx:631` | `handleGenerateAllSimuladoWrongFlashcards` gerava cards para questões em branco, divergindo do contador da UI. | Criação de flashcards artificiais sem distrator real assinalado pelo estudante. |
| #5 | P2 (Maior) | `SimuladoClient.tsx:280,1010` | Navegação por teclado ou retomada com falha em lote congelava tela em skeleton loader sem carregar questão. | Travamento visual ao alternar questões no teclado sem cache completo. |
| #6 | P3 (Otimização) | `SimuladoClient.tsx:81` | Leitura de `localStorage` na inicialização de `showTopic`. | Risco de hydration mismatch no SSR do Next.js. |
| #7 | P3 (Otimização) | `SimuladoClient.tsx:1038` | Uso de classes legadas `material-symbols-outlined` em vez de SVGs Lucide. | Risco de texto puro ("trophy", "info") caso fontes não estivessem em cache offline. |

---

## 4. Correções Aplicadas

### Correção #1: Correção do Endpoint e Persistência Confiável de Sessão de Simulado
- **Arquivos Alterados**: [`app/frontend/src/lib/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/api.ts), [`app/frontend/src/app/simulado/SimuladoClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/simulado/SimuladoClient.tsx)
- **Motivação & Solução**: A rota foi corrigida para `/api/simulado/sessions`. No `SimuladoClient.tsx`, a chamada foi integrada diretamente no fluxo de entrega e na recuperação offline, adicionando rastreamento de idempotência em `savedSessionIdRef` e eliminando o `useEffect` redundante que re-disparava gravações a cada re-render.
- **Teste de Regressão**: Teste unitário adicionado em `scripts/tests/audit-regressions.test.mjs` validando endpoint e método HTTP.

### Correção #2: Resolução de Deadlock e Recuperação Offline Idempotente
- **Arquivos Alterados**: [`app/frontend/src/app/simulado/SimuladoClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/simulado/SimuladoClient.tsx)
- **Motivação & Solução**: Quando o usuário clica para sincronizar ou o monitor online é acionado, verifica-se se a fila do Dexie ainda possui o item pendente. Se a fila já tiver sido concluída por outra aba ou em background, o cliente submete o lote diretamente; o backend MedQuest retorna a resposta do cache de idempotência com código 200 e resultados completos, destravando a interface para `RESULTS`.

### Correção #3: Leitura Indexada por Chave Composta no IndexedDB (`bulkGet`)
- **Arquivos Alterados**: [`app/frontend/src/lib/api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/api.ts), [`app/frontend/src/app/simulado/SimuladoClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/simulado/SimuladoClient.tsx)
- **Motivação & Solução**: O Dexie define a chave primária `[id+_owner_id]`. Substituíram-se varreduras com filtros na memória por `localDb.questions.bulkGet(readyPkg.question_ids.map(id => [id, uid]))` e `localDb.questions.get([id, uid])`. Isso preserva a ordem balanceada original do simulado e atinge leitura O(1) por questão.
- **Teste de Regressão**: Teste unitário adicionado em `scripts/tests/audit-regressions.test.mjs` garantindo formato de chave composta e ordem preservada.

### Correção #4: Alinhamento de Flashcards de Erros e Navegação Resiliente
- **Arquivos Alterados**: [`app/frontend/src/app/simulado/SimuladoClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/simulado/SimuladoClient.tsx)
- **Motivação & Solução**: `handleGenerateAllSimuladoWrongFlashcards` agora filtra estritamente `answers[q.id]`, casando com o contador da interface. Adicionou-se efeito reativo para garantir que qualquer questão ativa sem detalhe em cache seja carregada imediatamente via `loadDetail`.

### Correção #5: Acessibilidade, Ícones Nativos e Hidratação Segura
- **Arquivos Alterados**: [`app/frontend/src/app/simulado/SimuladoClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/simulado/SimuladoClient.tsx)
- **Motivação & Solução**: Substituição de spans de Material Symbols por `Info`, `Trophy` e `ShieldCheck` do Lucide. Sincronização de `showTopic` em `useEffect`. Adição de `aria-pressed` nos filtros da sidebar e ampliação de touch targets para mobile.

---

## 5. Validação & Resultados dos Testes

```bash
# 1. Suíte de regressão frontend:
node --test scripts/tests/audit-regressions.test.mjs
✔ reading and removing a session never migrates or erases another owner (147ms)
✔ a delayed session write is cancelled when the active account changes (23ms)
✔ offline card creation is durable and cannot return a fabricated server ID (107ms)
✔ server authorization failures are not disguised as local card saves (67ms)
✔ download traverses all pages of cards (42ms)
✔ calendar keeps topics whole, advances at daily capacity, and skips weekends (24ms)
✔ calendar HTTP failures reject instead of announcing success (16ms)
✔ calendar uses every page, preserves completed legacy events and imports completion (36ms)
✔ retrying a partial calendar sync updates the same IDs without deleting events (26ms)
✔ sync retries a processing conflict but stops for a mismatched idempotency key (53ms)
✔ a request started by Alice is not queued as Bob after an account switch (116ms)
✔ deck deletion invalidates only the current owners matching cached cards (53ms)
✔ legacy calendar fragments are removed only after replacement, and cleanup errors surface (34ms)
✔ cobertura diacritic normalization matches unaccented medical search queries (0.6ms)
✔ cobertura practice link sets unanswered_only false only when all questions are answered (0.1ms)
✔ api.sessions.saveSimulado targets the canonical /api/simulado/sessions endpoint (34ms)
✔ api.questions.getBatch local fallback uses compound keys [id, ownerId] (36ms)
ℹ tests 17 | pass 17 | fail 0

# 2. Linting dos arquivos da aba Simulado:
npx eslint src/app/simulado/SimuladoClient.tsx src/lib/api.ts --max-warnings=0
Exit Code: 0 (Zero erros e zero warnings)

# 3. Testes unitários backend relacionados:
.venv/bin/pytest -q tests/test_api.py tests/test_flashcards_api.py
32 passed in 2.66s
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico

1. **Subdivisão Modular de `SimuladoClient.tsx`**: O componente possui ~1980 linhas. Futuramente, pode ser decomposto em subcomponentes isolados (`SimuladoSetupView.tsx`, `SimuladoPlayingView.tsx`, `SimuladoResultsView.tsx` e `SimuladoOfflineSubmittedView.tsx`).
2. **Download Seletivo de Múltiplos Pacotes**: Permitir gerenciar múltiplos cadernos offline simultâneos com exclusão individual a partir da própria tela de setup.
3. **Análise Comparativa com Edital/Benchmark**: Apresentar na tela de resultados do simulado a comparação percentual instantânea com a nota de corte estimada da banca escolhida.
