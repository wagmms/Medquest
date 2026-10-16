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

- [ ] **Etapa 2 do Simulador OSCE: Palco Clínico Triplo com Ator, Information Gating e Sons Reais de Ausculta (`app/frontend/src/app/osce/[id]/`)**:
    1. **Arquivo/Módulo Alvo**: `app/frontend/src/app/osce/[id]/OsceRoomClient.tsx` (e novos componentes `ClinicalStage.tsx` / `AuscultationPlayer.tsx`)
    2. **Função/Componente/Seletor**: Componente `ClinicalStage` e sub-rotinas de reprodução sonora semiológica
    3. **Comportamento Esperado / Critério de Aceite**: Substituir interface de chat rolável por HUD imersivo com legendas dinâmicas estilo cinema (2 linhas), canais de voz isolados para Ator vs Examinador com Information Gating e reprodução de áudio real de ausculta cardíaca/pulmonar nos focos anatômicos.

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

- [x] **Etapa 1 do Novo Simulador OSCE: Motor Fisiológico Reativo (VitalStateEngine) & Monitor Multiparamétrico 60fps**: Desenvolvido o hook `useVitalStateEngine` com cálculo determinístico de ciclo hemodinâmico a 1Hz, farmacocinética dinâmica (doses e drogas de emergência), jitter estocástico e simulação de manguito de PNI; construído o componente `<MultiparameterMonitor />` com renderização Canvas a 60fps de ECG contínuo DII e curva de SpO2 Pleth, sintetizador psicoacústico de bips por saturação via Web Audio API e modal tático de cardioversão sincronizada; adicionado suporte a `physiology_engine` em `osce.py` e `osce_data.py` com novo teste unitário `test_osce_physiology_engine` aprovado (18/18 testes e `validate.sh fast` em 14.97s).

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
