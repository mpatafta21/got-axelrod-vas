from typing import Dict, Tuple

Potez = str  # "S" ili "I"

DEFAULT_MATRICA_ISPLATE = {
    ("S", "S"): (3, 3),
    ("I", "S"): (5, 0),
    ("S", "I"): (0, 5),
    ("I", "I"): (1, 1),
}


def izracunaj_isplatu(
    matrica_isplate: Dict[Tuple[Potez, Potez], Tuple[int, int]],
    potez_a: Potez,
    potez_b: Potez,
) -> Tuple[int, int]:
    return matrica_isplate[(potez_a, potez_b)]
