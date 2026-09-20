# Revisão 04 — Progresso teórico visível no planner

Você fará uma segunda revisão crítica da tarefa anterior do Gemini no MedQuest. Releia o prompt de implementação correspondente e `docs/gemini/entregas/04.md`. Não presuma que o resumo da implementação é correto: inspecione o código e execute verificações independentes.

Preserve as alterações de outras tarefas. Não publique, não faça commits ou reset, não exponha segredos e não acesse o banco remoto. Use bancos e serviços temporários. Consulte AGENTS.md e documentação local aplicável. Revise escopo, contrato, isolamento de usuário, erros, regressões e testes, além de caminho feliz.

Corrija os problemas comprovados dentro do escopo, acrescente testes de regressão pertinentes e rode-os novamente. Não reescreva arquitetura por preferência. Se houver decisão de produto ambígua ou bloqueio real, descreva-o sem inventar requisitos. Não declare ausência de bugs como garantia.

Foco desta revisão:
Trace o dado desde a gravação na central até a leitura no planner. Confira se o fluxo real de produção e os tipos retornam o novo campo, se existe apenas uma leitura em lote e se os testes detectariam um usuário vendo o progresso de outro. Alterne teoria concluída/pendente e navegue de volta: não aceite dados antigos. Confira que a meta semanal permanece independente e que o ICS continua válido. Verifique se o indicador está acessível e não depende apenas de cor.

Entrega: resumo de até 15 linhas com achados por gravidade, correções, comandos e resultados realmente executados, limitações e pontos para auditoria pelo Codex. Salve também `docs/gemini/entregas/04-revisao.md`. A revisão deve ser executada separadamente da implementação; preferencialmente em uma nova conversa com acesso ao mesmo workspace. Não inicie o próximo prompt automaticamente.
