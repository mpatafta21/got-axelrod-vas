from agent import KucaAgent
from engine import Simulacija
import strategije as st

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
        KucaAgent("Targaryen",  "Učenje (ε=0.10)",         st.tit_for_tat, je_ucenje=True, epsilon=0.10),

    ]

    simulacija = Simulacija(MATRICA_ISPLATE)

    broj_sezona = 200
    zapisi_sezona = []

    targaryen_name = "Targaryen"

    for sezona in range(1, broj_sezona + 1):
        statistika = simulacija.turnir_svatko_sa_svakim(agenti, track_agent_name=targaryen_name)
        postotak_suradnje = 100.0 * statistika["suradnje"] / statistika["poteza"]
        postotak_suradnje_targaryen = 0.0
        if statistika.get("poteza_agenta", 0) > 0:
            postotak_suradnje_targaryen = 100.0 * statistika["suradnje_agenta"] / statistika["poteza_agenta"]

        zapisi_sezona.append({
            "sezona": sezona,
            "suradnje": statistika["suradnje"],
            "poteza": statistika["poteza"],
            "postotak_suradnje": postotak_suradnje,
            "targaryen_postotak_suradnje": postotak_suradnje_targaryen
        })

    # --- Leaderboard ---
    poredak = sorted(agenti, key=lambda x: x.bodovi, reverse=True)
    print(f"=== Poredak (Leaderboard) | sezone={broj_sezona} | agenti={len(agenti)} ===")
    for a in poredak:
        print(f"{a.naziv:12s} | {a.naziv_strategije:18s} | bodovi={a.bodovi}")

    # --- DataFrameovi + spremanje ---
    df_sezone = pd.DataFrame(zapisi_sezona)
    df_leaderboard = pd.DataFrame([{
        "kuca": a.naziv,
        "strategija": a.naziv_strategije,
        "bodovi": a.bodovi
    } for a in poredak])

    # Prosjek po strategiji
    df_po_strategiji = (
        df_leaderboard.groupby("strategija", as_index=False)["bodovi"]
        .mean()
        .rename(columns={"bodovi": "prosjek_bodova"})
        .sort_values("prosjek_bodova", ascending=False)
    )

    output_dir = "statistika"
    os.makedirs(output_dir, exist_ok=True)

    # Spremi CSV 
    df_sezone.to_csv(os.path.join(output_dir, "rezultati_sezone.csv"), index=False)
    df_leaderboard.to_csv(os.path.join(output_dir, "leaderboard.csv"), index=False)
    df_po_strategiji.to_csv(os.path.join(output_dir, "prosjek_po_strategiji.csv"), index=False)

    print("\n=== Prosjek bodova po strategiji ===")
    for _, r in df_po_strategiji.iterrows():
        print(f"{r['strategija']:18s} | prosjek={r['prosjek_bodova']:.2f}")

    # --- Graf: % suradnje po sezoni ---
    plt.figure()
    plt.plot(df_sezone["sezona"], df_sezone["postotak_suradnje"])
    plt.title("Postotak suradnje po sezoni")
    plt.xlabel("Sezona")
    plt.ylabel("% suradnje")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "suradnje.png"))

    # --- Graf: % suradnje po sezoni (Targaryen) ---
    plt.figure()
    plt.plot(df_sezone["sezona"], df_sezone["targaryen_postotak_suradnje"])
    plt.title("Postotak suradnje po sezoni (Targaryen)")
    plt.xlabel("Sezona")
    plt.ylabel("% suradnje")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "targaryen_suradnje.png"))

    # --- Histogram: raspodjela % suradnje ---
    plt.figure()
    plt.hist(df_sezone["postotak_suradnje"], bins=10)
    plt.title("Raspodjela postotka suradnje")
    plt.xlabel("% suradnje")
    plt.ylabel("Broj sezona")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "suradnje_hist.png"))

    t = next(a for a in agenti if a.naziv == "Targaryen")
    print("\n=== Targaryen statistika učenja (primjer) ===")
    for protivnik in ["Stark", "Lannister", "Frey"]:
        if protivnik in t.statistika_ucenja:
            print(protivnik, t.statistika_ucenja[protivnik])


if __name__ == "__main__":
    main()
