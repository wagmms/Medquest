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

- [ ] **Auditoria de Atomicidade e Metadados Médicos em Módulos de Flashcards Anki (`scripts/anki/`)**:
    1. **Arquivo/Módulo Alvo**: `scripts/anki/` (ou rotas e utilitários de flashcards em `app/backend/api/flashcards.py`)
    2. **Função/Componente/Seletor**: Validador de esquemas e sanitizador de cards médicos
    3. **Comportamento Esperado / Critério de Aceite**: Garantir conformidade com a diretriz inviolável de comentários canônicos somente-leitura e validar atomicidade clínica (frente/verso, cloze e tags).

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Hardening de Fallback e Cache de Perfil Adaptativo em Desconexão (`app/backend/api/adaptive.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/adaptive.py`
    - **Função/Componente/Seletor**: Funções de inferência adaptativa
    - **Comportamento Esperado / Critério de Aceite**: Garantir retorno determinístico e cache resiliente para perfil de estudo adaptativo quando a latência de banco aumentar ou em fallback offline.

2. [ ] **Validação e Prevenção de Desalinhamento Temporal em Sessões de Simulado (`app/frontend/src/app/simulado/SimuladoClient.tsx`)**:
    - **Arquivo/Módulo Alvo**: `app/frontend/src/app/simulado/SimuladoClient.tsx`
    - **Função/Componente/Seletor**: Hook de timer e persistência de sessão
    - **Comportamento Esperado / Critério de Aceite**: Prevenir drift de cronômetro e perda de respostas parciais em caso de suspensão de aba ou reconexão.

3. [ ] **Benchmark e Otimização de Resposta em Lote para Fila Adaptativa (`app/backend/api/adaptive.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/adaptive.py`
    - **Função/Componente/Seletor**: Rota `/api/adaptive/queue`
    - **Comportamento Esperado / Critério de Aceite**: Reduzir latência p95 para menos de 80ms em requisições de remediação concorrente.

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

- [x] **Blindagem de Identidade de Domínio FSRS, Resiliência Concorrente e Timer Offline (Argon vs ChatGPT)**: Implementada associação unívoca entre tentativa e review via `attempt_id` em toda a cadeia (schema `ReviewIn`, `questions.py`, `types/api.ts`, `api.ts` e `QuizClient.tsx`), eliminando condições de corrida e avanço indevido no agendador; blindado `SimuladoClient.tsx` contra loops de submissão no timer com `hasAutoSubmittedRef`, `inFlightPracticeRef` e circuit breaker defensivo; eliminada concorrência de escritas no IndexedDB em `FlashcardClient.tsx` com transações atômicas `localDb.transaction` e circuit breaker de AnkiConnect; calibrado peso de `latest_wrong` (55.0) no adaptive scoring; suite completa validada em `./validate.sh standard` (416 testes de backend aprovados, ESLint, TypeScript e Budgets 100% OK em 141s).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
