from typing import Dict, List, Tuple
from agent import KucaAgent

Potez = str  # "S" ili "I"

class Simulacija:
    def __init__(self, matrica_isplate: Dict[Tuple[Potez, Potez], Tuple[int, int]]):
        self.matrica_isplate = matrica_isplate

    def odigraj_susret(self, a: KucaAgent, b: KucaAgent) -> None:
        potez_a = a.odaberi_potez(b.naziv)
        potez_b = b.odaberi_potez(a.naziv)

        bodovi_a, bodovi_b = self.matrica_isplate[(potez_a, potez_b)]
        a.bodovi += bodovi_a
        b.bodovi += bodovi_b

        a.zabiljezi(b.naziv, potez_a, potez_b)
        b.zabiljezi(a.naziv, potez_b, potez_a)

    def turnir_svatko_sa_svakim(self, agenti: List[KucaAgent]) -> None:
        for i in range(len(agenti)):
            for j in range(i + 1, len(agenti)):
                self.odigraj_susret(agenti[i], agenti[j])
