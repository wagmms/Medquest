# Relatório de Auditoria — Aba: Revisão Ativa (Flashcards)
**Data**: 2026-09-27  
**Status da Linha de Base**: Passou  
**Resultado Pós-Correções**: Passou (`./validate.sh fast`)

---

## 1. Resumo Executivo

A full-stack vertical slice audit was conducted on the **Revisão Ativa / Flashcards** module (`/revisao-ativa`), encompassing:
- **Frontend Architecture**: `app/frontend/src/app/revisao-ativa/page.tsx`, `loading.tsx`, `FlashcardClient.tsx`, `components/AnkiIntegrationModal.tsx`, `lib/normalizeFlashcard.ts`, `lib/ankiConnect.ts`, `lib/flashcardCache.ts`.
- **Backend APIs & Parsers**: `app/backend/api/flashcards.py`, `app/backend/api/srs.py`, `app/backend/api/anki.py`.
- **Database & Persistence**: SQLite/Turso tables (`flashcards`, `spaced_repetition`, `questions`), local Dexie IndexedDB cache and sync queue (`localDb.flashcards`).

The baseline passed successfully. During the 4-pillar audit, 8 targeted issues were identified, ranging from critical data loss in Anki exports and deck filtering failures to keyboard shortcut bleed and modal accessibility deficits. All 8 issues have been resolved with regression tests added and validated.

---

## 2. Diagnóstico por Pilar

### Pilar 1: Correção & Edge Cases
- [x] SSR / Client hydration consistency on dynamic params (`searchParams.subtema`).
- [x] Resilient empty queue handling (0 cards due, deck-filtered empty states, upcoming review preview).
- [x] Offline mutation queueing with `OfflineQueuedError` and local Dexie persistence.
- [x] Corrigido: `export_anki` utilizava `INNER JOIN questions q ON f.question_id = q.id`, descartando silenciosamente todos os flashcards importados do Anki ou cartões avulsos sem questão associada (`question_id IS NULL`).
- [x] Corrigido: `get_due_flashcards` utilizava `AND f.deck_name = ?` cru, falhando ao filtrar pelo baralho padrão "Geral" para cartões salvos com `deck_name` nulo.
- [x] Corrigido: `normalizeFlashcard` executava substituição não-global restrita ao índice `c1`, deixando letras de alternativas intactas em omissões `c2`/`c3` e em múltiplos clozes.
- [x] Corrigido: `page.tsx` passava `subtema` sem estreitamento de tipo (`string | string[]`), gerando inconsistência de tipo com `FlashcardClient`.

### Pilar 2: Performance & Banco de Dados
- [x] Paginação e índices compostos de alto desempenho (`idx_flashcards_user_review`, `idx_flashcards_user_deck`, `idx_flashcards_user_anki_cid`).
- [x] Eliminação de N+1 queries na sincronização de estado do AnkiConnect com consultas em lotes de 500 cartões.
- [x] Corrigido: `AnkiIntegrationModal` (componente pesado de 717 linhas) e dependências do AnkiConnect agora utilizam code splitting via `next/dynamic` com `ssr: false`, reduzindo o payload JavaScript inicial da página.

### Pilar 3: UX, Acessibilidade & Mobile
- [x] Tokens semânticos de Tailwind v4 com adaptação harmônica em modo escuro/claro.
- [x] Corrigido: Conflito de navegação por teclado suspenso quando modais estão abertos (`isAnkiModalOpen`).
- [x] Corrigido: Violação ARIA no contêiner do cartão — o elemento pai possuía `role="button"` permanente contendo botões interativos (`Reportar`, `Ver questão de origem`). Agora o cartão adota `role="button"` apenas enquanto fechado (`!flipped`), transicionando para `role="region"` sem foco concorrente quando revelado.
- [x] Corrigido: `AnkiIntegrationModal` agora segue as especificações de acessibilidade WAI-ARIA com `role="dialog"`, `aria-modal="true"`, `aria-labelledby="anki-modal-title"`, fechamento por tecla Escape e clique no backdrop.
- [x] Corrigido: Alvos de toque inferiores a 44x44px no botão de reportar, abas do modal, botão de exclusão de baralhos e controles de navegação.
- [x] Corrigido: Contraste de cores do tema escuro em textos roxos e azuis (`dark:text-purple-400`, `dark:text-blue-400`).
- [x] Corrigido: Substituição de webfont `<span className="material-symbols-outlined">menu_book</span>` pelo ícone consistente `BookOpen` do `lucide-react`.

### Pilar 4: Lógica Médica & Domínio
- [x] FSRS v6 calibrado especificamente para flashcards atômicos (`api/srs.py`): sem passos de minutos intradia, repetição padrão D+1 no erro e retenção alvo 0.85.
- [x] Mapeamento exato de confiança médica: `errei` -> Again, `duvida` -> Good, `certeza` -> Easy.
- [x] Normalização de cartões legados para o formato clínico de alta retenção com cenário, cloze ativo, gabarito e análise de distrator.

---

## 3. Problemas Identificados & Classificação de Risco

| ID | Severidade | Arquivo & Linha | Descrição do Problema | Impacto no Usuário |
| :--- | :--- | :--- | :--- | :--- |
| #1 | P1 (Crítico) | `app/backend/api/flashcards.py:871, 879` | `export_anki` utilizava `JOIN questions q ON f.question_id = q.id`. | Flashcards importados do Anki ou cartões avulsos sem questão vinculada eram completamente omitidos da exportação TXT. |
| #2 | P1 (Crítico) | `app/backend/api/flashcards.py:749` | `get_due_flashcards` filtrava por `AND f.deck_name = ?` sem coalescer valores nulos como 'Geral'. | Ao selecionar o baralho "Geral" no seletor, a fila de revisão retornava vazia (0 cartões) para todos os cartões nativos do MedQuest. |
| #3 | P2 (Maior) | `app/frontend/src/app/revisao-ativa/FlashcardClient.tsx:162` | O listener de atalhos globais de teclado não verificava se o modal do Anki estava aberto. | Pressionar espaço, Enter ou teclas 1-3 dentro do modal interagia e revisava os cartões de estudo em segundo plano. |
| #4 | P2 (Maior) | `app/frontend/src/app/revisao-ativa/FlashcardClient.tsx:388` | O contêiner pai do cartão mantinha `role="button"` mesmo após revelado, aninhando links e botões interativos. | Violação das diretrizes ARIA/HTML, falhas em leitores de tela e bloqueio de navegação por teclado nos elementos internos. |
| #5 | P2 (Maior) | `app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx:278` | Modal sem `role="dialog"`, sem `aria-modal="true"`, sem listener da tecla Escape e sem fechamento por clique no backdrop. | Inacessibilidade para usuários de teclado e descumprimento do padrão modal de design system. |
| #6 | P3 (Otimização) | `app/frontend/src/app/revisao-ativa/FlashcardClient.tsx:8` | `AnkiIntegrationModal` (717 linhas, 31KB) e módulo `ankiConnect` eram importados estaticamente no carregamento inicial. | Desperdício de largura de banda e tempo de parse JS na carga inicial de `/revisao-ativa`. |
| #7 | P3 (UX/Mobile) | `app/frontend/src/app/revisao-ativa/FlashcardClient.tsx:228, 292, 468`<br>`app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx:697` | Alvos de toque inferiores a 44x44px; baixo contraste de texto azul/roxo em modo escuro; ícone via webfont externa não empacotada. | Dificuldade ergonômica em mobile e degradação de legibilidade em dark mode. |
| #8 | P3 (Edge Case) | `app/frontend/src/lib/normalizeFlashcard.ts:75` | Regex de remoção de letras de alternativas não era global e tratava exclusivamente `c1`. | Cartões com clozes múltiplos ou clozes `c2`/`c3` mantinham letras redundantes como `A)` ou `B.`. |

---

## 4. Correções Aplicadas

### Correção #1: Suporte a Cartões Avulsos no Export Anki & Exclusão de Cartões Reportados
- **Arquivos Alterados**:
  - [`app/backend/api/flashcards.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/flashcards.py)
  - [`app/backend/tests/test_exports.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/tests/test_exports.py)
- **Motivação & Solução**: Modificada a query de `export_anki` para `LEFT JOIN questions q ON f.question_id = q.id`, adicionando cláusula `(f.report_status IS NULL OR TRIM(f.report_status) = '')` para evitar exportar cartões com erros reportados, e incorporando tags personalizadas do cartão (`f.tags`) e tags de baralho (`f.deck_name`).
- **Teste de Regressão Executado**: `test_export_anki_includes_unlinked_cards_and_custom_tags` em `test_exports.py`.

### Correção #2: Filtro Robusto de Baralhos e Inserção Padrão em `_save_flashcards`
- **Arquivos Alterados**:
  - [`app/backend/api/flashcards.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/flashcards.py)
  - [`app/backend/tests/test_flashcards_api.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/tests/test_flashcards_api.py)
- **Motivação & Solução**: Em `get_due_flashcards`, o filtro de baralho foi unificado para `COALESCE(NULLIF(TRIM(f.deck_name), ''), 'Geral') = ?`, garantindo que filtrar por "Geral" capture tanto registros com `deck_name = 'Geral'` quanto legados com `NULL`. Adicionado também o alias de rota `@bp.route("/flashcards/due", methods=["GET"])` e valor explícito `'Geral'` no INSERT de `_save_flashcards`.
- **Teste de Regressão Executado**: `test_flashcards_deck_filter_geral_and_due_alias` em `test_flashcards_api.py`.

### Correção #3: Suspensão de Atalhos Globais com Modal Aberto
- **Arquivos Alterados**:
  - [`app/frontend/src/app/revisao-ativa/FlashcardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/FlashcardClient.tsx)
- **Motivação & Solução**: Incluída verificação `if (isAnkiModalOpen) return;` no início de `handleKeyDown` e adicionado `isAnkiModalOpen` à lista de dependências do `useEffect`.

### Correção #4: Conformidade ARIA e Remoção de Aninhamento Interativo
- **Arquivos Alterados**:
  - [`app/frontend/src/app/revisao-ativa/FlashcardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/FlashcardClient.tsx)
- **Motivação & Solução**: O container do flashcard agora utiliza `role={!flipped ? "button" : "region"}` e `tabIndex={!flipped ? 0 : -1}`, eliminando a violação semântica de conter botões e links interativos como filhos de um botão acessível.

### Correção #5: Padrão WAI-ARIA e Fechamento no Modal do Anki
- **Arquivos Alterados**:
  - [`app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx)
- **Motivação & Solução**: Modal decorado com `role="dialog"`, `aria-modal="true"`, `aria-labelledby="anki-modal-title"`. Adicionado listener de evento para a tecla `Escape` e clique no backdrop para encerramento do diálogo.

### Correção #6: Code Splitting Dinâmico do Modal Anki
- **Arquivos Alterados**:
  - [`app/frontend/src/app/revisao-ativa/FlashcardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/FlashcardClient.tsx)
- **Motivação & Solução**: Substituída a importação estática por `next/dynamic` (`dynamic(() => import(...), { ssr: false })`), isolando 31KB de código de integração e parsers do pacote principal.

### Correção #7: Alvos de Toque, Contraste Escuro e Ícones Lucide
- **Arquivos Alterados**:
  - [`app/frontend/src/app/revisao-ativa/FlashcardClient.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/FlashcardClient.tsx)
  - [`app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/components/AnkiIntegrationModal.tsx)
  - [`app/frontend/src/app/revisao-ativa/loading.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/loading.tsx)
- **Motivação & Solução**: Alvos de toque ajustados para `min-h-[44px] min-w-[44px]`; contrastes ajustados para `dark:text-purple-400` e `dark:text-blue-400`; ícone de livro substituído pelo componente nativo `BookOpen` de `lucide-react`.

### Correção #8: Normalização Global de Clozes e Estreitamento de Parâmetros
- **Arquivos Alterados**:
  - [`app/frontend/src/lib/normalizeFlashcard.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/lib/normalizeFlashcard.ts)
  - [`app/frontend/src/app/revisao-ativa/page.tsx`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/src/app/revisao-ativa/page.tsx)
  - [`app/frontend/e2e/normalizeFlashcard.spec.ts`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/e2e/normalizeFlashcard.spec.ts)
  - [`app/frontend/scripts/tests/audit-regressions.test.mjs`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/frontend/scripts/tests/audit-regressions.test.mjs)
- **Motivação & Solução**: Regex atualizada para `/{{c(\d+)::[A-Ea-e][\)\.\:\-]\s*(.*?)}}/g`, removendo letras de alternativas em todos os clozes. Adicionada proteção contra entradas nulas e estreitamento de tipo seguro em `page.tsx`.
- **Testes de Regressão Executados**: `normalizeFlashcard.spec.ts` (10 testes) e `audit-regressions.test.mjs` (24 testes).

---

## 5. Validação & Resultados dos Testes

```bash
$ ./validate.sh fast
================================================================
[FAST TIER] MEDQUEST DEV-VELOCITY: COMMIT LOCAL
================================================================

--> [Backend Diff Tests (9 suites)] Executando: pytest -q --disable-warnings
........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 7.07s
    [OK] Backend Diff Tests (9 suites) concluido com sucesso (8.11s)

--> [Frontend Incremental Lint (27 arquivos)] Executando: eslint --quiet
    [OK] Frontend Incremental Lint (27 arquivos) concluido com sucesso (9.83s)

----------------------------------------------------------------
[PASS] SUCESSO: TODAS AS VALIDACOES PASSARAM (Camada: FAST | Tempo Total: 18.01s)
----------------------------------------------------------------
```

Testes unitários dedicados do Flashcards e Anki:
```bash
# Backend Hermético
$ pytest tests/test_flashcards_api.py tests/test_anki.py tests/test_exports.py -q
28 passed in 1.60s

# Frontend Unit Tests
$ npm run test:unit
ℹ tests 24
ℹ pass 24
ℹ fail 0
```

---

## 6. Oportunidades Futuras & Backlog Não-Crítico

1. **Atalhos Adicionais no Teclado**: Suporte à tecla de espaço para confirmar a classificação do FSRS quando virado (ex: espaço confirmar "Fácil", tecla `R` para reportar).
2. **Estatísticas de Retenção por Baralho**: Exibição da curva de esquecimento e taxa de retenção ponderada por baralho individualizado na interface de gerenciamento.
3. **Áudio e TTS em Flashcards**: Integração opcional de pronúncia de termos médicos complexos ou áudio de ausculta em cartões de semiologia.
