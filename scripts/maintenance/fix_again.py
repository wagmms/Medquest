import sqlite3

db_path = 'app/backend/medquest.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

explanation = """**Gabarito**: Letra C

**Pulo do Gato**:
A grande pegadinha desta questão está na primeira assertiva sobre ácido valproico, um tema que se repete com frequência nas provas. Diferentemente da maioria dos anticonvulsivantes que aparecem nas alternativas de contracepção, o **ácido valproico é a exceção** que confirma a regra: ele não induz enzimas hepáticas e não compromete a eficácia do anticoncepcional. Esse padrão de cobrança aparece tanto em questões sobre contraindicações quanto em casos clínicos práticos, geralmente tentando confundir com carbamazepina , fenitoína ou topiramato, que de fato reduzem os níveis hormonais.

O *metronidazol* representa outra armadilha clássica. Embora seja um antibiótico de uso frequente e muitos candidatos associem antibióticos à redução de eficácia contraceptiva, apenas a rifampicina e rifabutina realmente interferem. Esse mito sobre metronidazol aparece em questões que mesclam verdades e falácias, testando se conseguimos separar interações reais de crenças populares. A confusão provavelmente vem da prática de orientar preservativo durante tratamentos, mas por prevenção de ISTs, não por falha contraceptiva.

Quando as provas abordam *topiramato*, o enfoque costuma ser duplo: tanto a redução da eficácia do anticoncepcional quanto a necessidade de ajustar para doses maiores de *etinilestradiol* nessas pacientes. O conceito de **anticoncepcionais de baixa dosagem** também merece atenção, pois diferencia as formulações modernas das antigas, e as bancas exploram isso ao questionar perfil de segurança cardiovascular em mulheres sem fatores de risco.

**Raciocínio Clínico**:
Interações medicamentosas com anticoncepcionais são um tema recorrente nas provas e extremamente relevante na prática clínica. Esta questão testa nosso conhecimento sobre quatro situações diferentes: dois anticonvulsivantes (ácido valproico e topiramato), um antibiótico (metronidazol) e o perfil de segurança cardiovascular dos anticoncepcionais de baixa dosagem. Vamos analisar cada assertiva com cuidado, porque há pegadinhas importantes aqui.

Para entendermos as interações medicamentosas com anticoncepcionais, precisamos primeiro conhecer o conceito de **indução enzimática hepática**. Alguns medicamentos aumentam a atividade das enzimas do citocromo P450 no fígado, acelerando o metabolismo dos hormônios anticoncepcionais e reduzindo suas concentrações sanguíneas. Isso pode comprometer a eficácia contraceptiva.

Os principais indutores enzimáticos que reduzem a eficácia dos anticoncepcionais são:

rifampicina
rifabutina
fenitoína
carbamazepina
fenobarbital
primidona
oxcarbazepina
topiramato

Esses medicamentos aceleram o metabolismo do *etinilestradiol* (e em alguns casos também dos progestagênios), diminuindo suas concentrações plasmáticas.

Agora vamos analisar cada assertiva individualmente para construir nossa resposta correta.

**Por que a Letra C é a Correta?**:
Esta é nossa resposta correta: V - V - F - V. Vamos confirmar cada ponto: (1) VERDADEIRO - ácido valproico não altera a concentração do anticoncepcional, sendo a exceção entre os anticonvulsivantes; (2) VERDADEIRO - topiramato diminui sim a concentração sanguínea do anticoncepcional por indução enzimática; (3) FALSO - metronidazol não interfere com anticoncepcionais orais combinados, não sendo necessário orientar uso adicional de preservativo por este motivo (embora o preservativo sempre deva ser incentivado para prevenção de ISTs); (4) VERDADEIRO - **anticoncepcionais orais de baixa dosagem** realmente apresentam baixo risco absoluto de doença cardiovascular em mulheres jovens e saudáveis, sem fatores de risco adicionais. Esta sequência está perfeita!

**Análise dos Distratores**:
- **Letra A**: Esta alternativa sugere F - V - V - V. Vamos verificar: ela considera FALSA a primeira assertiva (sobre ácido valproico). Mas aqui está um ponto crucial que cai em muitas provas: o **ácido valproico é a grande EXCEÇÃO** entre os anticonvulsivantes! 🚨 Diferentemente da maioria dos antiepilépticos, o ácido valproico não é indutor enzimático e não reduz a concentração dos anticoncepcionais orais. Portanto, a primeira assertiva é VERDADEIRA, não falsa. Além disso, esta alternativa considera verdadeira a terceira assertiva sobre *metronidazol*, o que também está incorreto - metronidazol não interfere com anticoncepcionais. Por esses dois erros, eliminamos esta opção.
- **Letra B**: Esta alternativa traz V - F - V - F. Ela acerta ao considerar verdadeira a primeira assertiva (ácido valproico não interfere), mas erra ao considerar FALSA a segunda (sobre topiramato). O **topiramato SIM é um indutor enzimático** e reduz os níveis de *etinilestradiol*, diminuindo a eficácia contraceptiva. Pacientes usando topiramato precisam usar anticoncepcionais com doses mais altas de estrogênio (pelo menos 30-35 mcg de etinilestradiol) ou considerar métodos não hormonais. A alternativa também erra ao considerar verdadeira a terceira (metronidazol) e falsa a quarta assertiva. Portanto, não é nossa resposta.
- **Letra D**: Esta alternativa considera todas as assertivas falsas (F - F - F - F), o que claramente não procede. Sabemos que o ácido valproico não interfere, que o topiramato interfere sim, e que ACO de baixa dosagem tem baixo risco cardiovascular em mulheres saudáveis. Seria um erro grave marcar esta opção. 🚨 **Cuidado com alternativas extremas** que negam tudo - raramente são corretas em questões de V/F sobre farmacologia."""

c.execute("UPDATE explanations SET explanation_text = ? WHERE question_id=48718", (explanation,))
conn.commit()
conn.close()
