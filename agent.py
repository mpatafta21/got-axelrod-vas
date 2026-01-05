from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple
import random


Potez = str  # "S" ili "I"
FunkcijaStrategije = Callable[[List[Potez], List[Potez]], Potez]

@dataclass
class KucaAgent:
    naziv: str
    naziv_strategije: str
    strategija: FunkcijaStrategije
    bodovi: int = 0

    # povijest po protivniku: (moja_povijest, protivnikova_povijest)
    povijest: Dict[str, Tuple[List[Potez], List[Potez]]] = field(default_factory=dict)

    # --- Learning logika ---
    je_ucenje: bool = False
    epsilon: float = 0.10  # 10% istraživanje

    statistika_ucenja: Dict[str, Dict[Potez, Dict[str, float]]] = field(default_factory=dict)

    def odaberi_potez(self, naziv_protivnika: str) -> Potez:
        moja, protivnikova = self.povijest.get(naziv_protivnika, ([], []))

        if self.je_ucenje:
            return self._odaberi_potez_ucenje(naziv_protivnika)
        
        return self.strategija(moja, protivnikova)

    def zabiljezi(self, naziv_protivnika: str, moj_potez: Potez, potez_protivnika: Potez) -> None:
        moja, protivnikova = self.povijest.get(naziv_protivnika, ([], []))
        moja.append(moj_potez)
        protivnikova.append(potez_protivnika)
        self.povijest[naziv_protivnika] = (moja, protivnikova)

    # Learning logika
    # ----------------------------
    def _inicijaliziraj_statistiku(self, protivnik: str) -> None:
        if protivnik not in self.statistika_ucenja:
            self.statistika_ucenja[protivnik] = {
                "S": {"n": 0.0, "avg": 0.0},
                "I": {"n": 0.0, "avg": 0.0},
            }

    def _odaberi_potez_ucenje(self, protivnik: str) -> Potez:
        self._inicijaliziraj_statistiku(protivnik)

        # 1) istrazivanje (random)
        if random.random() < self.epsilon:
            return random.choice(["S", "I"])

        # 2) odaberi potez s većom prosječnom nagradom
        s = self.statistika_ucenja[protivnik]["S"]
        i = self.statistika_ucenja[protivnik]["I"]

        # Ako nešto još nije isprobano, prvo to isprobaj
        if s["n"] == 0:
            return "S"
        if i["n"] == 0:
            return "I"

        return "S" if s["avg"] >= i["avg"] else "I"

    def azuriraj_ucenje(self, protivnik: str, moj_potez: Potez, nagrada: float) -> None:
        """
        Ažurira prosjecnu nagradu za odabrani potez (S/I) protiv određenog protivnika.
        nagrada = bodovi dobiveni u tom susretu (za taj potez).
        """
        if not self.je_ucenje:
            return

        self._inicijaliziraj_statistiku(protivnik)
        zapis = self.statistika_ucenja[protivnik][moj_potez]

        n_staro = zapis["n"]
        avg_staro = zapis["avg"]

        n_novo = n_staro + 1.0
        avg_novo = avg_staro + (nagrada - avg_staro) / n_novo

        zapis["n"] = n_novo
        zapis["avg"] = avg_novo