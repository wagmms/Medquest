# 📜 MedQuest - Changelog de Tarefas Concluídas

Histórico completo de ciclos, sprints e melhorias entregues no repositório.

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
