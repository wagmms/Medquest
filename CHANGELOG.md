# 📜 MedQuest - Changelog de Tarefas Concluídas

Histórico completo de ciclos, sprints e melhorias entregues no repositório.

## [2026-10-16] - Etapa 1 do Novo Simulador OSCE: Motor Fisiológico Reativo (VitalStateEngine) & Monitor Multiparamétrico 60fps
- **Motor Fisiológico Reativo em Tempo Real (`app/frontend/src/app/osce/[id]/useVitalStateEngine.ts`)**:
  - Implementado o hook `useVitalStateEngine` com cálculo determinístico de ciclo hemodinâmico a 1Hz, modelando $S(t) = S_0 + \vec{D}_{\text{patologia}} + \sum \vec{I}_{\text{intervenções}} + \vec{\epsilon}(t)$.
  - Incorporada farmacocinética dinâmica (latência de início *onset*, pico e duração) para infusões de cristaloides, amiodarona, adenosina, noradrenalina, insulina e protocolo de transfusão maciça (1:1:1).
  - Adicionado jitter estocástico fisiológico ($\pm 1\%$) para oscilação natural dos parâmetros numéricos.
  - Implementada simulação de manguito de Pressão Não-Invasiva (PNI) com atraso de insuflação e cálculo da Pressão Arterial Média (PAM).
- **Monitor Multiparamétrico Virtual da Sala Vermelha (`app/frontend/src/app/osce/[id]/MultiparameterMonitor.tsx`)**:
  - Renderização contínua a 60 fps em HTML5 `<canvas>` com feixe de varredura (*sweep bar*) para traçados de ECG DII (verde) e Pletismografia de Oximetria SpO2 (ciano).
  - Formas de onda procedurais para ritmos clínicos: Ritmo Sinusal, Taquicardia Sinusal, TSV, Taquicardia Ventricular Monomórfica, Fibrilação Ventricular e Assistolia.
  - Sintetizador Psicoacústico via Web Audio API: bips na sístole modulados pela oximetria ($f = 440 + (\text{SpO}_2 - 80) \times 18\text{ Hz}$) e alarmes normatizados IEC com silenciamento por 2 minutos.
  - Modal tático de cardioversor/desfibrilador manual permitindo choque sincronizado ou desincronizado (com disparo de FV iatrogênica em caso de choque desincronizado em TV com pulso).
- **Backend & Modelagem de Fisiologia (`app/backend/api/osce.py`, `app/backend/api/osce_data.py`)**:
  - Função `_build_physiology_engine` com fallback determinístico e regras de progressão natural calibradas para as estações de choque e arritmias (`UNIFESP-2024-CM-TV`, `USP-RP-2024-CM-CAD`, `USP-RP-2023-CG-FAST`).
  - Atualizado endpoint `GET /api/osce/stations/<id>` expondo `physiology_engine` estruturado.
  - Novo teste unitário `test_osce_physiology_engine` em `app/backend/tests/test_osce.py` (18/18 testes aprovados).
  - Validação completa com `./validate.sh fast` (14.97s, zero erros de ESLint e testes verdes).

## [2026-10-15] - Execução Argon: Correções Cirúrgicas de Segurança (P0) e Resiliência de IA/Idempotência (P1)
- **Segurança de Credenciais e Governança Canônica (`app/backend/scripts/`)**:
  - `deepseek_map_hours.py`: Eliminada credencial Bearer da API DeepSeek exposta em texto claro; implementada leitura obrigatória via `os.environ["DEEPSEEK_API_KEY"]` com *fail-fast*.
  - `medway_client.py`: Removidas credenciais estáticas de Firebase (`FIREBASE_API_KEY`) e token de autenticação hardcoded, migrando para variáveis de ambiente.
  - `rewrite_medquest_explanations.py`: Purgadas credenciais padrão e adicionado bloqueio definitivo via `RuntimeError` para salvaguardar a diretriz inviolável de imutabilidade de comentários canônicos elaborados por professores de residência.
- **Proteção contra Prompt Injection e Hardening de Autenticação (`app/backend/api/`)**:
  - `ai.py`: Criada a função `_sanitize_prompt_input` com truncagem e neutralização de tags estruturais; enclausuradas as entradas livres do estudante em tags explícitas (`<student_query>`, `<student_response>`) nos modos de réplica e dúvida livre; reforçado o `system_instruction` do Preceptor IA com cláusula de bloqueio a jailbreaks e comandos de fuga.
  - `auth.py`: Criada a função `_is_testing_env` vinculando o bypass de teste estritamente a ambientes que não sejam de produção (`FLASK_ENV != "production"` e ausência de variáveis cloud/Render), blindando `require_auth`, `auth_me` e `require_curator`.
- **Resiliência de Rede e Circuit Breaker em IA (`app/backend/api/universal_pool.py`)**:
  - `universal_pool.py`: Implementado `CircuitBreaker` em memória com estados `CLOSED`, `OPEN` e `HALF_OPEN`; chamadas consecutivas com falha ativam Fast-Fail em $< 5\text{ms}$ prevenindo que workers Gunicorn fiquem retidos em chamadas externas degradadas; ajustado orçamento de timeout síncrono para 20s.
  - `tests/test_universal_pool.py`: Adicionado teste unitário `test_circuit_breaker_fast_fail` cobrindo abertura de circuito e rejeição imediata (7/7 testes aprovados).
- **Idempotência e Rastreabilidade de IA (`app/backend/api/questions.py`, `app/backend/api/ai_routes.py`)**:
  - `questions.py`: Integrado `reserve_idempotency` e `complete_idempotency` na rota `POST /simulado/sessions`, prevenindo duplicação de sessões e eventos em retries de rede.
  - `ai_routes.py`: Padronizada a proveniência `source = 'ai_synthesized'` e persistido `generated_at` no salvamento de explicações geradas por IA em `synthesize_explanation`.
- **Frontend & PWA (`app/frontend/src/lib/db.ts`)**:
  - `db.ts`: Adicionado fallback defensivo em `purgeExpiredSimuladoPackages` para adaptadores do Dexie sem suporte a `.where()`, restaurando 100% de aprovação na suíte de testes unitários do frontend (74/74 testes passando em `npm run test:unit`).
- **Validação de Regressão Zero**:
  - 399 testes de backend aprovados no `pytest`.
  - 74 testes unitários de frontend aprovados no Node.js test runner.
  - `./validate.sh fast` aprovado com sucesso em 18.25s e ESLint 100% limpo.

---
- **Persistência Distribuída e Resiliência LibSQL / SQLite (`app/backend/api/db.py`)**:
  - Implementada função `_sanitize_params` preservando parâmetros do tipo `dict` para queries nomeadas (`:param`), garantindo decodificação UTF-8 defensiva (`replace`) em strings e sequências sem corromper binários.
  - Refinada a função `_is_read_only_query` com regex de palavras-chave mutadoras (`INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER|...`), prevenindo que CTEs com escrita (`WITH ... DELETE/UPDATE`) sejam tratadas indevidamente como leitura e sofram retries duplicados.
  - Eliminado `TursoCursor.__del__` que disparava chamadas FFI/Rust durante o Garbage Collection em threads arbitrárias do Python; cursores de escrita (sem colunas) agora são fechados deterministicamente em `__init__`.
  - Tratamento defensivo em `TursoConnection.commit()` executando rollback e reconexão automática em caso de stream expirado; adicionado suporte a `SAVEPOINT` no context manager `db_transaction` para transações aninhadas seguras no SQLite local.
- **Harmonização do Motor FSRS v6 e Inteligência Adaptativa (`app/backend/api/adaptive.py`)**:
  - Unificada a instância do scheduler FSRS: `adaptive.py` agora importa `_question_scheduler` e `_safe_load_card` diretamente de `app/backend/api/srs.py`, garantindo paridade total com a calibração médica (retenção alvo 0.85, estabilidades $S_0$ e decaimento temporal idêntico).
- **Otimização do Pool de IA e Blindagem de Explicações Canônicas (`app/backend/api/gemini_pool.py`, `app/backend/api/ai_routes.py`)**:
  - `gemini_pool.py`: Corrigido o cálculo de `consecutive_429` e garantido piso mínimo de multiplicador (`max(1, ...)`); refatorado `get_available_key` para liberar o `lock` do pool antes de `time.sleep`, eliminando contenção de threads WSGI; filtrados blocos `"thought": true` nas partes de resposta de modelos Gemini 2.5/Flash para evitar vazamento de raciocínio interno nas explicações.
  - `ai_routes.py`: Reforçada a blindagem contra race condition na persistência de explicações sintetizadas, garantindo que a tabela `explanations` nunca sobrescreva explicações canônicas de professores já existentes.
- **Frontend, PWA e Otimização do Cache Dexie (`app/frontend/src/lib/db.ts`, `QuizClient.tsx`)**:
  - `db.ts`: Refatorado `purgeExpiredSimuladoPackages` para consultar diretamente os índices do Dexie (`expires_at` via `between` e `status` via `equals`) eliminando `toArray()` (full table scan em memória); restrita a exposição de `localDb` no objeto `window` apenas para ambiente de desenvolvimento (`NODE_ENV !== "production"`).
  - `QuizClient.tsx`: Marcada data sentinela otimista em `handleReviewFSRS` (`attemptResultRef.current = optimisticResult`), eliminando race condition que disparava reavaliação neutra concorrente (`duvida`) ao transicionar de questão.
  - Validação completa: 112 testes de backend aprovados e ESLint frontend 100% limpo em `./validate.sh fast`.

---

## [2026-10-12] - Entrega: Analisador Multimodal de Exames Médicos de Imagem (Padrão Ouro Semiológico)
- **Visão Computacional e Roteiros Semiológicos Canônicos (Backend & IA)**:
  - `app/backend/api/medical_vision.py`: Implementado o motor de análise multimodal com pré-processamento e redimensionamento proporcional inteligente via Pillow (`otimizar_imagem_para_analise`), roteiros semiológicos estruturados (ECG 12 derivações em 6 passos FMRP-USP/SBC, RX de tórax em ABCDE, TC de crânio com detecção de sangramentos agudos e desvio de linha média, Dermatologia com regra do ABCDE e OCR de exames laboratoriais); implementada a regra crítica de segurança com injeção obrigatória do Alerta de Sala Vermelha (`🚨 [ALERTA DE EMERGÊNCIA - SALA VERMELHA]`) na primeira linha do laudo em achados críticos.
  - `app/backend/api/gemini_pool.py`: Expandido o método `generate_content` para suportar `parts` multimodais arbitrárias contendo `inlineData` (base64) com balanceamento Round-Robin, fallback automático e função singleton `get_gemini_pool()`.
  - `app/backend/api/ai_routes.py`: Criado o endpoint `POST /api/ai/analyze-image` (e `/api/v1/ai/analyze-image`) aceitando imagens via multipart/form-data ou JSON (`image_base64`), modalidade e contexto clínico.
  - `app/backend/tests/test_medical_vision.py`: Criada suíte completa com 6 testes unitários e de integração validando otimização de imagem, extração de alertas críticos, rotas de API, suporte a base64 e multipart (100% de aprovação em `./validate.sh fast`).
  - `tooling/testador_master/`: Integrada a ação `analisar_exame_imagem` ao `DriverAPI`, personas médicas (`candidato_osce_pratico` e `r1_residencia_elite`), grafo de cobertura e dashboard visual interativo.

---

## [2026-10-12] - Ciclo Autoloop: Otimização de Renderização e Memoização nos Badges de Subtemas Clínicos
- **Desempenho Frontend e Ergonomia de Busca em Filtros de Estudo (Frontend)**:
  - `app/frontend/src/app/estudar/components/QuizFilters.tsx`: Criados subcomponentes puros memoizados `SubtemaChip` e `SubtemaDropdownItem` via `React.memo`, eliminando re-renders supérfluos; implementados hooks `useMemo` para normalização de array e `Set` de subtemas selecionados em $O(1)$, eliminando duplo filtro/slice inline no render; callbacks estáveis com `useCallback` (`handleRemoveSubtema`, `handleClearAllSubtemas`, `handleAddSubtema`) e adicionado atalho de teclado `Enter` no input de busca para seleção imediata do primeiro subtema filtrado com atributos ARIA (`role="listbox"`, `role="option"`).
  - `app/frontend/scripts/tests/quiz-filters-optimization.test.mjs`: Criada suíte com 5 testes unitários validando normalização defensiva, filtragem case-insensitive com exclusão em $O(1)$, teto de 50 itens e operações atômicas de adição e remoção de filtros (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

---

## [2026-10-12] - Ciclo Autoloop: Modelo de Domínio e Vocabulário Ubíquo da Plataforma Médica
- **Formalização do Modelo de Domínio e Vocabulário Ubíquo (Documentação & Arquitetura)**:
  - `GLOSSARY.md`: Criado documento canônico de vocabulário ubíquo estruturado pelas 4 dimensões essenciais da plataforma: *Conteúdo Médico e Curadoria Clínica* (Questão de Residência, Comentário do Professor/Explicação Canônica imutável, Grande Área, Subtema Canônico, Pulo do Gato), *Aprendizado Adaptativo e Repetição Espaçada* (FSRS v6, Estabilidade $S$, Dificuldade $D$, Grau de Confiança e Fila de Revisão do Dia D+1), *Avaliação Psicométrica e Modos de Treino* (Teoria de Resposta ao Item - TRI, Simulado e Caderno de Erros) e *Sincronização Local-First e Identidade* (Pacote Offline, Fila de Sincronização Transacional e Sessão Visitante/Modo Convidado). O glossário estabelece termos recomendados e termos a evitar (`_Evitar_`), eliminando ambiguidades conceituais em agentes autônomos, testes e documentação.

---

## [2026-10-12] - Ciclo Autoloop: Trap-Focus, Acessibilidade ARIA e Navegação por Teclado em Modais de Curadoria Médica
- **Ergonomia Frontend e Acessibilidade WCAG 2.1 AA em Modais (Frontend)**:
  - `app/frontend/src/lib/modalAccessibility.ts`: Criado módulo utilitário universal de acessibilidade com as funções `getFocusableElements(container)` (extração e filtragem de elementos focáveis interativos, ignorando desabilitados ou `aria-hidden`) e `handleModalKeyNavigation(event, options)` (gerenciador determinístico de trap-focus circular com Tab/Shift+Tab, atalho Escape com priorização de fechamento de subdiálogos e atalho rápido Ctrl+Enter/Cmd+Enter para submissão imediata).
  - `app/frontend/src/components/QuestionClassificationModal.tsx`: Integrada a gestão de foco acessível: memorização do elemento acionador original (`document.activeElement`) ao abrir com restauração de foco ao fechar, foco inicial automático no campo de busca de subtemas, vinculação semântica ARIA (`aria-describedby="classification-modal-description"`), atalho `Enter` no input de busca para seleção imediata de subtema único e anéis visuais de foco (`focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none`) em todos os botões e campos interativos.
  - `app/frontend/scripts/tests/modal-trap-focus.test.mjs`: Criada suíte com 8 testes unitários cobrindo trap-focus, tecla Escape com e sem modal de confirmação, short-circuit em estado ocupado, atalhos Ctrl/Cmd+Enter e filtragem de elementos focáveis (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

---

## [2026-10-12] - Entrega: Testador Master Ostensivo do MedQuest (E2E & API com Personas Médicas e TUI)
- **Robô Autônomo de Alta Fidelidade para Auditoria e Testes Contínuos (Tooling & Scripts)**:
  - `tooling/testador_master/testador_master.py`: Implementado o orquestrador com CLI completo (`--mode`, `--persona`, `--cycles`, `--duration`, `--delay`, `--no-clear`), loop de eventos, encerramento gracioso e salvamento contínuo de relatórios.
  - `tooling/testador_master/personas.py`: Criado o catálogo de personas médicas (*Internato Generalista*, *R1 Residência Elite*, *Revisor FSRS Metódico*, *Candidato OSCE Prático*, *Caótico Fuzzer*), com objetivos de estudo, pesos de ações clínicas e balões de raciocínio.
  - `tooling/testador_master/driver_api.py`: Driver in-memory ultrarrápido sobre Flask test-client cobrindo questões, FSRS v6, flashcards, simulados, TRI, estações práticas OSCE, estatísticas e busca semântica com latência sub-10ms.
  - `tooling/testador_master/driver_e2e.py`: Driver de frontend integrado com Playwright para execução de jornadas visuais no Next.js (App Router).
  - `tooling/testador_master/medical_oracle.py`: Oráculo de integridade médica com bloqueio inviolável de alteração de comentários canônicos de professores em `explanations`, validação de intervalos D+1+/D+7 do FSRS v6 e sanidade matemática do TRI.
  - `tooling/testador_master/crawler_engine.py`: Motor de grafo de recursos e cobertura (`MedQuestGraph`) rastreando nós, arestas e métricas em `data/testador_master_grafo.json`.
  - `tooling/testador_master/tui_renderer.py`: Interface rica de terminal (Anti-UI-Slop) com cores ANSI de alto contraste, telemetria em tempo real e visualização de raciocínio clínico.
  - `tooling/testador_master/reporter.py` e `repro_generator.py`: Geração automática do relatório vivo executivo em `docs/RELATORIO_TESTADOR_MASTER.md`, dados em JSON e auto-geração de scripts de reprodução isolada em `tests/repros/` para falhas.
  - `tooling/testador_master/dashboard_generator.py` & `docs/dashboard_grafo.html`: Dashboard visual autônomo e interativo em HTML gerado com Vis.js, exibindo rede de nós de telas e rotas de API, telemetria clínica, feed de personas em tempo real, filtros dinâmicos e métricas de cobertura física.
  - `scripts/iniciar_testador_master.sh`: Launcher em bash para execução interativa em janela visível de monitor.

---

## [2026-10-12] - Ciclo Autoloop: Prefetch PWA Transacional Offline de Próximas Questões do Caderno
- **Transição com Latência 0ms e Cache Offline Atômico no Dexie (Frontend)**:
  - `app/frontend/src/lib/db.ts`: Implementado o método `getCachedQuestionIds` na classe `MedQuestDB` e utilitário exportado para consulta rápida em lote de IDs persistidos no IndexedDB por `_owner_id`.
  - `app/frontend/src/lib/syncQueue.ts`: Criado o módulo unificado de prefetch offline com as funções `prefetchUpcomingQuestions(themeId, limit = 10)` e `prefetchQuestionsByIds(ids, options)`, implementando sanitização defensiva, isolamento SSR, desduplicação de chamadas concorrentes em memória e sincronização transacional atômica via `syncQuestions` com emissão de evento `questions-prefetched`.
  - `app/frontend/src/app/estudar/QuizClient.tsx`: Integrado o pré-carregamento contínuo em segundo plano na rotação de questões e carregamento de lote inicial de 10 questões no `loadQueue`, garantindo transição sem latência mesmo com conexão intermitente.
  - `app/frontend/scripts/tests/sync-queue-prefetch.test.mjs`: Criada suíte com 8 testes unitários cobrindo operação SSR, sanitização de IDs, short-circuit offline, integridade de transações Dexie e desduplicação de requisições concorrentes (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

---

## [2026-10-12] - Ciclo Autoloop: Recuperação Defensiva de JSON FSRS Corrompido e Contratos Padronizados
- **Robustez e Recuperação Defensiva no Motor FSRS e Rotas de Questões (Backend)**:
  - `app/backend/api/srs.py`: Implementada a função `_safe_load_card(card_json)` com deserialização defensiva contra JSONs truncados, malformados ou esquemas incompatíveis em `spaced_repetition.fsrs_card`, regenerando um `Card` padrão sem lançar exceções.
  - `app/backend/api/questions.py`: Adicionado logging formal e blocos de fallback defensivo em `submit_attempt` (`POST /api/questions/<int:qid>/attempt`), `review_fsrs` (`POST /api/questions/<int:qid>/review`) e `_process_single_attempt` (`POST /attempt/batch`), prevenindo erro 500 no fluxo de estudo mesmo com registros de repetição corrompidos no banco.
  - `app/backend/api/questions.py`: Padronizados os contratos de resposta de erro HTTP 400 e 404 em `submit_attempt`, `review_fsrs` e `question_detail` com códigos semânticos estruturados (`INVALID_INPUT`, `QUESTION_NOT_FOUND`, `NO_ATTEMPT_FOUND`) preservando retrocompatibilidade com o campo `error`.
  - `app/backend/tests/test_srs.py`: Adicionado teste unitário `test_review_recupera_json_corrompido_ou_invalido` cobrindo strings truncadas, tipos não-objeto, esquemas incompatíveis e strings vazias.
  - `app/backend/tests/test_api.py`: Adicionados testes de integração `test_attempt_e_review_recupera_fsrs_card_corrompido` e `test_attempt_and_review_invalid_input_standard_code`, com 100% de aprovação (57 testes aprovados em `./validate.sh fast` e 390 testes em toda a suíte de backend).

---

## [2026-10-11] - Ciclo Autoloop: Recuperação de Quota e Evicção de Simulados Expirados no Dexie
- **Recuperação de Quota e Evicção de Pacotes Expirados (Frontend)**:
  - `app/frontend/src/lib/db.ts`: Implementadas a função `isQuotaExceededError` (detecção abrangente de erros de cota de armazenamento via DOMException código 22, nome, regex e wraps de transações/erros internos do Dexie) e o método transacional atômico `purgeExpiredSimuladoPackages`, purgado pacotes expirados (`status === 'expired'` ou `expires_at <= now`) da tabela `simuladoPackages` e emitindo evento `simulado-packages-purged`; integrado guardrail de recuperação em `syncQuestions` para purgar pacotes vencidos e retentar atomicamente a persistência de questões antes de abortar/relançar o erro caso não haja espaço liberado.
  - `app/frontend/src/lib/simuladoPackage.ts`: Atualizado tratamento de erro de download de simulado para reutilizar o helper canônico `isQuotaExceededError`.
  - `app/frontend/scripts/tests/sync-questions-cache.test.mjs`: Expandida suíte de testes com 5 novos cenários (totalizando 10 testes unitários), validando detecção de erros de cota, purga atômica e preservação de pacotes válidos, retentativa bem-sucedida após liberação de espaço, aborto com propagação de erro quando não há pacotes expirados, e execução defensiva em SSR (100% de aprovação em `npm run test:unit`, `npm run lint` e `./validate.sh fast`).

---

## [2026-10-11] - Ciclo Autoloop: Guardrail de Sanitização e Parsing Defensivo em ExplanationViewer
- **Sanitização de Delimitadores Residuais e Robustez em Explicações (Frontend)**:
  - `app/frontend/src/components/ExplanationViewer.tsx`: Implementada a função `cleanSectionDelimiters` e atualizada a função `parseExplanation` com guardrails defensivos (`try/catch`, validação estrita de tipos e fallback gracioso), eliminando delimitadores residuais órfãos (asteriscos de fechamento em cabeçalhos colon-inside como `**Cabeçalho:**`, dois-pontos soltos, divisores horizontais vazios e quebras) em todas as seções clínicas (`puloDoGato`, `raciocinioClinico`, `padraoResposta`, `alternativaCorreta` e `distratores`), eliminando distratores fantasmas e preservando estritamente a formatação legítima de listas e comentários canônicos de professores.
  - `app/frontend/scripts/tests/explanation-viewer-sanitization.test.mjs`: Criada suíte com 5 testes unitários cobrindo sanitização de delimitadores órfãos, fallback defensivo para dados nulos/corrompidos/não-string, comentários colon-inside, seções discursivas e isolamento de Raciocínio Clínico (100% de aprovação em `npm run test:unit` e `./validate.sh fast`).

---

## [2026-10-11] - Ciclo Autoloop: Clamp Defensivo de Intervalo Mínimo D+1 no FSRS
- **Integridade Temporal e Robustez no Agendamento SRS (Backend)**:
  - `app/backend/api/srs.py`: Implementado clamp defensivo incondicional na função `review` assegurando que todo agendamento `due` gerado respeite rigorosamente `D+1` (`>= 24 horas` a partir de `now`), protegendo tanto o payload do `Card` serializado quanto o valor ISO retornado contra drift de relógio do servidor, passos intradia acidentais ou estados numéricos degenerados, mantendo suporte opcional a `now` determinístico para testes e auditorias temporais.
  - `app/backend/tests/test_srs.py`: Adicionados testes unitários `test_defensive_clamp_forces_minimum_d_plus_one` e `test_defensive_clamp_preserves_longer_intervals` na suíte `TestFSRSValidation`, comprovando o clamp em agendamentos simulados no passado ou intradia (< 24h) e garantindo a preservação exata de intervalos legítimos de longa maturação (~7d a ~78d) (100% de aprovação na suíte de testes).

---

## [2026-10-11] - Ciclo Autoloop: Validação de Existência Prévia em Favoritos
- **Integridade Referencial e Validação de Favoritos (Backend)**:
  - `app/backend/api/questions.py`: Implementada verificação de existência prévia de questão na rota `toggle_favorite` (`POST /api/questions/<int:qid>/favorite`), retornando HTTP 404 (`{"error": "Questão não encontrada"}`) e liberando token de idempotência caso a questão não exista no banco, prevenindo inserção de chaves órfãs na tabela `favorites`.
  - `app/backend/tests/test_api.py`: Adicionado teste unitário `test_question_favorite_not_found` validando resposta HTTP 404 para toggle padrão, favorito explícito (`is_favorite=True`), desfavoritar explícito (`is_favorite=False`) e assegurando ausência de registros órfãos persistidos na tabela `favorites` (100% de aprovação na suíte de testes).

---

## [2026-10-11] - Ciclo Autoloop: Resiliência de Cache e Rollback Transacional no Dexie
- **Resiliência e Atomicidade no Cache Offline (Frontend)**:
  - `app/frontend/src/lib/db.ts`: Implementado método `syncQuestions` na classe `MedQuestDB` e helper exportado `syncQuestions`, provendo sincronização transacional atômica (`rw`) no Dexie com rollback automático, isolamento por `_owner_id` e validação defensiva pré-transação contra registros malformados ou IDs inválidos.
  - `app/frontend/src/lib/simuladoPackage.ts`: Refatorado download de pacotes de simulado para persistir lotes de questões através de `localDb.syncQuestions(details, uid)`, substituindo chamada direta e frágil a `bulkPut` por operação transacional protegida contra dados parciais.
  - `app/frontend/scripts/tests/sync-questions-cache.test.mjs`: Criada suíte com 5 testes unitários validando atomicidade, rejeição estrita de dados corrompidos antes de transações, vinculação de `_owner_id`, garantia de rollback em falhas de I/O / cota e operação segura em ambiente SSR (100% de aprovação em `npm run test:unit`).

---

## [2026-10-11] - Ciclo Autoloop: Testes de Estresse e Invariantes do FSRS v6
- **Validação de Invariantes Temporais e Estresse no Motor FSRS (Backend)**:
  - `app/backend/tests/test_srs.py`: Implementada a classe de testes `TestFSRSValidation` cobrindo calibração de parâmetros (`desired_retention=0.85`, `learning_steps=()`, `relearning_steps=()`, `_QUESTION_PARAMS`), estresse sob 25 erros consecutivos em questões e flashcards, simulação temporal realista de 64 revisões mistas, recuperação de estabilidade pós-lapso e garantia de que nenhum agendamento gere passos intradia (< 24h) ou intervalos negativos.

---

## [2026-10-11] - Ciclo Autoloop: Otimização de Contagem de Questões e Cache TTL
- **Performance e Resiliência na Contagem de Questões (Backend)**:
  - `app/backend/api/questions.py`: Implementado suporte unificado a `/api/questions/count` e `/api/questions/counts` com cache em memória `count_cache` (TTL 60s, max 1000 entradas), separando escopo de catálogo global de filtros atrelados a usuário (`status`, `unanswered_only`, `favorite`), com tempo de resposta < 10ms.
  - `app/backend/api/questions.py`: Invalidação de `count_cache` por usuário integrada à rotina `invalidate_user_caches(user_id)` após respostas e revisões.
  - `app/backend/tests/test_api.py`: Expandido teste `test_questions_count_with_filters` validando alias `/counts`, combinação de `area` e `subtema` via índice composto `idx_questions_area_subtema`, resposta imediata do cache em memória e invalidação atrelada ao usuário.

---

## [2026-10-11] - Ciclo Autoloop: Tipagem Estrita e Acessibilidade em Componentes de Questão
- **Acessibilidade e Semântica ARIA no Frontend**:
  - `app/frontend/src/app/estudar/components/AlternativeList.tsx`: Adicionado container com `role="region"` e `aria-label="Alternativas da questão"`, `aria-label` descritivo e sintetizado em cada alternativa com estado dinâmico (selecionada/riscada/gabarito), além de `aria-hidden="true"` nos ícones e marcadores visuais.
  - `app/frontend/src/components/ExplanationViewer.tsx`: Adicionado `aria-hidden="true"` em todos os ícones decorativos de cabeçalho (`Award`, `Sparkles`, `Stethoscope`, `CheckCircle2`, `XCircle`, `AlertCircle`) e atributos acessíveis no modal de zoom de imagens médicas.
  - `app/frontend/src/components/QuestionClassificationModal.tsx`: Vinculado `aria-labelledby="classification-modal-title"`, `aria-pressed` nos seletores de Grande Área e subtema, e `aria-hidden="true"` em todos os ícones funcionais e de feedback.
  - `app/frontend/src/components/PreceptorFocusCard.tsx`, `QuizTimer.tsx`, `SubjectTreeSelector.tsx`, `OfflinePanel.tsx`, `ImageViewer.tsx`, `FormattedContent.tsx`: Reforçados papéis acessíveis de timer, diálogos modais e zoom.
- **Blindagem de Deploy e Imutabilidade de Explicações**:
  - `deploy.py` e `tests/test_deploy.py`: Implantação de lock físico de exclusão mútua (`fcntl.flock`), verificação obrigatória de branch `main`, integridade de SHA e validação de pareceres de auditoria.
  - `app/backend/api/ai_routes.py`: Proteção estrita de explicações canônicas de professores (`canonical_professor_locked`), impedindo regeneração e desperdício de tokens de IA.
  - `app/backend/scripts/sync_db_turso.py`: Validação defensiva do payload retornado pelo Turso Pipeline HTTP.

---

## [2026-10-10] - Ciclo Autoloop: Auditoria e Cobertura de Testes Unitários de API
- **Cobertura de Testes de API (Backend)**:
  - `app/backend/tests/test_api.py`: Expandida suíte com 10 novos testes cobrindo filtros de área/ano/subtema, status wrong/answered, toggle de favoritos, contagens, overview zero-state, distratores e modos adaptativos.
  - Correção do edge-case `NOT IN (NULL)` na query SQL de remediação.

---

## [2026-10-10] - Setup Inicial do Autoloop
- **Setup Seguro Inicial**:
  - Configuração da branch segura `autoloop/dev` e criação de `PROGRESS.md`.
  - Correção de data fixa em `test_planner.py`.
