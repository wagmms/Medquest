# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Implementar rotina de recuperação de quota e evicção em `app/frontend/src/lib/db.ts` no método `syncQuestions` expurgando pacotes expirados de `simuladoPackages` quando detectado `QuotaExceededError` com testes unitários em `app/frontend/scripts/tests/sync-questions-cache.test.mjs`.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Implementar recuperação defensiva e fallback para payload legado em `app/backend/api/questions.py` na rota `attempt` regenerando estado inicial caso o JSON de `user_question_fsrs` esteja corrompido com cobertura em `app/backend/tests/test_api.py`.
2. [ ] Implementar trap-focus e atalhos de navegação por teclado em `app/frontend/src/components/QuestionClassificationModal.tsx` no componente modal assegurando conformidade WCAG 2.1 AA sem dependências externas.
3. [ ] Implementar padronização de respostas de erro e contrato JSON em `app/backend/api/questions.py` nas rotas `attempt` e `review` retornando payload estruturado `{"error": "...", "code": "..."}` com cobertura em `app/backend/tests/test_api.py`.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)
- Padronização de respostas 404 e contrato JSON em `api/questions.py`.
- Prefetch inteligente de próximas questões no modo offline do PWA via Dexie.
- Suporte completo a navegação por teclado nos modais de curadoria médica.
- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.
- Auditoria de contraste WCAG AAA nos badges de subtemas clínicos.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída
- [x] **Guardrail de Sanitização em ExplanationViewer (Frontend)**: Implementada a função `cleanSectionDelimiters` e parsing defensivo em `app/frontend/src/components/ExplanationViewer.tsx` na função `parseExplanation`, assegurando fallback gracioso para entradas corrompidas/não-string e eliminando delimitadores residuais órfãos (asteriscos de cabeçalhos colon-inside `**Cabeçalho:**`, dois-pontos soltos e itens fantasmas) em todas as seções clínicas (`puloDoGato`, `raciocinioClinico`, `padraoResposta`, `alternativaCorreta` e `distratores`) sem mutar o conteúdo canônico de professores, acompanhado de suíte com 5 testes unitários em `app/frontend/scripts/tests/explanation-viewer-sanitization.test.mjs` (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)

