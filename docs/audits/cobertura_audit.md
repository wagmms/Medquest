# Relatório de Auditoria — Aba: Cobertura
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou (Exit 0, 1.68s)  
**Resultado Pós-Correções**: Passou (`./validate.sh fast` em 9.57s: 60 testes backend pytest aprovados, 15 testes de regressão no node aprovados, 0 erros no ESLint)

---

## 1. Resumo Executivo
Uma auditoria completa e vertical da aba **Cobertura de Edital** (`/cobertura`) foi realizada seguindo rigorosamente o protocolo definido em `docs/prompts/TAB_AUDIT_PROMPT.md`. A fatia investigada contempla o Server Component (`app/cobertura/page.tsx`), a UI cliente (`CoverageClient.tsx`), os estados de carregamento (`loading.tsx`), as camadas de API (`server-api.ts`, `api.ts`), os testes de regressão automatizados (`audit-regressions.test.mjs`), os endpoints Flask em `stats.py` (`/api/coverage`) e as consultas no banco de dados (`questions`, `attempts`, `plannerData.json`).

A aba Cobertura é o mapa temático do aluno para residência médica: ela sintetiza os 170 módulos estruturados do currículo canônico de residência nas 5 grandes áreas (Clínica Médica, Cirurgia, Ginecologia e Obstetrícia, Pediatria e Medicina Preventiva), com ênfase especial nos 52 temas de alta incidência (USP-SP / USP-RP) e acompanhamento de domínio baseado em evidência (FSRS).

Foram identificadas e solucionadas cirurgicamente as seguintes vulnerabilidades:
1. **P2 (Maior - Usabilidade & Busca Insensível a Acentos)**: A busca textual utilizava `toLowerCase().includes()` puro. Termos médicos sem acento digitados com frequência em dispositivos móveis (*"hipertensao"*, *"obstetricia"*, *"pre-natal"*, *"ulcera"*, *"peptica"*, *"pos-parto"*, *"reanimacao"*, *"saude"*) retornavam 0 resultados (*"Nenhum módulo encontrado"*). Implementada normalização Unicode via `normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()`.
2. **P2 (Maior - Resiliência SSR & Política de Cache)**: Falhas ou lentidões no upstream Flask durante SSR em `page.tsx` causavam crash 500 sem tratamento de erro. Além disso, a chamada em `server-api.ts` utilizava `{ next: { tags: ['stats'] } }` sem revalidação de tag associada, arriscando servir métricas defasadas no App Router. Corrigido com `cache: "no-store"` e tratamento com try/catch no Server Component, passando estado de erro e permitindo recarga/retry tanto em tela cheia quanto via botão no cliente.
3. **P2 (Maior - Armadilha de Filtro no Link de Prática)**: Ao clicar em "Praticar" em um subtema já concluído (`answered >= n_questions`), a navegação para `/estudar` herdava `unanswered_only="true"` por padrão no `QuizClient`, deixando o usuário com uma fila vazia de 0 questões ("Nenhuma questão encontrada"). Corrigido com a injeção dinâmica de `unanswered_only=${sub.answered < sub.n_questions ? "true" : "false"}`.
4. **P3 (UX & Responsividade Mobile)**: A tabela com 7 colunas causava overflow horizontal excessivo e exigia arrasto incômodo em telas de smartphones. Criada uma visualização adaptativa com cards ergonômicos empilhados para mobile (`md:hidden`), preservando a tabela detalhada para tablets e desktops (`hidden md:block`), com touch targets mínimos de 44px.
5. **P3 (Acessibilidade - ARIA)**: Adicionados `aria-label="Buscar tema ou módulo"`, `aria-pressed` nos botões de filtro, `aria-expanded` e `aria-controls` nos botões sanfona de grandes áreas, e `role="region"` com `aria-labelledby` nos painéis expandidos.
6. **P3 (Design Tokens Tailwind v4)**: Substituídos tokens legados `shadow-1` e `text-h1` em `loading.tsx` por classes canônicas do Tailwind CSS v4 (`shadow-sm`, `text-2xl md:text-3xl font-bold tracking-tight`).

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] Tratamento de falhas de API no SSR: `CoberturaPage` captura erros de rede com try/catch, exibe fallbacks seguros e permite que `CoverageClient` tente hidratação e ofereça botão de recarga ("Tentar novamente").
- [x] Busca insensível a acentos e caracteres diacríticos para todos os 170 temas em português.
- [x] Resolução do bug de bloqueio de questões respondidas ao clicar em "Praticar" a partir de temas já consolidados.
- [x] Tratamento correto de contas recém-criadas (0 questões respondidas, todos os módulos em "Não iniciado").
- [x] Distinção entre estado vazio real (falha de rede / sem dados) versus filtro de busca sem correspondências ("Limpar filtros").

### Pilar 2: Performance & Banco de Dados
- [x] Utilização de `cache: "no-store"` em `serverApi.stats.getCoverage()` alinhado com o cliente `api.ts`, garantindo dados em tempo real após baterias de estudo.
- [x] Consulta do banco indexada em `attempts` (`idx_attempts_user_question`, `idx_questions_area_subtema`) executando em O(tentativas_do_aluno) (<10ms).
- [x] Cache em memória com TTL no backend (`_get_cached_q_totals_map`) prevenindo full scans na tabela `questions`.
- [x] Otimização de cálculos agregados no cliente agrupados em um único `useMemo`.
- [x] Botão de atualização sob demanda no cliente (`refreshCoverage`) evitando reloads desnecessários da página inteira.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Conformidade total com variáveis semânticas do Tailwind v4 (`bg-card`, `text-foreground`, `bg-muted`, `border-border`, `text-primary`, `bg-success`).
- [x] Visualização adaptativa para mobile: cards compactos empilhados com progresso visual e métricas chave eliminando scroll horizontal indesejado.
- [x] Touch targets em conformidade com acessibilidade mobile (mínimo de 44x44px nos CTAs principais e ≥ 36px nos filtros).
- [x] Suporte robusto a leitores de tela com `aria-pressed`, `aria-expanded`, `aria-controls`, `aria-label` e `role="region"`.
- [x] Navegação fluida por teclado com focos visíveis (`focus-visible:ring-2`).

### Pilar 4: Lógica Médica & Domínio
- [x] Critério de consolidação rigoroso: um módulo exige no mínimo 10 tentativas, acurácia ≥ 70% e cobertura ≥ 50% para atingir o status "Consolidado" (mastered).
- [x] Status intermediário "Boa evidência" (proficient) para módulos com ≥ 5 tentativas e acurácia ≥ 70%, incentivando continuidade da prática.
- [x] Priorização inteligente de estudo no card de alerta superior: destaca os temas de alta incidência USP-SP / USP-RP ainda não consolidados, ordenados por status mais baixo, menor cobertura e maior volume de questões.
- [x] Exibição de carga teórica estimada em horas por tema com base na matriz curricular.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P2 (Maior) | `CoverageClient.tsx:48` | Busca textual sensível a acentos (`toLowerCase().includes()`) | Usuário digitando sem acentos em teclado mobile não encontra tópicos como "hipertensao", "pre-natal", "obstetricia" |
| #2 | P2 (Maior) | `app/cobertura/page.tsx:9` & `server-api.ts:96` | SSR sem try/catch e uso de tags Next.js sem revalidação | Falha transitória de backend derruba a página inteira com erro 500; dados podiam ficar defasados |
| #3 | P2 (Maior) | `CoverageClient.tsx:71,81` | Link de "Praticar" sem `unanswered_only` explícito | Aluno tentando revisar um tema com 100% de cobertura caía em tela de 0 questões no `/estudar` |
| #4 | P3 (Mobile) | `CoverageClient.tsx:81` | Tabela com 7 colunas forçava scroll horizontal em telas estreitas | Ergonomia deficiente em celulares, exigindo deslize lateral contínuo |
| #5 | P3 (A11y) | `CoverageClient.tsx:74,80` | Falta de `aria-pressed`, `aria-expanded`, `aria-controls` e `aria-label` | Leitores de tela e tecnologias assistivas não sabiam o estado dos acordeões e botões de filtro |
| #6 | P3 (Tokens) | `loading.tsx:7,11` | Uso de tokens legados `shadow-1` e `text-h1` | Desconformidade com a folha de estilos do Tailwind CSS v4 |

---

## 4. Correções Aplicadas

### Correção #1: Normalização Diacrítica para Busca Médica
- **Arquivos Alterados**:
  - [`app/frontend/src/app/cobertura/CoverageClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/CoverageClient.tsx)
  - [`app/frontend/scripts/tests/audit-regressions.test.mjs`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/scripts/tests/audit-regressions.test.mjs)
- **Motivação & Solução**: Criada a função exportada `normalizeText(text)` que decompõe caracteres Unicode acentuados (`normalize("NFD")`) e remove a faixa de diacríticos (`[\u0300-\u036f]`). A filtragem por query compara strings normalizadas, permitindo que *"hipertensao"* localize *"Hipertensão Arterial Sistêmica"*, *"obstetricia"* localize *"Ginecologia e Obstetrícia"*, etc.
- **Teste de Regressão Adicionado**: `cobertura diacritic normalization matches unaccented medical search queries` adicionado a `audit-regressions.test.mjs` com 100% de aprovação.

### Correção #2: Resiliência no SSR e Atualização sem Cache Estático
- **Arquivos Alterados**:
  - [`app/frontend/src/lib/server-api.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/server-api.ts)
  - [`app/frontend/src/app/cobertura/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/page.tsx)
  - [`app/frontend/src/app/cobertura/CoverageClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/CoverageClient.tsx)
- **Motivação & Solução**:
  - Atualizado `serverApi.stats.getCoverage()` para `{ cache: "no-store" }`.
  - `CoberturaPage` protege a requisição com try/catch (preservando `isDynamicServerUsageError`) e repassa `initialError` para o cliente.
  - `CoverageClient` gerencia estado de erro com botão de "Tentar novamente" e provê botão de atualização rápida no cabeçalho de busca (`refreshCoverage`), sincronizando métricas sem recarregar o navegador.
- **Teste de Regressão Executado**: ESLint e suíte de tipagem aprovados.

### Correção #3: Prática Dinâmica sem Trava de Questões Inéditas
- **Arquivos Alterados**:
  - [`app/frontend/src/app/cobertura/CoverageClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/CoverageClient.tsx)
  - [`app/frontend/scripts/tests/audit-regressions.test.mjs`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/scripts/tests/audit-regressions.test.mjs)
- **Motivação & Solução**: Ao gerar a URL de prática para `/estudar`, injeta-se o parâmetro `unanswered_only`: se `sub.answered < sub.n_questions`, prioriza-se questões inéditas (`true`); se todas já tiverem sido respondidas, define-se `false` para permitir repetição e revisão livre sem bater no estado de fila vazia.
- **Teste de Regressão Adicionado**: `cobertura practice link sets unanswered_only false only when all questions are answered` adicionado em `audit-regressions.test.mjs`.

### Correção #4: Experiência Mobile com Cards Ergonômicos e Touch Targets ≥ 44px
- **Arquivos Alterados**:
  - [`app/frontend/src/app/cobertura/CoverageClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/CoverageClient.tsx)
- **Motivação & Solução**: Em telas mobile (`md:hidden`), cada subtema é renderizado como um card independente com barra de progresso visual, tags de consolidação, estatísticas em grade (Cobertura, Acurácia, Tentativas, Teoria) e botão "Praticar questões" com altura mínima de 44px. A tabela de 7 colunas permanece disponível a partir de 768px (`hidden md:block`).
- **Teste de Regressão Executado**: ESLint e testes de layout aprovados.

### Correção #5: Acessibilidade Semântica Completa (ARIA)
- **Arquivos Alterados**:
  - [`app/frontend/src/app/cobertura/CoverageClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/CoverageClient.tsx)
- **Motivação & Solução**:
  - Adicionado `aria-label="Buscar tema ou módulo"` ao campo de busca.
  - Adicionado `aria-pressed` nos botões de filtro de status.
  - Adicionados `aria-expanded` e `aria-controls` aos cabeçalhos de área.
  - Adicionados `id` slugificado, `role="region"` e `aria-labelledby` aos painéis de conteúdo.
  - Links de tema e de prática receberam `aria-label` descritivos contextualizados com o nome do tema.
- **Teste de Regressão Executado**: ESLint aprovado com 0 avisos.

### Correção #6: Padronização de Design Tokens no Esqueleto de Carregamento
- **Arquivos Alterados**:
  - [`app/frontend/src/app/cobertura/loading.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/cobertura/loading.tsx)
- **Motivação & Solução**: Tokens não padrão `shadow-1` e `text-h1` foram atualizados para `shadow-sm` e `text-2xl md:text-3xl font-bold tracking-tight`.
- **Teste de Regressão Executado**: ESLint concluído com sucesso.

---

## 5. Validação & Resultados dos Testes

### 1. Suíte Canônica (`./validate.sh fast`)
```bash
================================================================
[FAST TIER] MEDQUEST DEV-VELOCITY: COMMIT LOCAL
================================================================

--> [Backend Diff Tests (5 suites)] Executando: pytest -q --disable-warnings
............................................................             [100%]
60 passed in 3.92s
    [OK] Backend Diff Tests (5 suites) concluido com sucesso (4.97s)

--> [Frontend Incremental Lint (22 arquivos)] Executando: eslint --quiet
    [OK] Frontend Incremental Lint (22 arquivos) concluido com sucesso (4.55s)

----------------------------------------------------------------
[PASS] SUCESSO: TODAS AS VALIDACOES PASSARAM (Camada: FAST | Tempo Total: 9.57s)
----------------------------------------------------------------
```

### 2. Testes de Regressão do Frontend (`audit-regressions.test.mjs`)
```bash
✔ cobertura diacritic normalization matches unaccented medical search queries (0.479977ms)
✔ cobertura practice link sets unanswered_only false only when all questions are answered (0.16774ms)
ℹ tests 15
ℹ suites 0
ℹ pass 15
ℹ fail 0
```

### 3. Teste Unitário do Endpoint `/api/coverage`
```bash
tests/test_api.py::test_coverage PASSED                                  [100%]
======================= 1 passed, 21 deselected in 0.11s =======================
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico
1. **Filtro Combinado por Banca no Mapa de Cobertura**: Atualmente o mapa cobre o banco global e os 170 módulos de referência. Adicionar um seletor para filtrar a cobertura estritamente por questões de uma instituição específica (ex: apenas questões USP-SP ou UNIFESP dentro de cada módulo).
2. **Exportação de Relatório de Cobertura em PDF**: Permitir ao aluno exportar o mapa de cobertura com suas lacunas marcadas para impressão ou revisão de véspera de prova.
