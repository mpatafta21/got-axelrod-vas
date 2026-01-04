from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

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

    def odaberi_potez(self, naziv_protivnika: str) -> Potez:
        moja, protivnikova = self.povijest.get(naziv_protivnika, ([], []))
        return self.strategija(moja, protivnikova)

    def zabiljezi(self, naziv_protivnika: str, moj_potez: Potez, potez_protivnika: Potez) -> None:
        moja, protivnikova = self.povijest.get(naziv_protivnika, ([], []))
        moja.append(moj_potez)
        protivnikova.append(potez_protivnika)
        self.povijest[naziv_protivnika] = (moja, protivnikova)
