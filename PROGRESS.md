# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).
> 5. Respeite a calibração do algoritmo FSRS v6 (retenção 0.85 e intervalos com piso D+1).

---

## 🔄 Próxima Tarefa em Andamento

- [ ] **Isolamento de Matemática Psicométrica e Prontidão Bayesiana (`app/backend/api/stats.py`)**:
    1. **Arquivo/Módulo Alvo**: `app/backend/api/stats.py`
    2. **Função/Componente/Seletor**: Funções `_beta_continued_fraction`, `regularized_incomplete_beta` e `calculate_bayesian_readiness`
    3. **Comportamento Esperado / Critério de Aceite**: Mover funções matemáticas pesadas para serviço isolado `app/backend/api/services/psychometrics.py`, reexportando os símbolos públicos em `stats.py` para manter compatibilidade e 100% da suíte `pytest` verde.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Separação de Serviço do Motor de Questões (`app/backend/api/questions.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/questions.py`
    - **Função/Componente/Seletor**: Regras de filtragem SRS/caderno de erros e paginação de questões fora dos handlers HTTP
    - **Comportamento Esperado / Critério de Aceite**: Extrair queries e montagem de payload para `app/backend/api/services/questions_service.py`, preservando contratos de resposta e caches em `api/cache.py`.

2. [ ] **Fatiamento Restante da Fisiologia OSCE (`app/backend/api/osce.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/osce.py`
    - **Função/Componente/Seletor**: Engine fisiológica e ciclo de vida de sessão após a extração já concluída de `osce_prompts.py` e `osce_evaluation.py`
    - **Comportamento Esperado / Critério de Aceite**: Extrair a engine fisiológica restante para `app/backend/api/osce_physiology.py`, mantendo reexports em `osce.py` e 100% dos testes do OSCE verdes.

3. [ ] **Hardening de Fallback e Cache de Perfil Adaptativo em Desconexão (`app/backend/api/adaptive.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/adaptive.py`
    - **Função/Componente/Seletor**: Funções de inferência adaptativa
    - **Comportamento Esperado / Critério de Aceite**: Garantir retorno determinístico e cache resiliente para perfil de estudo adaptativo quando a latência de banco aumentar ou em fallback offline.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)

- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.
- Auditoria de contraste WCAG AAA nos badges de subtemas clínicos.
- Purga seletiva de imagens médicas no Cache Storage (`medquest-image-cache`) em saturação de disco.
- Exportação de caderno de erros em formato offline portátil com gabarito comentado congelado.
- Bot Telegram de pílulas de questões diárias FSRS.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída

- [x] **Sincronização `Medquest-aistudio`, Hardening de Segurança e Refatoração Arquitetural (2026-11-14)**: Removidos `/revisao-ativa` no frontend (`manifest.json`, `OfflinePanel.tsx`), endpoints/código morto (`synthesize_explanation`, `prescribe_study`, `analyze-image`, `medical_vision.py`, `universal_pool.py`, frontend estático legado preservando `static/images/`, duplicatas `canonical_*.json` na raiz); aplicadas `@require_auth`, `get_current_user_id()` e idempotência OSCE; isolados `<SessionTimer>` e `useOsceAudio.ts` no frontend (`useOfflineStatus`, `navigation.ts`); unificados `SimpleTTLCache` em `api/cache.py`, `_fetch_attempt_rollup` SQL CTE em `stats.py` e extraídos `osce_prompts.py` + `osce_evaluation.py`.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
