# Revisão 02 — Orçamento diário de questões

Você fará uma segunda revisão crítica da tarefa anterior do Gemini no MedQuest. Releia o prompt de implementação correspondente e `docs/gemini/entregas/02.md`. Não presuma que o resumo da implementação é correto: inspecione o código e execute verificações independentes.

Preserve as alterações de outras tarefas. Não publique, não faça commits ou reset, não exponha segredos e não acesse o banco remoto. Use bancos e serviços temporários. Consulte AGENTS.md e documentação local aplicável. Revise escopo, contrato, isolamento de usuário, erros, regressões e testes, além de caminho feliz.

Corrija os problemas comprovados dentro do escopo, acrescente testes de regressão pertinentes e rode-os novamente. Não reescreva arquitetura por preferência. Se houver decisão de produto ambígua ou bloqueio real, descreva-o sem inventar requisitos. Não declare ausência de bugs como garantia.

Foco desta revisão:
Confira a aritmética nos três casos definidos e procure todos os usos de `questions_today`, `reviews_due` e da meta diária. Verifique se o botão de iniciar sessão usa o orçamento exibido, se o excedente continua visível e se os rótulos distinguem meta configurada e sugestão. Confirme ausência de escrita em datas de revisão ou histórico. Teste o contrato anterior dos demais campos e dados de usuários distintos. Considere que a fila pode ter menos questões disponíveis que o limite: não prometa que a sessão sempre terá N itens.

Entrega: resumo de até 15 linhas com achados por gravidade, correções, comandos e resultados realmente executados, limitações e pontos para auditoria pelo Codex. Salve também `docs/gemini/entregas/02-revisao.md`. A revisão deve ser executada separadamente da implementação; preferencialmente em uma nova conversa com acesso ao mesmo workspace. Não inicie o próximo prompt automaticamente.
