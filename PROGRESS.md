# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Reforçar resiliência de cache em `app/frontend/src/lib/db.ts` no método `syncQuestions` assegurando tratamento defensivo de falha de conexão e rollback transacional no Dexie.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Criar validação de existência prévia em `app/backend/api/questions.py` na função `toggle_favorite` prevenindo inserção de `question_id` inexistente na tabela `favorites`.
2. [ ] Implementar telemetria de latência em `app/backend/api/db.py` no método `_execute_with_reconnect` medindo tempos de roundtrip em consultas remotas LibSQL.
3. [ ] Implementar guardrail de sanitização em `app/frontend/src/components/ExplanationViewer.tsx` na renderização de texto assegurando fallback contra marcações residuais em comentários clínicos sem alterar o conteúdo canônico.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)
- Guardrail defensivo explícito contra drift temporal em `api/srs.py` (piso D+1).
- Telemetria de latência para consultas remotas LibSQL/Turso Cloud em `api/db.py`.
- Prefetch inteligente de próximas questões no modo offline do PWA via Dexie.
- Suporte completo a navegação por teclado nos modais de curadoria médica.
- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída
- [x] **Testes de Estresse e Invariantes do FSRS v6 (Backend)**: Implementada suíte `TestFSRSValidation` em `app/backend/tests/test_srs.py` com 6 novos testes validando retenção 0.85, ausência estrita de passos intradia (< 24h), integridade temporal sob 25 erros consecutivos e simulação realista de 64 revisões de prova.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)

