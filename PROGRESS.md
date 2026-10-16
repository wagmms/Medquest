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

- [ ] **Repaginação Geral da UI/UX do MedQuest: Clinical Precision Workspace & Anti-Slop Architecture (`app/frontend/src/`)**:
    1. **Arquivo/Módulo Alvo**: `app/frontend/src/app/globals.css`, `app/frontend/src/components/`, `app/frontend/src/app/(DashboardClient|estudar|revisao-ativa|osce)`
    2. **Função/Componente/Seletor**: Tokens Tailwind v4, ClinicalIcon, ClinicalAppShell (Desktop + Thumb-Zone BottomNav) e telas centrais
    3. **Comportamento Esperado / Critério de Aceite**: Erradicar visual de SaaS genérico e Material Symbols webfont; implementar paletas Radiology Dark e Ambulatório Paper; layout de split-pane para questões e dock de exames laboratoriais; FSRS v6 com atalhos 1-4 e telemetria de retenção; bottom nav mobile para plantão; 100% de aprovação na suíte de testes unitários e zero regressões.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Auditoria de Atomicidade e Metadados Médicos em Módulos de Flashcards Anki (`scripts/anki/`)**:
    - **Arquivo/Módulo Alvo**: `scripts/anki/` (ou rotas e utilitários de flashcards em `app/backend/api/flashcards.py`)
    - **Função/Componente/Seletor**: Validador de esquemas e sanitizador de cards médicos
    - **Comportamento Esperado / Critério de Aceite**: Garantir conformidade com a diretriz inviolável de comentários canônicos somente-leitura e validar atomicidade clínica (frente/verso, cloze e tags).

2. [ ] **Hardening de Fallback e Cache de Perfil Adaptativo em Desconexão (`app/backend/api/adaptive.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/adaptive.py`
    - **Função/Componente/Seletor**: Funções de inferência adaptativa
    - **Comportamento Esperado / Critério de Aceite**: Garantir retorno determinístico e cache resiliente para perfil de estudo adaptativo quando a latência de banco aumentar ou em fallback offline.

3. [ ] **Validação e Prevenção de Desalinhamento Temporal em Sessões de Simulado (`app/frontend/src/app/simulado/SimuladoClient.tsx`)**:
    - **Arquivo/Módulo Alvo**: `app/frontend/src/app/simulado/SimuladoClient.tsx`
    - **Função/Componente/Seletor**: Hook de timer e persistência de sessão
    - **Comportamento Esperado / Critério de Aceite**: Prevenir drift de cronômetro e perda de respostas parciais em caso de suspensão de aba ou reconexão.

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

- [x] **Etapa 4 do Novo Simulador OSCE: Avaliação Live de Barema, Red Flags com Travas de Segurança, Espelho Oficial de 2ª Fase & Feedback do Preceptor**: Implementado o motor determinístico `RedFlagEngine` mapeando violações críticas (laceração do feixe intercostal `RF_ANAT_NEUROVASC`, cricotireoidostomia sobre istmo tireoidiano `RF_ANAT_THYROID`, choque desincronizado em taquiarritmia com pulso `RF_ELEC_UNSYNC_VT`, quebra da sequência do ATLS `RF_ABCDE_VIOLATION` e drogas de risco letal `RF_PHARM_CONTRA`) com penalização de pontos e travas de teto de nota de segurança (`caps_station_at`); calculado o Radar de 5 Competências Médicas Fundamentais (`compute_competency_radar_5d`) e emitido veredito oficial da banca (`APROVADO COM DISTINÇÃO`, `APROVADO NO LIMITE`, `REPROVADO POR TÉCNICA` e `ELIMINADO POR IATROGENIA`); criado o componente de alta precisão `<StationResultMirror />` com spider chart em SVG puro leve (<10KB, 60fps), cards de Red Flags, Parecer do Preceptor Chefe com Conduta Canônica Padrão-Ouro, tabela com filtros por bloco e evidências capturadas; adicionados 3 novos testes unitários em `TestOsceStage4EvaluationAndMirror` (28/28 testes de backend aprovados) e validação completa via `./validate.sh fast` em 20.43s.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
