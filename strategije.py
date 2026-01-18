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

def sumnjivi_tit_for_tat(moja_povijest: List[Potez], povijest_protivnika: List[Potez]) -> Potez:
    # Prvi potez izdaja, dalje kopira protivnika
    if not povijest_protivnika:
        return "I"
    return povijest_protivnika[-1]

def tit_for_two_tats(_moja_povijest: List[Potez], povijest_protivnika: List[Potez]) -> Potez:
    # Suradnja osim ako su zadnja 2 poteza protivnika bila izdaja
    if len(povijest_protivnika) >= 2 and povijest_protivnika[-1] == "I" and povijest_protivnika[-2] == "I":
        return "I"
    return "S"

def grim_trigger(_moja_povijest: List[Potez], povijest_protivnika: List[Potez]) -> Potez:
    # Suradnja dok protivnik jednom ne izda; nakon toga uvijek izdaja
    if "I" in povijest_protivnika:
        return "I"
    return "S"

def joss(moja_povijest: List[Potez], povijest_protivnika: List[Potez], p_izdaje_nakon_suradnje: float = 0.10) -> Potez:
    # Kao TFT, ali s malom šansom izdaje čak i nakon što bi surađivao
    # (Axelrodov JOSS: 10% "zločestoće")
    tft_potez = "S" if not povijest_protivnika else povijest_protivnika[-1]
    if tft_potez == "S" and random.random() < p_izdaje_nakon_suradnje:
        return "I"
    return tft_potez

def win_stay_lose_shift(moja_povijest: List[Potez], povijest_protivnika: List[Potez]) -> Potez:
    # WSLS / Pavlov:
    # ako je prošli ishod bio "dobar" -> ponovi potez
    # inače -> promijeni potez
    if not moja_povijest:
        return "S"  # start s kooperacijom

    moj_zadnji = moja_povijest[-1]
    protivnikov_zadnji = povijest_protivnika[-1] if povijest_protivnika else "S"

    # ali u PD-u tipično WSLS: ponovi ako je dobio visoku nagradu.
    # - ponovi potez ako je ishod bio (S,S) ili (I,S)
    # - promijeni u ostalim slučajevima
    if (moj_zadnji, protivnikov_zadnji) in [("S", "S"), ("I", "S")]:
        return moj_zadnji
    return "I" if moj_zadnji == "S" else "S"