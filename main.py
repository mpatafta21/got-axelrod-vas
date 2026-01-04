from agent import KucaAgent
from engine import Simulacija
import strategije as st

# Matrica isplate (klasična iterirana dilema zatvorenika)
# (S,S)=3, (I,S)=5/0, (S,I)=0/5, (I,I)=1
MATRICA_ISPLATE = {
    ("S", "S"): (3, 3),
    ("I", "S"): (5, 0),
    ("S", "I"): (0, 5),
    ("I", "I"): (1, 1),
}

def main() -> None:
    agenti = [
        KucaAgent("Stark", "TFT", st.tit_for_tat),
        KucaAgent("Mormont", "Uvijek surađuj", st.uvijek_suradjuj),
        KucaAgent("Lannister", "Uvijek izdaj", st.uvijek_izdaj),
        KucaAgent("Martell", "Slučajno (60% S)", lambda moja, protiv: st.slucajna_strategija(moja, protiv, 0.6)),
    ]

    simulacija = Simulacija(MATRICA_ISPLATE)

    broj_sezona = 10
    for _ in range(broj_sezona):
        simulacija.turnir_svatko_sa_svakim(agenti)

    print("=== Poredak (Leaderboard) ===")
    for a in sorted(agenti, key=lambda x: x.bodovi, reverse=True):
        print(f"{a.naziv:10s} | {a.naziv_strategije:18s} | bodovi={a.bodovi}")

if __name__ == "__main__":
    main()
