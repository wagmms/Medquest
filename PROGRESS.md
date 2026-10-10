# 🎯 MedQuest - Progresso e Backlog de Engenharia Autônoma

### STATUS: ATIVO

> **Diretrizes de Segurança do Autoloop**:
> 1. Todas as alterações ocorrem na branch `autoloop/dev`. A `main` e a produção (`medquest.live` / Render) estão 100% protegidas.
> 2. Valide cada mudança com `./validate.sh fast` antes de dar a tarefa como concluída.
> 3. Não modifique `app/frontend/src/proxy.ts`, `app/backend/api/db.py` ou credenciais do Clerk.
> 4. Nunca faça alterações automáticas em bancos de produção (Turso Cloud).

---

## 🔄 Próxima Tarefa em Andamento
- [ ] **Tipagem Estrita e Acessibilidade em Componentes de Questão (Frontend)**
  - Revisar componentes em `app/frontend/src/components` para eliminar `any` implícito no TypeScript e assegurar atributos ARIA acessíveis.
  - Executar `npm run lint` em `app/frontend` para garantir zero avisos.

---

## 📋 Backlog Prioritário (Tarefas Atômicas e Seguras)
1. [ ] **Resiliência e Cache de Consultas SQLite Locais (Backend)**
   - Otimizar indexação de subtemas e áreas médicas em consultas frequentes de contagem de questões.
   - Manter total compatibilidade com `TursoConnection` em `api/db.py`.

2. [ ] **Validação Defensiva de Parâmetros FSRS v6 (Backend)**
   - Adicionar testes de estresse em `app/backend/tests/test_fsrs.py` para garantir que intervalos de repetição nunca retornem valores negativos ou passos intradia indesejados.

3. [ ] **Auditoria de Componentes de Layout PWA e Offline (Frontend)**
   - Verificar sincronização do Dexie no frontend para casos de perda momentânea de conexão de rede.

---

## 💡 Sugestões de Melhorias Futuras
- Adicionar painel de telemetria de latência para consultas LibSQL/Turso.
- Implementar prefetch inteligente de próximas questões no modo offline do PWA.
- Validar existência de question_id em toggle_favorite para prevenir favoritos de IDs órfãos.
- Criar benchmark automatizado de carga para endpoints de fila adaptativa e remediação.

---

## ✅ Histórico de Tarefas Concluídas
- [x] **Auditoria e Cobertura de Testes Unitários de API (Backend)** (Expandida suíte test_api.py com 10 novos testes cobrindo filtros de área/ano/subtema, status wrong/answered, toggle de favoritos, contagens, overview zero-state, distratores, modos adaptativos e correção do edge-case NOT IN (NULL) em remediation)
- [x] **Configuração da Branch Segura autoloop/dev e Correção de Data Fixa em test_planner.py** (Setup inicial blindado)
