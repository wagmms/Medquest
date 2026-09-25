from datetime import datetime

# Áreas reconhecidas pelo banco de dados do MedQuest
AREAS_MEDQUEST = [
    "Preventiva", 
    "Ginecologia e Obstetrícia", 
    "Cirurgia", 
    "Medicina Intensiva", 
    "Clínica Médica", 
    "Pediatria", 
    "Especialidades"
]

# Configuração da Turma J - FMRP USP
RODIZIOS_TURMA_J = [
    # 5º Ano Atual (2026) - Atualizado
    {"start": "2026-09-01", "end": "2026-11-26", "area": "Ginecologia e Obstetrícia"}, # GO nas próximas 9 semanas
    {"start": "2026-11-27", "end": "2027-01-25", "area": "Preventiva"}, # Férias (dez-jan)
    
    # 6º Ano (2027) - Calendário Previsto
    {"start": "2027-01-26", "end": "2027-02-22", "area": "Cirurgia"},
    {"start": "2027-02-23", "end": "2027-03-22", "area": "Medicina Intensiva"},
    {"start": "2027-03-23", "end": "2027-04-19", "area": "Ginecologia e Obstetrícia"},
    {"start": "2027-04-20", "end": "2027-05-17", "area": "Especialidades"},
    {"start": "2027-05-18", "end": "2027-06-14", "area": "Preventiva"},
    {"start": "2027-06-15", "end": "2027-08-09", "area": "Clínica Médica"},
    {"start": "2027-08-10", "end": "2027-09-13", "area": "Pediatria"},
    {"start": "2027-09-14", "end": "2027-11-08", "area": "Cirurgia"}
]

def get_area_prioritaria_atual():
    hoje = datetime.now()
    for bloco in RODIZIOS_TURMA_J:
        inicio = datetime.strptime(bloco["start"], "%Y-%m-%d")
        fim = datetime.strptime(bloco["end"], "%Y-%m-%d")
        # Considera que o dia final vai até 23:59:59
        fim = fim.replace(hour=23, minute=59, second=59)
        
        if inicio <= hoje <= fim:
            return bloco["area"]
    return None
