# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Otimizar contagem de questões em `app/backend/api/question_routes.py` no endpoint `/api/questions/counts` garantindo índices compostos `idx_questions_area_subtema` e query com tempo de resposta < 10ms mantendo total compatibilidade com `TursoConnection`.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Adicionar testes de estresse em `app/backend/tests/test_fsrs.py` na classe `TestFSRSValidation` garantindo que intervalos de repetição nunca retornem valores negativos ou passos intradia indesejados.
2. [ ] Reforçar resiliência de cache em `app/frontend/src/lib/db.ts` no método `syncQuestions` assegurando tratamento defensivo de falha de conexão e rollback transacional no Dexie.
3. [ ] Criar validação de existência prévia em `app/backend/api/question_routes.py` na função `toggle_favorite` prevenindo inserção de `question_id` inexistente no banco.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)
- Telemetria de latência para consultas remotas LibSQL/Turso Cloud em `api/db.py`.
- Prefetch inteligente de próximas questões no modo offline do PWA via Dexie.
- Suporte completo a navegação por teclado nos modais de curadoria médica.
- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.
- Auditoria de contraste WCAG AAA para badges de temas médicos nos modos claro e escuro.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída
- [x] **Tipagem Estrita e Acessibilidade em Componentes de Questão (Frontend)**: Revisados e blindados componentes de questão (`AlternativeList.tsx`, `ExplanationViewer.tsx`, `QuestionClassificationModal.tsx`, `PreceptorFocusCard.tsx`, `QuizTimer.tsx`, `FormattedContent.tsx`, `ImageViewer.tsx`), eliminando riscos de tipagem, adicionando papéis semânticos ARIA, estados `aria-pressed`, `aria-hidden` em ícones decorativos e rótulos acessíveis com zero avisos no linter (`npm run lint`) e 100% de aprovação em `./validate.sh fast`.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
