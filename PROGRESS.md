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

- [x] **Auditoria de Resiliência Concorrente, Blindagem FSRS e Fidelidade Temporal Offline com Gemini 4 Argon**: Arbitragem profunda entre análises técnicas; mitigada repetição indevida de escritas no Turso e preservados `lastrowid`/`rowcount` em `TursoCursor`; corrigido `NameError` em `synthesize_explanation`; implementado `answered_at` defensivo contra clock skew no backend; eliminado avanço duplo do FSRS e falso gabarito 'A' no Simulado; integrada cobertura real por tema no rank adaptativo; implementada detecção de negação e harmonização de hipercalemia no `ClinicalSafetyGuard` do OSCE; validação rápida `./validate.sh fast` 100% aprovada (114 testes e lints em 18.50s).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
