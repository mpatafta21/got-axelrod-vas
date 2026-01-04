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
        # Časne i stabilne kuće
        KucaAgent("Stark",      "TFT",                 st.tit_for_tat),
        KucaAgent("Arryn",      "TFT",                 st.tit_for_tat),
        KucaAgent("Tully",      "TFT-2T",              st.tit_for_two_tats),
        KucaAgent("Mormont",    "Uvijek surađuj",      st.uvijek_suradjuj),

        # Oportunisti / pragmatičari
        KucaAgent("Tyrell",     "WSLS (Pavlov)",       st.win_stay_lose_shift),
        KucaAgent("Martell",    "Slučajno (60% S)",    lambda moja, protiv: st.slucajna_strategija(moja, protiv, 0.60)),
        KucaAgent("Greyjoy",    "Sumnjivi TFT",        st.sumnjivi_tit_for_tat),
        KucaAgent("Frey",       "JOSS (10% I)",        lambda moja, protiv: st.joss(moja, protiv, p_izdaje_nakon_suradnje=0.10)),

        # Agresivne / kaznene kuće
        KucaAgent("Lannister",  "Uvijek izdaja",       st.uvijek_izdaj),
        KucaAgent("Bolton",     "Uvijek izdaja",       st.uvijek_izdaj),
        KucaAgent("Baratheon",  "Grim Trigger",        st.grim_trigger),

        # Adaptabilna kuća
        KucaAgent("Targaryen",  "WSLS (privremeno)",         st.win_stay_lose_shift),

    ]

    simulacija = Simulacija(MATRICA_ISPLATE)

    broj_sezona = 50
    for _ in range(broj_sezona):
        simulacija.turnir_svatko_sa_svakim(agenti)

    print(f"=== Poredak (Leaderboard) | sezone={broj_sezona} | agenti={len(agenti)} ===")
    for a in sorted(agenti, key=lambda x: x.bodovi, reverse=True):
        print(f"{a.naziv:12s} | {a.naziv_strategije:18s} | bodovi={a.bodovi}")

if __name__ == "__main__":
    main()
