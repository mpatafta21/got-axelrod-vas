import random
from typing import List

Potez = str  # "S" = suradnja, "I" = izdaja

def uvijek_suradjuj(_moja_povijest: List[Potez], _povijest_protivnika: List[Potez]) -> Potez:
    return "S"

def uvijek_izdaj(_moja_povijest: List[Potez], _povijest_protivnika: List[Potez]) -> Potez:
    return "I"

def tit_for_tat(_moja_povijest: List[Potez], povijest_protivnika: List[Potez]) -> Potez:
    # Prvi potez: suradnja; dalje: kopiraj zadnji potez protivnika
    return "S" if not povijest_protivnika else povijest_protivnika[-1]

def slucajna_strategija(_moja_povijest: List[Potez], _povijest_protivnika: List[Potez], vjerojatnost_suradnje: float = 0.5) -> Potez:
    return "S" if random.random() < vjerojatnost_suradnje else "I"
