# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Adicionar testes de estresse em `app/backend/tests/test_srs.py` na classe `TestFSRSValidation` garantindo que intervalos de repetição FSRS v6 nunca retornem valores negativos ou passos intradia indesejados (< 24h) com retenção calibrada em 0.85.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Reforçar resiliência de cache em `app/frontend/src/lib/db.ts` no método `syncQuestions` assegurando tratamento defensivo de falha de conexão e rollback transacional no Dexie.
2. [ ] Criar validação de existência prévia em `app/backend/api/questions.py` na função `toggle_favorite` prevenindo inserção de `question_id` inexistente na tabela `favorites`.
3. [ ] Implementar telemetria de latência em `app/backend/api/db.py` no método `_execute_with_reconnect` medindo tempos de roundtrip em consultas remotas LibSQL.

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
- [x] **Otimização de Contagem de Questões e Cache TTL (Backend)**: Otimizado endpoint `/api/questions/count` e alias `/api/questions/counts` em `app/backend/api/questions.py` com `count_cache` (TTL 60s, max 1000 entradas), aproveitamento do índice composto `idx_questions_area_subtema` (< 10ms), invalidação por usuário em `invalidate_user_caches` e cobertura completa em `tests/test_api.py`.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
