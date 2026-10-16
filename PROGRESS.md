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

- [ ] **Etapa 3 do Simulador OSCE: Gestão de Insumos Críticos, Latência de Enfermagem e Manequim Cirúrgico 2D (`app/frontend/src/app/osce/[id]/`)**:
    1. **Arquivo/Módulo Alvo**: `app/frontend/src/app/osce/[id]/ProcedureMannequin.tsx` e `app/backend/api/osce.py`
    2. **Função/Componente/Seletor**: Componente `ProcedureMannequin` e sub-rotinas de latência de enfermagem / estoque de insumos beira-leito
    3. **Comportamento Esperado / Critério de Aceite**: Modelar atraso temporal operacional da equipe de enfermagem para drogas venosas/intubação (latência com feedback na tela), estoque de insumos críticos por complexidade SUS e manequim interativo com zonas anatômicas ativas de punção/drenagem.

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

- [x] **Etapa 2 do Novo Simulador OSCE: Palco Clínico Triplo, Semiotécnica Bruta Acústica & Roteador Dual-Agent**: Criado o componente `<ClinicalStage />` com HUD cinematográfico de 2 falas com fade (eliminando chat rolável), seletor tático de canal (Paciente vs Examinador) via `Tab`, prontuário de bolso retrátil e silhueta anatômica com focos de ausculta; desenvolvido o `StethoscopeAudioEngine` sintetizando 6 sons brutos via Web Audio API modulados por FC e FR; implementado no backend (`osce.py` e `osce_routes.py`) o roteador dual-agent com modulação fonatória hemodinâmica (`get_hemodynamic_speech_modifier`), *Information Gating* estrito e postura neutra/fria da banca examinadora; adicionados 3 novos testes unitários em `TestOsceStage2DualAgentAndAuscultation` (21/21 testes passando e `validate.sh fast` em 18.59s).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
