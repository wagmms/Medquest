# 📜 MedQuest - Changelog de Tarefas Concluídas

Histórico completo de ciclos, sprints e melhorias entregues no repositório.

---

## [2026-10-11] - Ciclo Autoloop: Validação de Existência Prévia em Favoritos
- **Integridade Referencial e Validação de Favoritos (Backend)**:
  - `app/backend/api/questions.py`: Implementada verificação de existência prévia de questão na rota `toggle_favorite` (`POST /api/questions/<int:qid>/favorite`), retornando HTTP 404 (`{"error": "Questão não encontrada"}`) e liberando token de idempotência caso a questão não exista no banco, prevenindo inserção de chaves órfãs na tabela `favorites`.
  - `app/backend/tests/test_api.py`: Adicionado teste unitário `test_question_favorite_not_found` validando resposta HTTP 404 para toggle padrão, favorito explícito (`is_favorite=True`), desfavoritar explícito (`is_favorite=False`) e assegurando ausência de registros órfãos persistidos na tabela `favorites` (100% de aprovação na suíte de testes).

---

## [2026-10-11] - Ciclo Autoloop: Resiliência de Cache e Rollback Transacional no Dexie
- **Resiliência e Atomicidade no Cache Offline (Frontend)**:
  - `app/frontend/src/lib/db.ts`: Implementado método `syncQuestions` na classe `MedQuestDB` e helper exportado `syncQuestions`, provendo sincronização transacional atômica (`rw`) no Dexie com rollback automático, isolamento por `_owner_id` e validação defensiva pré-transação contra registros malformados ou IDs inválidos.
  - `app/frontend/src/lib/simuladoPackage.ts`: Refatorado download de pacotes de simulado para persistir lotes de questões através de `localDb.syncQuestions(details, uid)`, substituindo chamada direta e frágil a `bulkPut` por operação transacional protegida contra dados parciais.
  - `app/frontend/scripts/tests/sync-questions-cache.test.mjs`: Criada suíte com 5 testes unitários validando atomicidade, rejeição estrita de dados corrompidos antes de transações, vinculação de `_owner_id`, garantia de rollback em falhas de I/O / cota e operação segura em ambiente SSR (100% de aprovação em `npm run test:unit`).

---

## [2026-10-11] - Ciclo Autoloop: Testes de Estresse e Invariantes do FSRS v6
- **Validação de Invariantes Temporais e Estresse no Motor FSRS (Backend)**:
  - `app/backend/tests/test_srs.py`: Implementada a classe de testes `TestFSRSValidation` cobrindo calibração de parâmetros (`desired_retention=0.85`, `learning_steps=()`, `relearning_steps=()`, `_QUESTION_PARAMS`), estresse sob 25 erros consecutivos em questões e flashcards, simulação temporal realista de 64 revisões mistas, recuperação de estabilidade pós-lapso e garantia de que nenhum agendamento gere passos intradia (< 24h) ou intervalos negativos.

---

## [2026-10-11] - Ciclo Autoloop: Otimização de Contagem de Questões e Cache TTL
- **Performance e Resiliência na Contagem de Questões (Backend)**:
  - `app/backend/api/questions.py`: Implementado suporte unificado a `/api/questions/count` e `/api/questions/counts` com cache em memória `count_cache` (TTL 60s, max 1000 entradas), separando escopo de catálogo global de filtros atrelados a usuário (`status`, `unanswered_only`, `favorite`), com tempo de resposta < 10ms.
  - `app/backend/api/questions.py`: Invalidação de `count_cache` por usuário integrada à rotina `invalidate_user_caches(user_id)` após respostas e revisões.
  - `app/backend/tests/test_api.py`: Expandido teste `test_questions_count_with_filters` validando alias `/counts`, combinação de `area` e `subtema` via índice composto `idx_questions_area_subtema`, resposta imediata do cache em memória e invalidação atrelada ao usuário.

---

## [2026-10-11] - Ciclo Autoloop: Tipagem Estrita e Acessibilidade em Componentes de Questão
- **Acessibilidade e Semântica ARIA no Frontend**:
  - `app/frontend/src/app/estudar/components/AlternativeList.tsx`: Adicionado container com `role="region"` e `aria-label="Alternativas da questão"`, `aria-label` descritivo e sintetizado em cada alternativa com estado dinâmico (selecionada/riscada/gabarito), além de `aria-hidden="true"` nos ícones e marcadores visuais.
  - `app/frontend/src/components/ExplanationViewer.tsx`: Adicionado `aria-hidden="true"` em todos os ícones decorativos de cabeçalho (`Award`, `Sparkles`, `Stethoscope`, `CheckCircle2`, `XCircle`, `AlertCircle`) e atributos acessíveis no modal de zoom de imagens médicas.
  - `app/frontend/src/components/QuestionClassificationModal.tsx`: Vinculado `aria-labelledby="classification-modal-title"`, `aria-pressed` nos seletores de Grande Área e subtema, e `aria-hidden="true"` em todos os ícones funcionais e de feedback.
  - `app/frontend/src/components/PreceptorFocusCard.tsx`, `QuizTimer.tsx`, `SubjectTreeSelector.tsx`, `OfflinePanel.tsx`, `ImageViewer.tsx`, `FormattedContent.tsx`: Reforçados papéis acessíveis de timer, diálogos modais e zoom.
- **Blindagem de Deploy e Imutabilidade de Explicações**:
  - `deploy.py` e `tests/test_deploy.py`: Implantação de lock físico de exclusão mútua (`fcntl.flock`), verificação obrigatória de branch `main`, integridade de SHA e validação de pareceres de auditoria.
  - `app/backend/api/ai_routes.py`: Proteção estrita de explicações canônicas de professores (`canonical_professor_locked`), impedindo regeneração e desperdício de tokens de IA.
  - `app/backend/scripts/sync_db_turso.py`: Validação defensiva do payload retornado pelo Turso Pipeline HTTP.

---

## [2026-10-10] - Ciclo Autoloop: Auditoria e Cobertura de Testes Unitários de API
- **Cobertura de Testes de API (Backend)**:
  - `app/backend/tests/test_api.py`: Expandida suíte com 10 novos testes cobrindo filtros de área/ano/subtema, status wrong/answered, toggle de favoritos, contagens, overview zero-state, distratores e modos adaptativos.
  - Correção do edge-case `NOT IN (NULL)` na query SQL de remediação.

---

## [2026-10-10] - Setup Inicial do Autoloop
- **Setup Seguro Inicial**:
  - Configuração da branch segura `autoloop/dev` e criação de `PROGRESS.md`.
  - Correção de data fixa em `test_planner.py`.
