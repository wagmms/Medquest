# Relatório de Auditoria Técnica, Segurança e Resiliência — MedQuest
**Data**: 15 de Outubro de 2026  
**Status da Auditoria**: Concluída (100% Read-Only no Código-Fonte)  
**Motor de Análise**: `gemini-argon`  
**Escopo**: Backend Flask (`app/backend/`), Frontend Next.js (`app/frontend/`), Scripts de Automação e Infraestrutura  

---

## Sumário Executivo

A auditoria técnica e arquitetural de ponta a ponta inspecionou a conformidade operacional, a segurança, a resiliência de rede/LLM, as fronteiras de domínio e a higiene estrutural do projeto **MedQuest**.

### Indicadores Gerais de Saúde do Código
- **Backend (Pytest)**: 398 testes executados com 100% de aprovação (`398 passed in 68.37s`).
- **Frontend (Node Test Runner)**: 74 testes unitários com 72 aprovações e 2 falhas pontuais no mock do Dexie (`sync-questions-cache.test.mjs`).
- **Vulnerabilidades Críticas (P0)**: 5 achados (chaves de API expostas em scripts legados, script violador de diretriz canônica médica e risco de prompt injection em entradas livres de alunos).
- **Inchaço Estrutural**: ~755 MB de arquivos mortos (`.bak` de SQLite e tarballs) consumindo espaço em disco na árvore ativa.

---

## Eixo 1 — Segurança & Gestão de Credenciais (P0)

### 1.1 Rastreamento de Credenciais e Segredos Expostos
Foram identificados segredos e chaves de API ativas/hardcoded em arquivos rastreados no repositório:

1. **Token Bearer da API DeepSeek exposto em texto claro**:
   - **Arquivo:Linha**: [`app/backend/scripts/deepseek_map_hours.py:8`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/deepseek_map_hours.py#L8)
   - **Evidência**: `"Authorization": "Bearer sk-2dc9602f50834037a65e670c2d4aada0"`
   - **Severidade**: **P0 (Crítico)**
   - **Risco**: Consumo não autorizado de cotas, vazamento financeiro e comprometimento de conta em plataformas externas.
   - **Ação**: Rotacionar imediatamente a credencial no console DeepSeek, expurgar a string do código e tornar obrigatório o carregamento via `os.environ["DEEPSEEK_API_KEY"]` com *fail-fast*.

2. **Chave de API Firebase exposta em script**:
   - **Arquivo:Linha**: [`app/backend/scripts/medway_client.py:20`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/medway_client.py#L20)
   - **Evidência**: `FIREBASE_API_KEY = "AIzaSyCOOvkFhuLp-MXInY5AJNsnbNc9Qg41vo8"`
   - **Severidade**: **P0 (Crítico)**
   - **Risco**: Abuso de cotas do projeto Firebase/Google Cloud e exposição da infraestrutura do cliente de extração.
   - **Ação**: Revogar a credencial no Google Cloud Console e mover para variável de ambiente.

3. **Chaves de API em defaults de `os.environ.get`**:
   - **Arquivo:Linha**: [`app/backend/scripts/rewrite_medquest_explanations.py:51`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/rewrite_medquest_explanations.py#L51) e [`app/backend/scripts/rewrite_medquest_explanations.py:57`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/rewrite_medquest_explanations.py#L57)
   - **Evidência**: `os.environ.get("YUNQIAO_API_KEY", "sk-2pqLEozeRTA1kaORC1dHNv3u5R8RkgukcVXByDgQOQrBr3iT")` e `os.environ.get("SOMAAPI_KEY", "sk-f9CuFhW85HXOW3Z7TObNSi0pYFCH69euabKFQkF9EnVQov00")`
   - **Severidade**: **P0 (Crítico)**
   - **Risco**: Chaves de provedores de IA hardcoded como fallback.
   - **Ação**: Purgar as strings hardcoded.

4. **Script Violador da Diretriz Inviolável de Comentários Canônicos**:
   - **Arquivo:Linha**: [`app/backend/scripts/rewrite_medquest_explanations.py:1-120`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/rewrite_medquest_explanations.py#L1-L120)
   - **Evidência**: O script foi projetado para iterar sobre a tabela `explanations` e reescrever comentários médicos usando LLMs.
   - **Severidade**: **P0 (Crítico - Violação de Governança Médica)**
   - **Risco**: Violação direta da regra canônica: *"Os comentários e resoluções de questões de residência médica foram elaborados e revisados diretamente por professores e especialistas médicos. São materiais canônicos e congelados. Proibição Estrita de Edição e Revisão por IA. Consumo Zero de Tokens"*.
   - **Ação**: Excluir permanentemente o script ou arquivá-lo em quarentena estrita inoperante.

### 1.2 Higienização de Inputs e Proteção contra Injeção
- **SQL Injection**: O projeto adota uma postura robusta na camada de dados ([`app/backend/api/db.py`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/db.py)). As queries em rotas centrais utilizam placeholders parametrizados `?`. Consultas dinâmicas em [`app/backend/api/filters.py`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/filters.py) e [`app/backend/api/stats.py`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/stats.py) sanitizam parâmetros ou aplicam whitelists estritas (`ALLOWED_BREAKDOWN_COLS`, `ALLOWED_ANALYSIS_INSTITUTIONS`).
- **Prompt Injection (P0)**:
  - **Arquivo:Linha**: [`app/backend/api/ai.py:747`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai.py#L747), [`app/backend/api/ai.py:763`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai.py#L763) e [`app/backend/api/ai.py:661`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai.py#L661)
  - **Evidência**: `DÚVIDA ESPECÍFICA: "{user_query}"` e `history_lines.append(f"**{role_label}**: {c}")` interpolam o texto enviado diretamente pelo usuário no corpo do prompt do Preceptor IA sem tags de isolamento.
  - **Risco**: Jailbreaks podem forçar a IA a ignorar instruções prévias, emitir diagnósticos incorretos ou expor detalhes do prompt do sistema.
  - **Ação**: Enclausurar mensagens do usuário em blocos `<aluno_input>...</aluno_input>` e incluir instrução canônica no system prompt informando que qualquer comando de sobrescrita contido no bloco de entrada deve ser desconsiderado.

- **Bypass de Autenticação em Ambiente `TESTING` (P1)**:
  - **Arquivo:Linha**: [`app/backend/api/auth.py:69-80`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/auth.py#L69-L80)
  - **Evidência**: Se `current_app.config.get("TESTING") == True`, o decorador `require_auth` confia cegamente em `request.headers["X-User-ID"]` ou adota usuário padrão `"1"`.
  - **Ação**: Blindar a verificação para que opere apenas se `app.testing` for verdadeiro E `os.environ.get("FLASK_ENV") != "production"` E variáveis de ambiente do Render/produção estiverem ausentes.

---

## Eixo 2 — Resiliência de Rede, Integração `gemini-argon`/LLM & Idempotência (P0/P1)

### 2.1 Resiliência de Chamadas Externas e Risco de Starvation de Workers (P0)
- **Arquivo:Linha**: [`app/backend/api/universal_pool.py:76`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/universal_pool.py#L76) e [`app/backend/api/gemini_pool.py:285-300`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/gemini_pool.py#L285-L300)
- **Diagnóstico**: `generate_content_with_fallback` utiliza orçamento máximo de 35 segundos (`max_total_seconds=max(provider_timeout, 35.0)`). Em momentos de degradação da API Google Gemini ou falhas de rede lentas, a chamada retém a thread síncrona do Flask por até 35s.
- **Impacto em Produção**: O deploy padrão (Render/Gunicorn) aloca tipicamente 4 workers. Se 4 requisições consecutivas de IA enfrentarem alta latência, 100% dos workers ficam travados aguardando socket de rede, causando DoS completo nas rotas leves de estudo (ex: submissão de respostas, listagem de questões).
- **Correção Proposta**:
  1. Implementar um **Circuit Breaker** em memória no `universal_pool.py`: após $N$ falhas consecutivas ou timeouts, abrir o circuito por 60s, retornando fallback imediato em $< 5\text{ms}$ sem consumir thread do pool.
  2. Reduzir o teto de timeout interativo para rotas web de 35s para no máximo 12s.

### 2.2 Idempotência e Prevenção de Duplicação de Estado (P1)
O mecanismo de idempotência em [`app/backend/api/idempotency.py`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/idempotency.py) é exemplar: possui lease lock de 30s, controle por token de posse (`lease_owner_token`) e hash SHA-256 do payload.
Contudo, sua aplicação não é homogênea:

| Rota / Operação | Arquivo:Linha | Possui Idempotência? | Risco em Flutuação de Rede |
| :--- | :--- | :---: | :--- |
| `POST /questions/<qid>/attempt` | `questions.py:837` | **Sim** (`reserve_idempotency`) | Protegido contra duplo envio. |
| `POST /questions/<qid>/review` | `questions.py:957` | **Sim** (`reserve_idempotency`) | Protegido. |
| `POST /attempt/batch` | `questions.py:1156` | **Sim** (`reserve_idempotency`) | Protegido. |
| `POST /simulado/sessions` | [`questions.py:370`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/questions.py#L370) | **Não** | **Gera sessões de simulado duplicadas**. |
| `POST /flashcards/save` | [`flashcards.py:129`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/flashcards.py#L129) | **Não** | **Duplica cartões de revisão no Anki/banco**. |
| `POST /osce/sessions/start` | [`osce_routes.py:71`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/osce_routes.py#L71) | **Não** | **Duplica instâncias de estações clínicas**. |

- **Correção Proposta**: Estender a chamada de `reserve_idempotency` e `complete_idempotency` para `/simulado/sessions` e `/flashcards/save`.

### 2.3 Rastreabilidade de Conteúdo Gerado por IA (P1)
- **Arquivo:Linha**: [`app/backend/api/ai_routes.py:227-236`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai_routes.py#L227-L236)
- **Diagnóstico**: Quando uma questão não possui explicação canônica e a síntese é realizada via IA, ela é inserida na tabela `explanations` sem marcação explícita de metadados (`source`).
- **Correção**: Assegurar coluna ou metadado indicando `source = 'ai_synthesized'`, evitando contaminação do acervo autoral de professores.

---

## Eixo 3 — Fronteiras de Domínio (Core MedQuest vs. Infraestrutura) (P1/P2)

### 3.1 Acoplamento Extremo de Domínio em `stats.py` e `questions.py`
O projeto possui módulos que misturam três responsabilidades distintas:
1. **Roteamento HTTP / Serialização** (Flask `@bp.route`, `request.args`, `jsonify`).
2. **Infraestrutura / Persistência** (Queries SQL com `get_db()`, joins complexos, transações).
3. **Domínio Médico Puro** (Estatística bayesiana de aprovação, algoritmo FSRS v6, cálculo de Wilson, TRI).

- **Arquivo:Linha**: [`app/backend/api/stats.py:1-2046`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/stats.py#L1-L2046)
  - Módulo monolítico com mais de 2.000 linhas.
  - Funções puras de estatística médica (`regularized_incomplete_beta`, `beta_quantile`, `weighted_beta_credible_interval`, `calculate_wilson_ci`, `calculate_bayesian_readiness`) convivem no mesmo arquivo que lida com requisições HTTP e queries no banco.
- **Arquivo:Linha**: [`app/backend/api/questions.py:832-940`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/questions.py#L832-L940) (`submit_attempt`)
  - Uma única função de 108 linhas gerencia validação, query de questão, avaliação de discursiva, regras de gabarito, cálculo FSRS da questão original e da questão espelho (`twin_for_question_id`), gravação no banco, invalidação de caches e despacho de evento de telemetria.

### 3.2 Contratos de Extração para Motores de Domínio Puros (Zero Mocks / In-Memory)

Para permitir testes unitários determinísticos com tempo de execução inferior a $10\text{ms}$ e sem necessidade de fixtures de banco de dados, propõe-se a seguinte extração:

#### Contrato 1: Motor Puro de Prontidão para Residência (`ExamReadinessEngine`)
```python
# app/backend/domain/metrics/readiness.py (Zero Flask, Zero SQLite)
from dataclasses import dataclass
from typing import List, Dict

@dataclass(frozen=True)
class AreaMetricInput:
    area: str
    total_available: int
    answered: int
    correct: int
    edital_weight: float

@dataclass(frozen=True)
class ReadinessResult:
    predicted_score: float
    credible_interval: tuple[float, float]
    evidence_status: str
    area_breakdowns: Dict[str, dict]

class ExamReadinessEngine:
    @staticmethod
    def calculate(inputs: List[AreaMetricInput]) -> ReadinessResult:
        """Executa cálculo bayesiano ponderado com regularização beta pura em memória."""
        ...
```

#### Contrato 2: Motor Puro de Avaliação de Tentativa (`AttemptEvaluationEngine`)
```python
# app/backend/domain/study/attempt.py (Zero Flask, Zero SQLite)
@dataclass(frozen=True)
class AttemptContext:
    selected_letter: str
    correct_letter: str
    correct_alternatives: set[str]
    confidence: str
    is_discursive: bool
    current_fsrs_card_json: str | None

@dataclass(frozen=True)
class AttemptOutcome:
    is_correct: bool | None
    next_fsrs_card_json: str
    next_review_date: str

class AttemptEvaluationEngine:
    @staticmethod
    def evaluate(ctx: AttemptContext, now_utc) -> AttemptOutcome:
        """Determina acerto e avança o estado FSRS v6 de forma 100% determinística."""
        ...
```

---

## Eixo 4 — Higiene Estrutural & Confiabilidade de Build/Testes (P2/P3)

### 4.1 Inchaço do Repositório por Arquivos Mortos e Backups Legados (P2)
Foram localizados arquivos pesados que inflam o tamanho do repositório e o clone de novas instâncias:

1. **Backups de Banco de Dados Mortos dentro de `app/backend/`**:
   - `app/backend/medquest.db.bak_gabaritos_1791388409` (**650 MB**)
   - `app/backend/medquest.db.bak_20260920_095510` (**105 MB**)
   - `backups/medquest-before-theme-hub-20260920.tar.gz` (**~2 MB**)
   - **Impacto**: Mais de **755 MB** de espaço consumido por backups legados dentro de pastas ativas.
   - **Ação**: Mover para arquivamento externo e adicionar regras estritas no `.gitignore` (`*.bak*`, `*.tar.gz`).

2. **Proliferação Caótica de Scripts de Sincronização Turso**:
   - Em `app/backend/scripts/`: foram mapeados mais de 20 scripts de sincronização duplicados (`sync_all_turso.py`, `sync_all_turso_batch.py`, `sync_all_turso_chunked.py`, `sync_clean_to_turso.py`, `sync_content_to_turso.py`, `sync_database_turso.py`, `sync_db_turso.py`, `sync_ultra_fast_turso.py`, etc.).
   - **Impacto**: O projeto já possui [`deploy.py`](file:///home/wagmoraes/Projetos%20IA/MedQuest/deploy.py) e [`deploy.sh`](file:///home/wagmoraes/Projetos%20IA/MedQuest/deploy.sh) na raiz como runners canônicos oficiais. A presença de 20 variantes obsoletas induz erros operacionais.
   - **Ação**: Descontinuar e mover scripts legados de sincronização para `archive/scripts/`.

3. **Scripts e Arquivos de Teste Soltos na Raiz e Backend**:
   - Na raiz: `export_batch.py`, `inspecionar.py`, `batch_input_pilot.jsonl` (666 KB).
   - Em `app/backend/`: `test_ai2.py`, `test_ai3.py`, `test_api.py`, `test_db_ai.py`, `test_fetch.py`, `test_preceptor.py`, `test_preceptor_ai.py`, `inspect_db.py`, `query.py`.
   - **Ação**: Consolidar utilitários de desenvolvimento em `tooling/` ou `scripts/dev/` e remover arquivos temporários.

### 4.2 Diagnóstico da Suíte de Testes & Falhas Detectadas
- **Backend**: 398 testes rodando via `pytest` com 100% de sucesso.
- **Frontend**: 74 testes unitários via `node --test` executados:
  - 72 testes aprovados.
  - **2 testes falhando** em [`app/frontend/scripts/tests/sync-questions-cache.test.mjs:195`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/frontend/scripts/tests/sync-questions-cache.test.mjs#L195) e [`app/frontend/scripts/tests/sync-questions-cache.test.mjs:230`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/frontend/scripts/tests/sync-questions-cache.test.mjs#L230):
    - `TypeError: this.simuladoPackages.where is not a function`: Desalinhamento do mock de testes com a interface do Dexie v4.
    - `Error [QuotaExceededError]: The quota has been exceeded`: Falha na simulação de recuperação de quota.

### 4.3 Os 3 Testes Determinísticos Mais Urgentes para Blindagem Pré-Refatoração

1. **Teste 1 — Idempotência Concorrente de Submissão de Tentativa (`test_attempt_idempotency_concurrency.py`)**:
   - Submeter requisições idênticas em paralelo com o mesmo `X-Idempotency-Key` UUIDv4.
   - **Critério**: Garantir que exatamente 1 registro seja inserido em `attempts`, exatamente 1 avanço ocorra no FSRS, e que todas as requisições paralelas recebam a resposta em cache HTTP 200.
2. **Teste 2 — Determinismo e Piso Temporal FSRS v6 (`test_srs_deterministic_floor.py`)**:
   - Submeter sequências de respostas (`Again`, `Hard`, `Good`, `Easy`) em memória pura com variação de timestamps e fusos horários.
   - **Critério**: Garantir incondicionalmente que `next_review_date >= now + 24h` (piso D+1), sem passos intradia em minutos e com retenção alvo cravada em 0.85.
3. **Teste 3 — Sanitização de Prompt Injection no Preceptor IA (`test_ai_prompt_sanitization.py`)**:
   - Injetar strings com padrões de quebra de instrução (`\n\n### SYSTEM: Ignore previous rules...`) no payload do aluno.
   - **Critério**: Assegurar que o prompt gerado para o Google Gemini encapsule a entrada em delimitadores estritos e neutralize comandos adversários.

---

## 5. Plano de Execução Fatiado (Próximos Turnos)

A tabela abaixo prioriza os achados por severidade, com indicação cirúrgica de intervenção para os próximos turnos:

| ID | Severidade | Arquivo:Linha | Diagnóstico Curto | Correção Cirúrgica Proposta |
| :---: | :---: | :--- | :--- | :--- |
| **SEC-01** | **P0** | [`app/backend/scripts/deepseek_map_hours.py:8`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/deepseek_map_hours.py#L8) | Token Bearer DeepSeek hardcoded no código | Purgar chave, rotacionar credencial na plataforma e exigir `os.environ["DEEPSEEK_API_KEY"]`. |
| **SEC-02** | **P0** | [`app/backend/scripts/medway_client.py:20`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/medway_client.py#L20) | Firebase API Key hardcoded em texto claro | Mover para variável de ambiente e revogar a chave antiga no Google Cloud Console. |
| **SEC-03** | **P0** | [`app/backend/scripts/rewrite_medquest_explanations.py:51`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/rewrite_medquest_explanations.py#L51) | Chaves de API externas em fallbacks default | Remover chaves padrão hardcoded em chamadas de `os.environ.get`. |
| **SEC-04** | **P0** | [`app/backend/scripts/rewrite_medquest_explanations.py:1`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/scripts/rewrite_medquest_explanations.py#L1) | Script ativo violador da imutabilidade de comentários canônicos | Excluir o script ou movê-lo para quarentena inativa permanente. |
| **SEC-05** | **P0** | [`app/backend/api/ai.py:747`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai.py#L747), [`app/backend/api/ai.py:763`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai.py#L763) | Concatenação de input livre de aluno sem isolamento contra Prompt Injection | Enclausurar entradas do usuário em tags `<aluno_input>` e incluir regra de bloqueio no system prompt. |
| **RES-01** | **P0** | [`app/backend/api/universal_pool.py:76`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/universal_pool.py#L76) | Timeout total de 35s sem Circuit Breaker pode esgotar workers Gunicorn | Implementar Circuit Breaker (Fail-Fast) em memória e reduzir timeout interativo para 12s. |
| **SEC-06** | **P1** | [`app/backend/api/auth.py:69`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/auth.py#L69) | Bypass de autenticação dependente exclusivamente de `config["TESTING"]` | Exigir `app.testing and os.environ.get("FLASK_ENV") != "production"` e ausência de vars de cloud. |
| **RES-02** | **P1** | [`app/backend/api/questions.py:370`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/questions.py#L370), [`app/backend/api/flashcards.py:129`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/flashcards.py#L129) | Criação de simulados e flashcards sem checagem de idempotência | Adicionar `reserve_idempotency` e `complete_idempotency` com chave de cabeçalho `X-Idempotency-Key`. |
| **RES-03** | **P1** | [`app/backend/api/ai_routes.py:227`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/ai_routes.py#L227) | Explicações sintetizadas por IA inseridas sem tag explícita de proveniência | Salvar metadado/coluna de proveniência (`source = 'ai_synthesized'`) para preservar integridade de dados. |
| **ARCH-01** | **P1** | [`app/backend/api/stats.py:714-830`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/stats.py#L714-L830) | Cálculos estatísticos bayesianos misturados com Flask e SQL em monólito de 2k linhas | Extrair motor puro de estatística para `app/backend/domain/metrics/readiness.py` (Zero Mocks). |
| **ARCH-02** | **P1** | [`app/backend/api/questions.py:832-940`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/questions.py#L832-L940) | Lógica de submissão e orquestração de tentativa acoplada a rota HTTP | Criar caso de uso puro `SubmitAttemptUseCase` isolando regras de negócio e FSRS. |
| **ARCH-03** | **P2** | [`app/backend/api/adaptive.py:84`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/backend/api/adaptive.py#L84) | Ranqueamento adaptativo misturado com queries de banco de dados | Separar em repositório de candidatos (I/O) e algoritmo puro de ranqueamento em memória. |
| **HYG-01** | **P2** | `app/backend/medquest.db.bak_*` | 755 MB de backups legados de SQLite inflando o repositório | Mover backups para armazenamento externo e adicionar `*.bak*` ao `.gitignore`. |
| **HYG-02** | **P2** | `app/backend/scripts/sync_*turso*.py` | Mais de 20 scripts legados de sincronização gerando ambiguidade arquitetural | Arquivar variantes obsoletas em `archive/scripts/` e documentar `deploy.py` como único oficial. |
| **HYG-03** | **P2** | [`app/frontend/scripts/tests/sync-questions-cache.test.mjs:195`](file:///home/wagmoraes/Projetos%20IA/MedQuest/app/frontend/scripts/tests/sync-questions-cache.test.mjs#L195) | 2 testes unitários do frontend quebrando por erro de mock Dexie v4 | Corrigir interface mock de `simuladoPackages` para restaurar 100% de aprovação no frontend. |
| **HYG-04** | **P3** | Raiz e `app/backend/test_*.py` | Scripts pontuais de teste soltos fora das pastas oficiais | Mover utilitários para `tooling/` ou `scripts/dev/` e remover arquivos temporários de teste. |

---

## Conclusão da Auditoria

A base de código do **MedQuest** possui excelente maturidade nos pilares centrais de repetição espaçada (FSRS v6 calibrado para questões de residência médica com retenção 0.85 e piso D+1), proteção contra injeções SQL e cobertura de testes de backend (398 testes ativos aprovados).

As intervenções mais críticas e imediatas para o **Turno 2** concentram-se na higienização de credenciais expostas em scripts legados (**SEC-01** a **SEC-03**), eliminação do script violador de comentários canônicos (**SEC-04**), proteção contra starvation de workers de IA via Circuit Breaker (**RES-01**), e blindagem de rotas mutadoras com idempotência (**RES-02**).
