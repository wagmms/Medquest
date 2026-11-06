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

- [ ] **Fatiamento Modular do Motor de Simulação Clínica OSCE (`app/backend/api/osce.py`)**:
    1. **Arquivo/Módulo Alvo**: `app/backend/api/osce.py` (3.087 linhas)
    2. **Função/Componente/Seletor**: Desacoplamento da engine de fisiologia, modificadores hemodinâmicos de fala e avaliador de barema
    3. **Comportamento Esperado / Critério de Aceite**: Extrair lógica de fisiologia para `api/services/osce/physiology.py` e avaliador de barema para `api/services/osce/grading.py`, mantendo a rota HTTP em `api/osce_routes.py` e 100% dos testes do OSCE verdes.

---

## 📋 Backlog Prioritário (Tarefas Cirúrgicas)

1. [ ] **Consolidação e Enxugamento da Camada de IA (`app/backend/api/universal_pool.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/universal_pool.py` e `app/backend/api/gemini_pool.py`
    - **Função/Componente/Seletor**: Camada de pool e Circuit Breaker
    - **Comportamento Esperado / Critério de Aceite**: Fundir a camada redundante `universal_pool.py` no `gemini_pool.py`, simplificando as chamadas e mantendo proteção de timeout e resiliência de rate limit.

2. [ ] **Isolamento de Matemática Psicométrica e Prontidão Bayesiana (`app/backend/api/stats.py`)**:
    - **Arquivo/Módulo Alvo**: `app/backend/api/stats.py` (2.045 linhas)
    - **Função/Componente/Seletor**: Funções `_beta_continued_fraction`, `regularized_incomplete_beta` e `calculate_bayesian_readiness`
    - **Comportamento Esperado / Critério de Aceite**: Mover funções matemáticas pesadas para serviço isolado `services/psychometrics.py`, reduzindo a complexidade ciclomática do controlador de estatísticas.

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

- [x] **Racionalização de Overengineering: Quarentena de Scripts e Desacoplamento do OSCE**: Arquivados com segurança 374 scripts legados em `archive/legacy_backend_scripts/` e duplicatas de SO da raiz em `archive/legacy_root_scripts/` via `git mv` (preservando 100% do histórico e git blame); reduzida a pasta `app/backend/scripts/` de 382 arquivos para apenas os 13 módulos vitais; extraídas 2.816 linhas de dados estáticos clínicos de `osce_data.py` para `app/backend/data/osce/canonical_stations.json`, transformando `osce_data.py` em facade leve de 28 linhas com `lru_cache`; adicionada trava anti-bloat em `test_pipeline_registry.py`; 100% dos 419 testes aprovados e `./validate.sh fast` em 1.30s.

> 📁 Histórico completo arquivado em [CHANGELOG.md](CHANGELOG.md)
