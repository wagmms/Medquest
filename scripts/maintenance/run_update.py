import sys
sys.path.insert(0, 'app/backend')

from api import create_app
from api.db import get_db

app = create_app()

new_explanation = """**Gabarito**: Letra A

**Pulo do Gato**: O enunciado tenta te induzir ao diagnóstico de **adenite mesentérica** (pródromo viral com tosse e dor de garganta). Porém, a presença de **Blumberg positivo** (peritonite localizada) acende o alerta máximo para **apendicite aguda**. Na dúvida entre diagnóstico cirúrgico (apendicite) e clínico (adenite) em crianças, o exame inicial de escolha é o **ultrassom de abdome** para evitar radiação.

**Raciocínio Clínico**: A questão traz um cenário clássico na pediatria: criança com dor em FID após um quadro de infecção das vias aéreas superiores (IVAS). O grande diagnóstico diferencial aqui é entre **apendicite aguda** e **adenite mesentérica**. A adenite mesentérica é classicamente desencadeada por um pródromo viral, mas dificilmente apresenta peritonite focal franca. Como o exame físico revela descompressão brusca dolorosa (sinal de Blumberg), a suspeita de apendicite aguda torna-se prioritária. Na apendicite infantil, o quadro viral pode inclusive ser o gatilho (causando hiperplasia linfoide apendicular), e a constipação citada no enunciado favorece a formação de fecalito - ambos causam a obstrução da luz do apêndice. Para confirmar o diagnóstico e diferenciar essas patologias poupando a criança da radiação da tomografia, a conduta correta é solicitar a ultrassonografia de abdome.

**Por que a Letra A é a Correta?**: A ultrassonografia é o método de escolha inicial em pediatria para o abdome agudo inflamatório. Critérios diagnósticos: diâmetro apendicial >6mm, hiperemia ao Doppler, ausência de compressibilidade, líquido periapendicial. Sensibilidade 85-95% quando realizada por radiologista experiente. Permite avaliação simultânea de estruturas anexas (como linfonodos mesentéricos, confirmando a adenite se o apêndice estiver normal), sem exposição à radiação ionizante — essencial em criança. Se o ultrassom for inconclusivo, a TC de abdome com protocolo pediátrico é a segunda opção.

**Análise dos Distratores**:
- **Raio-X de abdome (não listado, mas frequente em prova)**: Indicado para exclusão de perfuração (pneumoperitônio) ou outros diagnósticos; baixa sensibilidade específica para apendicite.
- **TC de abdome e pelve**: Reservado para casos com diagnóstico incerto pós-ultrassom ou suspeita de complicação; expõe a criança à radiação ionizante desnecessariamente como exame inicial.
- **Ressonância magnética**: Sem indicação na urgência rotineira; tempo de realização inviável no pronto-socorro.
- **Exames laboratoriais isolados (hemograma, PCR)**: Complementam, mas não confirmam o diagnóstico nem substituem o exame de imagem necessário para a conduta cirúrgica."""

with app.app_context():
    db = get_db()
    db.execute("UPDATE explanations SET explanation_text = ? WHERE question_id = 13283", (new_explanation,))
    db.commit()
    print("Database update successful using app_context!")
