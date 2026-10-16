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

- [ ] **Etapa 4 do Simulador OSCE: Avaliação Live de Barema, Espelho de Prova em 2ª Fase & Feedback do Preceptor (`app/backend/api/osce.py`, `app/frontend/src/app/osce/[id]/`)**:
    1. **Arquivo/Módulo Alvo**: `app/backend/api/osce.py`, `app/frontend/src/app/osce/[id]/OsceRoomClient.tsx`, `app/frontend/src/app/osce/[id]/LiveBaremaModal.tsx`
    2. **Função/Componente/Seletor**: Função `evaluate_live_barema_progress`, componente do espelho de prova pós-estação e radar de competências
    3. **Comportamento Esperado / Critério de Aceite**: Auditoria automatizada de itens cumpridos no barema com pontuação ponderada (USP/UNICAMP/INEP), detecção de erros eliminatórios imediatos (ex: atropelo de ABCDE, iatrogenias vasculares) e geração de espelho de prova com nota final e plano de estudos corretivo.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Repaginação Geral da UI/UX do MedQuest: Clinical Precision Workspace & Anti-Slop Architecture (`app/frontend/src/`)**:
    - **Arquivo/Módulo Alvo**: `app/frontend/src/app/globals.css`, `app/frontend/src/components/`, `app/frontend/src/app/(DashboardClient|estudar|revisao-ativa|osce)`
    - **Função/Componente/Seletor**: Tokens Tailwind v4, ClinicalIcon, ClinicalAppShell (Desktop + Thumb-Zone BottomNav) e telas centrais
    - **Comportamento Esperado / Critério de Aceite**: Erradicar visual de SaaS genérico e Material Symbols webfont; implementar paletas Radiology Dark e Ambulatório Paper; layout de split-pane para questões e dock de exames laboratoriais; FSRS v6 com atalhos 1-4 e telemetria de retenção; bottom nav mobile para plantão; 100% de aprovação na suíte de testes unitários e zero regressões.

2. [ ] **Auditoria de Atomicidade e Metadados Médicos em Módulos de Flashcards Anki (`scripts/anki/`)**:
    - **Arquivo/Módulo Alvo**: `scripts/anki/` (ou rotas e utilitários de flashcards em `app/backend/api/flashcards.py`)
    - **Função/Componente/Seletor**: Validador de esquemas e sanitizador de cards médicos
    - **Comportamento Esperado / Critério de Aceite**: Garantir conformidade com a diretriz inviolável de comentários canônicos somente-leitura e validar atomicidade clínica (frente/verso, cloze e tags).

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

- [x] **Etapa 3 do Novo Simulador OSCE: Gestão de Insumos SUS, Fila de Enfermagem com Latência & Manequim Cirúrgico 2D**: Desenvolvido o manequim vetorial multicamadas em SVG cirúrgico (<30KB, 60fps) com mapeamento milimétrico de marcos anatômicos e hitboxes de segurança vs iatrogenia (toracocentese em borda superior vs laceração intercostal em borda inferior; cricotireoidostomia vs lesão do istmo tireoidiano; dreno de tórax no 5º EIC; janelas completas do E-FAST e acesso vascular); implementadas matrizes de insumos dos 3 níveis de complexidade do SUS (UBS, UPA e Terciário) com bloqueio físico de materiais; criada a fila de enfermagem assíncrona com latência clínica real (20-40s) e preempção em choque; criados 4 novos testes unitários em `TestOsceStage3MannequinAndProcedures` (25/25 testes de backend passando) e validação completa com `./validate.sh fast` em 16.41s.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
