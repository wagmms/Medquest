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

- [ ] **Recuperação Defensiva de JSON Corrompido no Histórico FSRS (`app/backend/api/questions.py`)**:
    1. **Arquivo/Módulo Alvo**: `app/backend/api/questions.py`
    2. **Função/Componente/Seletor**: Rota `attempt` (`POST /api/questions/<int:qid>/attempt`)
    3. **Comportamento Esperado / Critério de Aceite**: Fornecer regeneração de estado padrão caso o JSON armazenado de `user_question_fsrs` esteja malformado ou corrompido, evitando erro 500 no review, coberto em `app/backend/tests/test_api.py`.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Prefetch PWA Transacional Offline de Próximas Questões do Caderno (`app/frontend/src/lib/syncQueue.ts`)**:
    - **Arquivo/Módulo Alvo**: `app/frontend/src/lib/syncQueue.ts` e `app/frontend/src/lib/db.ts`
    - **Função/Componente/Seletor**: Função `prefetchUpcomingQuestions(themeId, limit = 10)`
    - **Comportamento Esperado / Critério de Aceite**: Pré-carregar em segundo plano os enunciados e alternativas das 10 próximas questões na fila adaptativa do aluno para o cache Dexie, viabilizando transição com latência 0ms entre questões mesmo em conexões instáveis.

2. [ ] **Trap-Focus e Navegação por Teclado em Modais de Curadoria Médica (`app/frontend/src/components/QuestionClassificationModal.tsx`)**:
    - **Arquivo/Módulo Alvo**: `app/frontend/src/components/QuestionClassificationModal.tsx`
    - **Função/Componente/Seletor**: Componente `QuestionClassificationModal`
    - **Comportamento Esperado / Critério de Aceite**: Implementar trap-focus acessível e atalhos de escape/enter no modal garantindo conformidade WCAG 2.1 AA sem dependências externas.

3. [ ] **Padronização de Respostas de Erro e Contrato JSON nas Rotas de Questões (`app/backend/api/questions.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/questions.py`
    - **Função/Componente/Seletor**: Rotas `attempt` e `review`
    - **Comportamento Esperado / Critério de Aceite**: Retornar payload estruturado consistente `{"error": "...", "code": "..."}` com status HTTP semântico, coberto em `app/backend/tests/test_api.py`.

---

## 💡 Sugestões de Melhorias Futuras (Buffer Recente)

- Padronização de respostas 404 e contrato JSON em `api/questions.py`.
- Benchmark automatizado de carga para endpoints de fila adaptativa e remediação.
- Auditoria de contraste WCAG AAA nos badges de subtemas clínicos.
- Purga seletiva de imagens médicas no Cache Storage (`medquest-image-cache`) em saturação de disco.
- Exportação de caderno de erros em formato offline portátil com gabarito comentado congelado.

> 💡 Catálogo completo de sugestões arquivado em [docs/SUGESTOES_FUTURAS.md](docs/SUGESTOES_FUTURAS.md)

---

## ✅ Última Tarefa Concluída

- [x] **Recuperação de Quota e Evicção de Simulados Expirados no Dexie (Frontend)**: Implementada a rotina de purga atômica `purgeExpiredSimuladoPackages` e detecção robusta de `isQuotaExceededError` em `app/frontend/src/lib/db.ts` no método `syncQuestions` com retentativa pós-evicção, liberando espaço de pacotes expirados de `simuladoPackages` antes de abortar a transação, acompanhada por suíte de testes unitários com 10 cenários (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
