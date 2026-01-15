# ui_stats.py
# Helpers for stats calculation, export, and overlay rendering.

import csv
import os
import statistics
from typing import List, Dict, Tuple

import pygame


def init_stats(agenti):
    agent_stats = {a.naziv: {"suradnje": 0, "izdaje": 0, "poteza": 0} for a in agenti}
    global_pct_by_season: List[float] = []
    learning_pct_by_season: List[float] = []
    learning_rank_by_season: List[int] = []
    learning_agent = next((a.naziv for a in agenti if a.je_ucenje), "")
    pair_stats: Dict[Tuple[str, str], Dict[str, int]] = {}
    rank_stats = {
        "top3": {a.naziv: 0 for a in agenti},
        "last": {a.naziv: 0 for a in agenti},
    }
    return agent_stats, global_pct_by_season, learning_pct_by_season, learning_rank_by_season, learning_agent, pair_stats, rank_stats


def update_stats_for_season(
    dog,
    agent_stats,
    global_pct_by_season,
    learning_pct_by_season,
    learning_rank_by_season,
    learning_agent,
    pair_stats,
    rank_stats,
    agenti,
):
    season_suradnje = 0
    season_poteza = 0
    season_learning_suradnje = 0
    season_learning_poteza = 0

    for (a, b, pa, pb, _ba, _bb) in dog:
        season_suradnje += (1 if pa == "S" else 0) + (1 if pb == "S" else 0)
        season_poteza += 2

        agent_stats[a]["poteza"] += 1
        agent_stats[b]["poteza"] += 1
        if pa == "S":
            agent_stats[a]["suradnje"] += 1
        else:
            agent_stats[a]["izdaje"] += 1
        if pb == "S":
            agent_stats[b]["suradnje"] += 1
        else:
            agent_stats[b]["izdaje"] += 1

        if learning_agent:
            if a == learning_agent:
                season_learning_poteza += 1
                if pa == "S":
                    season_learning_suradnje += 1
            if b == learning_agent:
                season_learning_poteza += 1
                if pb == "S":
                    season_learning_suradnje += 1

        key = tuple(sorted((a, b)))
        if key not in pair_stats:
            pair_stats[key] = {"ss": 0, "si": 0, "ii": 0, "total": 0}
        if pa == "S" and pb == "S":
            pair_stats[key]["ss"] += 1
        elif pa == "I" and pb == "I":
            pair_stats[key]["ii"] += 1
        else:
            pair_stats[key]["si"] += 1
        pair_stats[key]["total"] += 1

    poredak = sorted(agenti, key=lambda x: x.bodovi, reverse=True)
    for a in poredak[:3]:
        rank_stats["top3"][a.naziv] += 1
    if poredak:
        rank_stats["last"][poredak[-1].naziv] += 1
    if learning_agent:
        for idx, a in enumerate(poredak, start=1):
            if a.naziv == learning_agent:
                learning_rank_by_season.append(idx)
                break

    last_season_pct = 100.0 * season_suradnje / season_poteza if season_poteza > 0 else 0.0
    global_pct_by_season.append(last_season_pct)
    if season_learning_poteza > 0:
        learning_pct_by_season.append(100.0 * season_learning_suradnje / season_learning_poteza)
    else:
        learning_pct_by_season.append(0.0)

    return season_suradnje, season_poteza, last_season_pct


def build_stats(agenti, agent_stats, sezona):
    agent_rows = []
    for a in agenti:
        moves = agent_stats[a.naziv]["poteza"]
        coop = agent_stats[a.naziv]["suradnje"]
        defect = agent_stats[a.naziv]["izdaje"]
        coop_pct = 100.0 * coop / moves if moves > 0 else 0.0
        defect_pct = 100.0 * defect / moves if moves > 0 else 0.0
        avg_season = a.bodovi / sezona if sezona > 0 else 0.0
        agent_rows.append({
            "kuca": a.naziv,
            "strategija": a.naziv_strategije,
            "bodovi": a.bodovi,
            "prosjek": avg_season,
            "suradnja_pct": coop_pct,
            "izdaja_pct": defect_pct,
        })

    strategije = {}
    for a in agenti:
        s = a.naziv_strategije
        if s not in strategije:
            strategije[s] = {
                "bodovi": [],
                "suradnje": 0,
                "poteza": 0,
            }
        strategije[s]["bodovi"].append(a.bodovi)
        strategije[s]["suradnje"] += agent_stats[a.naziv]["suradnje"]
        strategije[s]["poteza"] += agent_stats[a.naziv]["poteza"]

    strategija_rows = []
    for s, data in strategije.items():
        bodovi = data["bodovi"]
        avg_bodovi = sum(bodovi) / len(bodovi) if bodovi else 0.0
        min_bodovi = min(bodovi) if bodovi else 0
        max_bodovi = max(bodovi) if bodovi else 0
        std_bodovi = statistics.pstdev(bodovi) if len(bodovi) > 1 else 0.0
        coop_pct = 100.0 * data["suradnje"] / data["poteza"] if data["poteza"] > 0 else 0.0
        strategija_rows.append({
            "strategija": s,
            "prosjek": avg_bodovi,
            "min": min_bodovi,
            "max": max_bodovi,
            "std": std_bodovi,
            "suradnja_pct": coop_pct,
        })

    agent_rows.sort(key=lambda x: x["bodovi"], reverse=True)
    strategija_rows.sort(key=lambda x: x["prosjek"], reverse=True)
    return agent_rows, strategija_rows


def build_pair_stats(pair_stats):
    rows = []
    for (a, b), data in sorted(pair_stats.items()):
        total = data["total"]
        stabilnost = data["ss"] / total if total > 0 else 0.0
        rows.append({
            "par": f"{a} - {b}",
            "ss": data["ss"],
            "si": data["si"],
            "ii": data["ii"],
            "total": total,
            "stabilnost": stabilnost,
        })
    return rows


def build_learning_stats(agenti, learning_agent):
    if not learning_agent:
        return []
    agent = next((a for a in agenti if a.naziv == learning_agent), None)
    if agent is None:
        return []
    rows = []
    protivnici = [(a.naziv, a.naziv_strategije) for a in agenti if a.naziv != learning_agent]
    for p, strategija_naziv in sorted(protivnici):
        stat = agent.statistika_ucenja.get(p, {})
        s = stat.get("S", {"n": 0.0, "avg": 0.0})
        i = stat.get("I", {"n": 0.0, "avg": 0.0})
        n_s = int(s.get("n", 0.0))
        n_i = int(i.get("n", 0.0))
        avg_s = s.get("avg", 0.0)
        avg_i = i.get("avg", 0.0)
        if n_s == 0 and n_i == 0:
            pref = "-"
        elif n_s == 0:
            pref = "I"
        elif n_i == 0:
            pref = "S"
        else:
            pref = "S" if avg_s >= avg_i else "I"
        pref_s = stat.get("pref_after_s", "-")
        pref_i = stat.get("pref_after_i", "-")
        pct_s = stat.get("pct_s_after_s", 0.0)
        pct_i = stat.get("pct_i_after_i", 0.0)
        rows.append({
            "protivnik": p,
            "strategija": strategija_naziv,
            "avg_s": avg_s,
            "avg_i": avg_i,
            "n": n_s + n_i,
            "pref": pref,
            "pref_s": pref_s,
            "pref_i": pref_i,
            "pct_s": pct_s,
            "pct_i": pct_i,
        })
    return rows


def build_rank_stats(rank_stats):
    rows = []
    for kuca in sorted(rank_stats["top3"].keys()):
        rows.append({
            "kuca": kuca,
            "top3": rank_stats["top3"][kuca],
            "last": rank_stats["last"][kuca],
        })
    return rows


def export_stats(
    agenti,
    agent_stats,
    sezona,
    global_pct_by_season,
    learning_pct_by_season,
    learning_rank_by_season,
    learning_agent,
    pair_stats,
    rank_stats,
):
    os.makedirs("ui_data", exist_ok=True)
    agent_rows, strategija_rows = build_stats(agenti, agent_stats, sezona)
    pair_rows = build_pair_stats(pair_stats)
    learning_rows = build_learning_stats(agenti, learning_agent)
    rank_rows = build_rank_stats(rank_stats)

    with open(os.path.join("ui_data", "agent_stats.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kuca", "strategija", "bodovi", "prosjek_po_sezoni", "postotak_suradnje", "postotak_izdaje"])
        for r in agent_rows:
            w.writerow([
                r["kuca"],
                r["strategija"],
                r["bodovi"],
                f"{r['prosjek']:.2f}",
                f"{r['suradnja_pct']:.2f}",
                f"{r['izdaja_pct']:.2f}",
            ])

    with open(os.path.join("ui_data", "strategija_stats.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategija", "prosjecni_bodovi", "min", "max", "std_dev", "prosjek_suradnje_pct"])
        for r in strategija_rows:
            w.writerow([
                r["strategija"],
                f"{r['prosjek']:.2f}",
                r["min"],
                r["max"],
                f"{r['std']:.2f}",
                f"{r['suradnja_pct']:.2f}",
            ])

    with open(os.path.join("ui_data", "suradnja_po_sezoni.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sezona", "global_suradnja_pct", "learning_suradnja_pct"])
        for i, g in enumerate(global_pct_by_season, start=1):
            l = learning_pct_by_season[i - 1] if i - 1 < len(learning_pct_by_season) else 0.0
            w.writerow([i, f"{g:.2f}", f"{l:.2f}"])

    if learning_agent:
        with open(os.path.join("ui_data", "targaryen_pozicija_po_sezoni.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["sezona", "pozicija"])
            for i, r in enumerate(learning_rank_by_season, start=1):
                w.writerow([i, r])

    with open(os.path.join("ui_data", "mrezna_statistika.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["par", "ss", "si", "ii", "ukupno", "stabilnost"])
        for r in pair_rows:
            w.writerow([r["par"], r["ss"], r["si"], r["ii"], r["total"], f"{r['stabilnost']:.3f}"])

    with open(os.path.join("ui_data", "learning_agent.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["protivnik", "strategija", "avg_S", "avg_I", "pokusaji", "preferirani_potez", "pref_after_S", "pref_after_I", "pct_S_after_S", "pct_I_after_I"])
        for r in learning_rows:
            w.writerow([r["protivnik"], r["strategija"], f"{r['avg_s']:.2f}", f"{r['avg_i']:.2f}", r["n"], r["pref"], r["pref_s"], r["pref_i"], f"{r['pct_s']:.1f}", f"{r['pct_i']:.1f}"])

    with open(os.path.join("ui_data", "stabilnost_poretka.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kuca", "top3_sezone", "zadnja_sezone"])
        for r in rank_rows:
            w.writerow([r["kuca"], r["top3"], r["last"]])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sez = list(range(1, len(global_pct_by_season) + 1))
    plt.figure(figsize=(8, 4))
    plt.plot(sez, global_pct_by_season, label="Global % suradnje")
    if learning_agent:
        plt.plot(sez, learning_pct_by_season, label=f"{learning_agent} % suradnje")
    plt.xlabel("Sezona")
    plt.ylabel("% suradnje")
    plt.title("Suradnja po sezoni")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join("ui_data", "suradnja_po_sezoni.png"))
    plt.close()

    if learning_agent and learning_rank_by_season:
        plt.figure(figsize=(8, 4))
        plt.plot(sez, learning_rank_by_season, label=f"{learning_agent} pozicija")
        plt.xlabel("Sezona")
        plt.ylabel("Pozicija (1=prvi)")
        plt.title("Pozicija learning agenta po sezoni")
        plt.gca().invert_yaxis()
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join("ui_data", "targaryen_pozicija_po_sezoni.png"))
        plt.close()


def draw_stats_overlay(
    screen,
    W,
    H,
    font_title,
    font_small,
    font_mono,
    boja_tekst,
    boja_subt,
    agent_rows,
    strategija_rows,
    pair_rows,
    learning_rows,
    rank_rows,
    tab_index,
):
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    box_w = int(W * 0.88)
    box_h = int(H * 0.85)
    box_x = (W - box_w) // 2
    box_y = (H - box_h) // 2
    pygame.draw.rect(screen, (20, 20, 28), (box_x, box_y, box_w, box_h))
    pygame.draw.rect(screen, (90, 90, 90), (box_x, box_y, box_w, box_h), 2)

    tabs = [
        "AGENTI",
        "STRATEGIJE",
        "MREZNA STATISTIKA",
        "LEARNING AGENT",
        "STABILNOST PORETKA",
    ]
    tab_index = max(0, min(tab_index, len(tabs) - 1))

    lines = []
    lines.append("STATISTIKA")
    lines.append("")
    lines.append("")
    lines.append(f"Tab: {tabs[tab_index]}   (←/→ za prebacivanje, E za export)")
    lines.append("")

    if tab_index == 0:
        lines.append("AGENTI")
        lines.append("")
        header_agents = "Kuca       Strategija          Bodovi    Prosjek     %S     %I"
        lines.append(header_agents)
        lines.append("-" * len(header_agents))
        for r in agent_rows:
            strategija = r["strategija"][:16]
            lines.append(f"{r['kuca']:<10} {strategija:<16} {r['bodovi']:>8} {r['prosjek']:>10.1f} {r['suradnja_pct']:>7.1f} {r['izdaja_pct']:>7.1f}")
    elif tab_index == 1:
        lines.append("STRATEGIJE")
        lines.append("")
        header_strat = "Strategija          Avg    Min    Max    Std     %S"
        lines.append(header_strat)
        lines.append("-" * len(header_strat))
        for r in strategija_rows:
            strategija = r["strategija"][:16]
            lines.append(f"{strategija:<16} {r['prosjek']:>6.1f} {r['min']:>6} {r['max']:>6} {r['std']:>7.1f} {r['suradnja_pct']:>7.1f}")
    elif tab_index == 2:
        lines.append("MREZNA STATISTIKA (parovi)")
        lines.append("")
        header_pairs = "Par                     S/S  S/I  I/I  Ukupno  Stabilnost"
        lines.append(header_pairs)
        lines.append("-" * len(header_pairs))
        for r in pair_rows:
            lines.append(f"{r['par']:<23} {r['ss']:>3} {r['si']:>4} {r['ii']:>4} {r['total']:>7} {r['stabilnost']:>10.3f}")
    elif tab_index == 3:
        lines.append("LEARNING AGENT (Targaryen)")
        lines.append("")
        header_learn = "Protivnik        Strategija        Avg S   Avg I  Pokusaji  Pref  PrefS PrefI  %S_S  %I_I"
        lines.append(header_learn)
        lines.append("-" * len(header_learn))
        for r in learning_rows:
            strat = r["strategija"][:16]
            lines.append(f"{r['protivnik']:<14} {strat:<16} {r['avg_s']:>6.2f} {r['avg_i']:>7.2f} {r['n']:>9} {r['pref']:>5} {r['pref_s']:>5} {r['pref_i']:>5} {r['pct_s']:>5.0f}% {r['pct_i']:>5.0f}%")
    else:
        lines.append("STABILNOST PORETKA")
        lines.append("")
        header_rank = "Kuca            Top-3  Zadnja"
        lines.append(header_rank)
        lines.append("-" * len(header_rank))
        for r in rank_rows:
            lines.append(f"{r['kuca']:<14} {r['top3']:>5} {r['last']:>7}")

    pad = 12
    x = box_x + pad
    y = box_y + pad
    line_h = 16
    max_lines = (box_h - pad * 2) // line_h
    for line in lines[:max_lines]:
        if line == "":
            y += line_h
            continue
        if line == "STATISTIKA":
            font_use = font_title
            col = boja_tekst
        elif line in ("AGENTI", "STRATEGIJE") or line.startswith("Graf"):
            font_use = font_small
            col = boja_subt
        else:
            font_use = font_mono
            col = boja_tekst
        surf = font_use.render(line, True, col)
        screen.blit(surf, (x, y))
        y += line_h
