# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Criar validação de existência prévia em `app/backend/api/questions.py` na função `toggle_favorite` prevenindo inserção de `question_id` inexistente na tabela `favorites` retornando HTTP 404 (`{"error": "Questão não encontrada"}`) com cobertura de testes unitários em `app/backend/tests/test_api.py`.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Implementar telemetria de latência em `app/backend/api/db.py` no método `_execute_with_reconnect` medindo tempos de roundtrip em consultas remotas LibSQL.
2. [ ] Implementar guardrail de sanitização em `app/frontend/src/components/ExplanationViewer.tsx` na renderização de texto assegurando fallback contra marcações residuais em comentários clínicos sem alterar o conteúdo canônico.
3. [ ] Implementar rotina de recuperação de quota e evicção em `app/frontend/src/lib/db.ts` no método `syncQuestions` expurgando pacotes expirados de `simuladoPackages` quando detectado `QuotaExceededError`.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)
- Telemetria de latência para consultas remotas LibSQL/Turso Cloud em `api/db.py`.
- Prefetch inteligente de próximas questões no modo offline do PWA via Dexie.
- Suporte completo a navegação por teclado nos modais de curadoria médica.
- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.
- Estratégia de evicção de pacotes expirados sob QuotaExceededError em `db.ts`.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída
- [x] **Resiliência de Cache e Rollback Transacional no Dexie (Frontend)**: Implementado método `syncQuestions` em `app/frontend/src/lib/db.ts` e refatorado `downloadSimuladoPackage` em `app/frontend/src/lib/simuladoPackage.ts` para persistência transacional atômica (`rw`) com validação prévia de integridade, isolamento de `_owner_id` e rollback automático em falhas, acompanhado de suíte unitária de 5 testes em `sync-questions-cache.test.mjs` (100% de aprovação e zero avisos de lint).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)

