from typing import Dict, List, Tuple
from agent import KucaAgent

Potez = str  # "S" ili "I"

class Simulacija:
    def __init__(self, matrica_isplate: Dict[Tuple[Potez, Potez], Tuple[int, int]]):
        self.matrica_isplate = matrica_isplate

    def odigraj_susret(self, a: KucaAgent, b: KucaAgent) -> Tuple[int, int, Potez, Potez]:
        potez_a = a.odaberi_potez(b.naziv)
        potez_b = b.odaberi_potez(a.naziv)

        bodovi_a, bodovi_b = self.matrica_isplate[(potez_a, potez_b)]
        a.bodovi += bodovi_a
        b.bodovi += bodovi_b

        a.azuriraj_ucenje(b.naziv, potez_a, bodovi_a)
        b.azuriraj_ucenje(a.naziv, potez_b, bodovi_b)

        a.zabiljezi(b.naziv, potez_a, potez_b)
        b.zabiljezi(a.naziv, potez_b, potez_a)

        broj_suradnji = (1 if potez_a == "S" else 0) + (1 if potez_b == "S" else 0)
        return broj_suradnji, 2, potez_a, potez_b

    def turnir_svatko_sa_svakim(self, agenti: List[KucaAgent], track_agent_name: str | None = None) -> Dict[str, int]:

        ukupno_suradnji = 0
        ukupno_poteza = 0
        suradnje_agenta = 0
        poteza_agenta = 0

        for i in range(len(agenti)):
            for j in range(i + 1, len(agenti)):
                s, t, potez_a, potez_b = self.odigraj_susret(agenti[i], agenti[j])
                ukupno_suradnji += s
                ukupno_poteza += t
                if track_agent_name is not None:
                    if agenti[i].naziv == track_agent_name:
                        poteza_agenta += 1
                        suradnje_agenta += 1 if potez_a == "S" else 0
                    if agenti[j].naziv == track_agent_name:
                        poteza_agenta += 1
                        suradnje_agenta += 1 if potez_b == "S" else 0
                
        rezultat = {"suradnje": ukupno_suradnji, "poteza": ukupno_poteza}
        if track_agent_name is not None:
            rezultat["suradnje_agenta"] = suradnje_agenta
            rezultat["poteza_agenta"] = poteza_agenta
        return rezultat
    
    
    def odigraj_sezonu_sa_dogadjajima(self, agenti):
        """
        Odradi jednu sezonu (svatko sa svakim) i vrati listu događaja:
        (kucaA, kucaB, potezA, potezB, bodA, bodB)
        """
        dogadjaji = []
        for i in range(len(agenti)):
            for j in range(i + 1, len(agenti)):
                a = agenti[i]
                b = agenti[j]

                potez_a = a.odaberi_potez(b.naziv)
                potez_b = b.odaberi_potez(a.naziv)

                bodovi_a, bodovi_b = self.matrica_isplate[(potez_a, potez_b)]
                a.bodovi += bodovi_a
                b.bodovi += bodovi_b

                a.zabiljezi(b.naziv, potez_a, potez_b)
                b.zabiljezi(a.naziv, potez_b, potez_a)

                # update learning (ako je agent learning)
                a.azuriraj_ucenje(b.naziv, potez_a, bodovi_a)
                b.azuriraj_ucenje(a.naziv, potez_b, bodovi_b)

                dogadjaji.append((a.naziv, b.naziv, potez_a, potez_b, bodovi_a, bodovi_b))
        return dogadjaji

