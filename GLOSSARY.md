# Glossário de Domínio - MedQuest

Plataforma médica de aprendizado adaptativo, repetição espaçada de alta retenção (FSRS) e resolução de questões de residência médica com operação local-first.

---

## Conteúdo Médico e Curadoria Clínica

**Questão de Residência**:
Enunciado clínico canônico oriundo de processos seletivos oficiais de acesso direto ou pré-requisito (ENARE, USP, UNIFESP, etc.), acompanhado de distratores objetivos e alternativa correta.
_Evitar_: Pergunta, item de prova, card de teste.

**Comentário do Professor (Explicação Canônica)**:
Resolução técnica formal e raciocínio clínico elaborado exclusivamente por preceptores e médicos especialistas, imutável e estritamente somente-leitura.
_Evitar_: Feedback da IA, justificativa gerada, correção automática.

**Grande Área**:
Uma das cinco especialidades basilares canônicas da medicina (Cirurgia Geral, Clínica Médica, Ginecologia e Obstetrícia, Medicina Preventiva e Social, Pediatria).
_Evitar_: Categoria macro, departamento, divisão médica.

**Subtema Canônico**:
Classificação taxonômica padronizada de patologias, síndromes ou condutas clínicas dentro de uma grande área (ex: Cardiologia, Trauma, Neonatologia).
_Evitar_: Tag, assunto genérico, tópico livre.

**Pulo do Gato**:
Síntese clínica de alto rendimento que destaca a chave diagnóstica patognomônica ou a conduta terapêutica mandatória para resolução ágil da questão.
_Evitar_: Macete, dica rápida, resumo.

---

## Aprendizado Adaptativo e Repetição Espaçada

**Repetição Espaçada (FSRS v6)**:
Motor matemático baseado no modelo *Free Spaced Repetition Scheduler* calibrado para retenção alvo de 85% em ciclos médicos de longo prazo.
_Evitar_: Algoritmo Leitner, Anki tradicional, SM-2.

**Estabilidade ($S$)**:
Intervalo estimado em dias para que a probabilidade de recordação do conceito médico pelo aluno decline até o limiar alvo de 85%.
_Evitar_: Intervalo bruto, tempo de vida da memória.

**Dificuldade ($D$)**:
Índice intrínseco de complexidade de retenção do item médico na escala de 1 a 10, calibrado continuamente pelo histórico de acertos e falhas do aluno.
_Evitar_: Dificuldade da questão na prova, peso do item.

**Grau de Confiança (Autoavaliação de Certeza)**:
Metadado cognitivo informado pelo estudante ao submeter a resposta (`errou`, `chutei`, `duvida`, `certeza`) que mapeia a transição de estado FSRS.
_Evitar_: Rating arbitrário, nota subjetiva, pontuação.

**Fila de Revisão do Dia**:
Coleção priorizada de questões cujo vencimento temporal (`due`) alcançou a data atual, garantindo piso defensivo mínimo de repetição em D+1.
_Evitar_: Fila diária, deck pendente, tarefas do dia.

---

## Avaliação Psicométrica e Modos de Treino

**Teoria de Resposta ao Item (TRI)**:
Modelo psicométrico probabilístico que estima a proficiência real do aluno considerando discriminação, dificuldade e probabilidade de acerto casual dos itens.
_Evitar_: Percentual simples de acerto, média aritmética, nota bruta.

**Simulado**:
Sessão formal cronometrada com bloco pré-determinado de questões de bancas específicas que emula rigorosamente as condições de prova de residência médica.
_Evitar_: Quiz, provinha, teste avulso.

**Caderno de Erros**:
Coleção dinâmica de questões erradas pelo estudante agrupadas por subtema clínico para remediação diagnóstica focal.
_Evitar_: Lista de erros, histórico de falhas.

---

## Sincronização Local-First e Identidade

**Pacote Offline**:
Snapshot autocontido e imutável de questões, gabaritos e explicações de professores pré-carregado no armazenamento local para resolução em áreas sem conectividade.
_Evitar_: Download temporário, cache de navegador, dump.

**Fila de Sincronização Transacional**:
Sequência ordenada e durável de mutações locais geradas offline (tentativas, revisões, favoritos) aguardando envio idempotente e atômico ao backend.
_Evitar_: Buffer de requisições, outbox genérico, retry loop.

**Sessão Visitante (Modo Convidado)**:
Identidade efêmera persistida localmente via identificador único sanitizado que permite experimentação integral do estudante sem autenticação prévia.
_Evitar_: Usuário anônimo, sessão nula, bypass de autenticação.
