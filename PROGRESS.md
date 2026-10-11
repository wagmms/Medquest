# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] Implementar guardrail de sanitização em `app/frontend/src/components/ExplanationViewer.tsx` na função `parseExplanation` assegurando fallback defensivo e limpeza de delimitadores residuais órfãos em seções clínicas sem alterar ou mutar o conteúdo canônico original.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)
1. [ ] Implementar rotina de recuperação de quota e evicção em `app/frontend/src/lib/db.ts` no método `syncQuestions` expurgando pacotes expirados de `simuladoPackages` quando detectado `QuotaExceededError` com testes unitários em `app/frontend/scripts/tests/sync-questions-cache.test.mjs`.
2. [ ] Implementar recuperação defensiva e fallback para payload legado em `app/backend/api/questions.py` na rota `attempt` regenerando estado inicial caso o JSON de `user_question_fsrs` esteja corrompido com cobertura em `app/backend/tests/test_api.py`.
3. [ ] Implementar trap-focus e atalhos de navegação por teclado em `app/frontend/src/components/QuestionClassificationModal.tsx` no componente modal assegurando conformidade WCAG 2.1 AA sem dependências externas.

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
- [x] **Clamp Defensivo de Intervalo Mínimo FSRS D+1 (Backend)**: Implementado clamp defensivo na função `review` em `app/backend/api/srs.py` assegurando que qualquer agendamento `due` gerado respeite rigorosamente `D+1` (`>= 24 horas` a partir de `now`), protegendo tanto o payload do `Card` serializado quanto o valor ISO retornado contra drift de relógio do servidor, passos intradia acidentais ou estados degenerados, mantendo suporte opcional a `now` determinístico e acompanhado de testes unitários `test_defensive_clamp_forces_minimum_d_plus_one` e `test_defensive_clamp_preserves_longer_intervals` em `app/backend/tests/test_srs.py` (100% de aprovação na suíte de testes).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)

