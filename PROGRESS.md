# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Implementar telemetria de latência em `app/backend/api/db.py` no método `TursoConnection._execute_with_reconnect` registrando tempo de roundtrip de consultas remotas no logger `medquest.telemetry` com evento `db_query_latency` com testes unitários em `app/backend/tests/test_observability.py` assegurando tolerância a falhas sem afetar reconexão.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Implementar guardrail de sanitização em `app/frontend/src/components/ExplanationViewer.tsx` na renderização de texto assegurando fallback contra marcações residuais em comentários clínicos sem alterar o conteúdo canônico.
2. [ ] Implementar rotina de recuperação de quota e evicção em `app/frontend/src/lib/db.ts` no método `syncQuestions` expurgando pacotes expirados de `simuladoPackages` quando detectado `QuotaExceededError` com testes unitários no frontend.
3. [ ] Implementar clamp defensivo de intervalo mínimo em `app/backend/api/srs.py` na função `review` assegurando que qualquer agendamento gerado respeite D+1 (>= 24h) com cobertura de testes em `app/backend/tests/test_srs.py`.

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
- [x] **Validação de Existência Prévia em Favoritos (Backend)**: Implementada validação de existência de questão em `app/backend/api/questions.py` na rota `toggle_favorite` retornando HTTP 404 (`{"error": "Questão não encontrada"}`) e liberação de idempotência caso não encontrada, prevenindo inserção de chaves órfãs na tabela `favorites`, acompanhada de teste unitário `test_question_favorite_not_found` em `app/backend/tests/test_api.py` (100% de aprovação na suíte de testes).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)

