# MedQuest - Regras & Diretrizes do Projeto para Agentes IA

Este documento define a arquitetura, convenções e regras críticas de execução do projeto **MedQuest**. Sempre consulte estas regras antes de propor mudanças, refatorações ou novos scripts.

---

## 1. Visão Geral da Arquitetura

O MedQuest é uma plataforma médica de aprendizado adaptativo e questões comentadas com repetição espaçada (FSRS), organizada como monorepo:

* **Backend (`app/backend/`)**:
  * **Framework**: Flask (Python 3.12+) com Blueprints modulares em `api/`.
  * **Banco de Dados**: Híbrido SQLite local (`app/backend/medquest.db`) e **Turso Cloud** (LibSQL).
  * **Motor SRS**: FSRS v6 (`fsrs`) em `api/srs.py` e perfil adaptativo em `api/adaptive.py`.
  * **Ambiente Virtual**: `.venv/` em `app/backend/` gerenciado com suporte a `uv` ou `pip`.
* **Frontend (`app/frontend/`)**:
  * **Framework**: Next.js 16+ (App Router) com React 19 e TypeScript.
  * **Estilização**: Tailwind CSS v4 (`@tailwindcss/postcss`).
  * **Autenticação**: Clerk (`@clerk/nextjs`) com suporte a modo visitante via proxy interno.
  * **Offline/PWA**: Dexie (IndexedDB) e `@ducanh2912/next-pwa`.
  * **Testes E2E**: Playwright (`npm run test:e2e`).
* **Automação & Deploy (Raiz)**:
  * Runner de validação em camadas: `scripts/dev_check.py` / `validate.sh`.
  * Script unificado de deploy e sincronização Turso: `deploy.py` / `deploy.sh`.

---

## 2. Regras Críticas do Banco de Dados (Turso / LibSQL)

1. **Camada de Abstração Obrigatória**:
   * Todas as operações de banco devem passar exclusivamente pela camada implementada em [`app/backend/api/db.py`](file:///home/wagmoraes/Projetos%20Prog/MedQuest/app/backend/api/db.py) (`get_db()`, `TursoConnection`, `TursoCursor`).
   * O cliente nativo `libsql` possui runtime em Rust e **não pode ser compartilhado indiscriminadamente entre threads**. Conexões persistentes por thread-local (`_turso_clients`) são gerenciadas internamente.

2. **Tratamento de Conexões Expiradas (Stale Stream)**:
   * Turso fecha conexões WebSocket/stream inativas (erros contendo `stream not found`, `baton`, `hrana`, status 404/408).
   * O método `_execute_with_reconnect` e `_executemany_with_reconnect` já tratam reconexão automática segura para declarações idempotentes fora de transação ativa. **Não capture nem mascare essas exceções de forma que impeça a reconexão.**

3. **Operações em Lote (`executemany`)**:
   * Sempre passe dados sanitizados (strings UTF-8 limpas, decodificando `bytes` para texto se necessário).
   * O `TursoConnection.executemany` inclui fallback sequencial caso o driver nativo falhe em lotes remotos heterogêneos.

---

## 3. Diretrizes do FSRS & Algoritmo Adaptativo

1. **Parâmetros Calibrados para Questões Médicas Longas (`api/srs.py`)**:
   * Questões de prova utilizam o scheduler calibrado:
     * Retenção alvo: `desired_retention = 0.85`.
     * Intervalos iniciais longos: `S0(Again) = 3.5` (~7 dias no erro), `S0(Hard) = 8.0`, `S0(Good) = 18.0`, `S0(Easy) = 40.0`.
     * `learning_steps = ()` e `relearning_steps = ()` (sem passos de minutos intradia).
   * Flashcards atômicos utilizam o scheduler padrão sem passos intradia (mínimo D+1 no erro).

2. **Mapeamento de Confiança do Aluno**:
   * `errou` -> `Rating.Again`
   * `acertou + chutei` -> `Rating.Hard`
   * `acertou + duvida` -> `Rating.Good`
   * `acertou + certeza` -> `Rating.Easy`

3. **Prevenção de Avanço Duplo**:
   * Não reavalie nem avance o estado FSRS repetidamente na mesma questão se o usuário apenas alterar anotações ou fizer retificação sem responder novamente.

---

## 4. Regras de Frontend & Autenticação

1. **Middleware & Sessão de Visitante (`app/frontend/src/proxy.ts`)**:
   * O Clerk gerencia autenticação oficial. Usuários não autenticados recebem uma sessão de convidado via cookie `medquest_guest_session` (UUIDv4).
   * **Nunca confie** em cabeçalhos de identidade vindos diretamente do navegador. O middleware injeta `x-internal-guest-id` garantindo sanitização.

2. **Tailwind CSS v4 & React 19**:
   * O projeto usa Tailwind v4. Não adicione arquivos legados `tailwind.config.js` nem dependências do Tailwind v3.
   * Respeite o modelo de Server Components vs Client Components (`'use client'`) do Next.js App Router.

---

## 5. Comandos Padronizados de Execução & Testes

Ao testar ou validar alterações, utilize sempre os comandos canônicos:

* **Validação Rápida (Recomendada)**:
  ```bash
  ./validate.sh fast        # Execução incremental baseada em diff (< 15s)
  ./validate.sh standard    # Validação do componente alterado
  ./validate.sh full        # Suíte completa de build e testes
  ```

* **Testes de Backend**:
  ```bash
  cd app/backend
  ../../app/backend/.venv/bin/pytest tests/ -q
  # Ou com uv:
  uv run pytest tests/ -q
  ```

* **Testes & Build de Frontend**:
  ```bash
  cd app/frontend
  npm run lint
  npm run build
  npm run test:e2e
  ```

* **Deploy & Sincronização**:
  ```bash
  ./deploy.sh               # Sync do SQLite com Turso Cloud + Git Commit/Push
  ./deploy.sh --db-only     # Apenas sincronização de banco
  ```
