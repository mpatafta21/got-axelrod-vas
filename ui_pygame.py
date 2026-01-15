
import math
import os
import ui_stats
import sys
import time
import threading
from copy import deepcopy
from queue import Queue, Empty
from dataclasses import dataclass, replace
from typing import Dict, List, Tuple

import pygame

from agent import KucaAgent
from engine import Simulacija
import strategije as st
from spade_orchestrator import SpadeSession, KUCe as SPADE_KUCE

Potez = str  # "S" ili "I"

MATRICA_ISPLATE = {
    ("S", "S"): (3, 3),
    ("I", "S"): (5, 0),
    ("S", "I"): (0, 5),
    ("I", "I"): (1, 1),
}

# ---- Vizualna pravila
BOJA_POZADINA = (18, 18, 24)
BOJA_PANEL = (28, 28, 36)
BOJA_TEKST = (230, 230, 230)
BOJA_SUBT = (170, 170, 170)

BOJA_SS = (70, 200, 120)   # savez (S,S)
BOJA_IZDAJA = (220, 90, 90) # izdaja (S/I ili I/S)
BOJA_II = (120, 120, 120)  # konflikt (I,I)

BOJA_CVOR = (80, 140, 220)
BOJA_CVOR_AKT = (255, 210, 90)
BOJA_CVOR_UCENJE = (240, 200, 80)

RADIUS_CVOR = 18
USE_SPADE = True
ERA_LEN = 10

HOUSE_DEFS = [
    {"naziv": "Stark", "strategija_id": "tit_for_tat", "strategija_naziv": "TFT", "fn": st.tit_for_tat},
    {"naziv": "Arryn", "strategija_id": "tit_for_tat", "strategija_naziv": "TFT", "fn": st.tit_for_tat},
    {"naziv": "Tully", "strategija_id": "tit_for_two_tats", "strategija_naziv": "TFT-2T", "fn": st.tit_for_two_tats},
    {"naziv": "Mormont", "strategija_id": "uvijek_suradjuj", "strategija_naziv": "Uvijek surađuj", "fn": st.uvijek_suradjuj},
    {"naziv": "Tyrell", "strategija_id": "win_stay_lose_shift", "strategija_naziv": "WSLS (Pavlov)", "fn": st.win_stay_lose_shift},
    {"naziv": "Martell", "strategija_id": "slucajna_0_60", "strategija_naziv": "Slučajno (60% S)", "fn": lambda moja, protiv: st.slucajna_strategija(moja, protiv, 0.60)},
    {"naziv": "Greyjoy", "strategija_id": "sumnjivi_tit_for_tat", "strategija_naziv": "Sumnjivi TFT", "fn": st.sumnjivi_tit_for_tat},
    {"naziv": "Frey", "strategija_id": "joss", "strategija_naziv": "JOSS (10% I)", "fn": lambda moja, protiv: st.joss(moja, protiv, p_izdaje_nakon_suradnje=0.10)},
    {"naziv": "Lannister", "strategija_id": "always_defect", "strategija_naziv": "Uvijek izdaja", "fn": st.uvijek_izdaj},
    {"naziv": "Bolton", "strategija_id": "always_defect", "strategija_naziv": "Uvijek izdaja", "fn": st.uvijek_izdaj},
    {"naziv": "Baratheon", "strategija_id": "grim_trigger", "strategija_naziv": "Grim Trigger", "fn": st.grim_trigger},
    {"naziv": "Targaryen", "strategija_id": "learning_tft", "strategija_naziv": "Učenje (ε=0.10)", "fn": st.tit_for_tat, "je_ucenje": True, "epsilon": 0.10},
]

STRATEGIJA_LABELS = {
    "tit_for_tat": "TFT",
    "tit_for_two_tats": "TFT-2T",
    "uvijek_suradjuj": "Uvijek surađuj",
    "win_stay_lose_shift": "WSLS",
    "slucajna_0_60": "Slučajno (60% S)",
    "sumnjivi_tit_for_tat": "Sumnjivi TFT",
    "joss": "JOSS (10% I)",
    "always_defect": "Uvijek izdaja",
    "grim_trigger": "Grim Trigger",
    "learning_tft": "Učenje (ε=0.10)",
}

STRATEGIJA_ORDER = [
    "tit_for_tat",
    "tit_for_two_tats",
    "uvijek_suradjuj",
    "win_stay_lose_shift",
    "sumnjivi_tit_for_tat",
    "always_defect",
    "grim_trigger",
    "slucajna_0_60",
    "joss",
    "learning_tft",
]

PARAM_META = {
    "slucajna_0_60": [
        {"key": "param", "label": "p", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": "{:.0f}%"},
    ],
    "joss": [
        {"key": "param", "label": "pI", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": "{:.0f}%"},
    ],
    "learning_tft": [
        {"key": "epsilon", "label": "istraživanje (ε)", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": "{:.2f}"},
        {"key": "alpha", "label": "učenje (α)", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": "{:.2f}"},
        {"key": "gamma", "label": "nagrada (γ)", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": "{:.2f}"},
    ],
}


def _build_default_settings():
    counts = {}
    for d in HOUSE_DEFS:
        counts[d["strategija_id"]] = counts.get(d["strategija_id"], 0) + 1
    settings = {}
    for sid in STRATEGIJA_ORDER:
        cfg = {"enabled": True, "count": counts.get(sid, 0)}
        if sid == "slucajna_0_60":
            cfg["param"] = 0.60
        if sid == "joss":
            cfg["param"] = 0.10
        if sid == "learning_tft":
            cfg["epsilon"] = 0.10
            cfg["alpha"] = 0.20
            cfg["gamma"] = 0.90
        settings[sid] = cfg
    return settings


STRATEGIJA_MAX = {sid: cfg["count"] for sid, cfg in _build_default_settings().items()}


def _build_agents_from_settings(settings):
    agenti = []
    by_sid = {}
    for d in HOUSE_DEFS:
        by_sid.setdefault(d["strategija_id"], []).append(d)
    for sid in STRATEGIJA_ORDER:
        cfg = settings.get(sid, {"enabled": False, "count": 0})
        if not cfg["enabled"] or cfg["count"] <= 0:
            continue
        pool = by_sid.get(sid, [])
        for d in pool[: cfg["count"]]:
            fn = d["fn"]
            if sid == "slucajna_0_60":
                p = cfg.get("param", 0.60)
                fn = lambda moja, protiv, p=p: st.slucajna_strategija(moja, protiv, p)
                strategija_naziv = f"Slučajno ({int(round(p * 100))}% S)"
            if sid == "joss":
                p = cfg.get("param", 0.10)
                fn = lambda moja, protiv, p=p: st.joss(moja, protiv, p_izdaje_nakon_suradnje=p)
                strategija_naziv = f"JOSS ({int(round(p * 100))}% I)"
            if sid == "learning_tft":
                p = cfg.get("epsilon", d.get("epsilon", 0.10))
                strategija_naziv = f"Učenje (ε={p:.2f})"
            if sid not in ("slucajna_0_60", "joss", "learning_tft"):
                strategija_naziv = d["strategija_naziv"]
            agenti.append(
                KucaAgent(
                    d["naziv"],
                    strategija_naziv,
                    fn,
                    je_ucenje=d.get("je_ucenje", False),
                    epsilon=cfg.get("epsilon", d.get("epsilon", 0.10)),
                )
            )
    return agenti


def _build_spade_kuca_defs(settings):
    by_sid = {}
    for d in SPADE_KUCE:
        by_sid.setdefault(d["config"].strategija_id, []).append(d)
    kuca_defs = []
    for sid in STRATEGIJA_ORDER:
        cfg = settings.get(sid, {"enabled": False, "count": 0})
        if not cfg["enabled"] or cfg["count"] <= 0:
            continue
        pool = by_sid.get(sid, [])
        for d in pool[: cfg["count"]]:
            conf = d["config"]
            if sid == "slucajna_0_60":
                conf = replace(conf, p_suradnje=cfg.get("param", 0.60))
            elif sid == "joss":
                conf = replace(conf, p_joss=cfg.get("param", 0.10))
            elif sid == "learning_tft":
                conf = replace(
                    conf,
                    epsilon=cfg.get("epsilon", 0.10),
                    alpha=cfg.get("alpha", 0.20),
                    gamma=cfg.get("gamma", 0.90),
                )
            kuca_defs.append({"jid": d["jid"], "password": d["password"], "config": conf})
    return kuca_defs


@dataclass
class Dogadjaj:
    a: str
    b: str
    potez_a: Potez
    potez_b: Potez
    bod_a: int
    bod_b: int


def kreiraj_agente(settings=None) -> List[KucaAgent]:
    if settings is None:
        settings = _build_default_settings()
    return _build_agents_from_settings(settings)


def pozicioniraj_kuce(kuce: List[str], cx: int, cy: int, radius: int) -> Dict[str, Tuple[int, int]]:
    # raspored u krug (mapa)
    n = len(kuce)
    poz = {}
    for i, k in enumerate(kuce):
        ang = (2 * math.pi) * (i / n) - math.pi / 2
        x = cx + int(radius * math.cos(ang))
        y = cy + int(radius * math.sin(ang))
        poz[k] = (x, y)
    return poz


def boja_veze(potez_a: Potez, potez_b: Potez) -> Tuple[int, int, int]:
    if potez_a == "S" and potez_b == "S":
        return BOJA_SS
    if potez_a == "I" and potez_b == "I":
        return BOJA_II
    return BOJA_IZDAJA


def nacrtaj_strelicu(
    screen,
    from_pos: Tuple[int, int],
    to_pos: Tuple[int, int],
    color: Tuple[int, int, int],
    target_radius: int,
) -> None:
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux = dx / length
    uy = dy / length

    end_x = to_pos[0] - ux * (target_radius + 1)
    end_y = to_pos[1] - uy * (target_radius + 1)
    arrow_len = 10
    arrow_w = 5
    base_x = end_x - ux * arrow_len
    base_y = end_y - uy * arrow_len
    perp_x = -uy
    perp_y = ux

    left = (base_x + perp_x * arrow_w, base_y + perp_y * arrow_w)
    right = (base_x - perp_x * arrow_w, base_y - perp_y * arrow_w)
    tip = (end_x, end_y)
    outline_len = arrow_len + 2
    outline_w = arrow_w + 2
    obase_x = end_x - ux * outline_len
    obase_y = end_y - uy * outline_len
    oleft = (obase_x + perp_x * outline_w, obase_y + perp_y * outline_w)
    oright = (obase_x - perp_x * outline_w, obase_y - perp_y * outline_w)
    pygame.draw.polygon(screen, BOJA_IZDAJA, [oleft, oright, tip])
    pygame.draw.polygon(screen, (0, 0, 0), [left, right, tip])


def napravi_kruzni_grb(slika: pygame.Surface, size: int) -> pygame.Surface:
    scaled = pygame.transform.smoothscale(slika, (size, size))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
    scaled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return scaled


def ucitaj_grbove(kuce: List[str]) -> Dict[str, pygame.Surface]:
    grbovi = {}
    for k in kuce:
        path = os.path.join("assets", f"House_{k}.png")
        if not os.path.exists(path):
            continue
        grbovi[k] = pygame.image.load(path).convert_alpha()
    return grbovi


def udaljenost_tocke_od_duzine(px: int, py: int, x1: int, y1: int, x2: int, y2: int) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def tekst_dogadjaja(d: Dogadjaj) -> str:
    if d.potez_a == "S" and d.potez_b == "S":
        return f"Savez: {d.a} <-> {d.b}  (+{d.bod_a}/+{d.bod_b})"
    if d.potez_a == "I" and d.potez_b == "I":
        return f"Sukob: {d.a} x {d.b}  (+{d.bod_a}/+{d.bod_b})"
    # izdaja
    if d.potez_a == "I" and d.potez_b == "S":
        return f"Izdaja: {d.a} -> {d.b}  (+{d.bod_a}/+{d.bod_b})"
    if d.potez_a == "S" and d.potez_b == "I":
        return f"Izdaja: {d.b} -> {d.a}  (+{d.bod_a}/+{d.bod_b})"
    return f"{d.a} vs {d.b}: {d.potez_a}/{d.potez_b}"


def main() -> None:
    pygame.init()
    pygame.display.set_caption("GoT Axelrod VAS — Mapa")

    W, H = 1720, 700
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Segoe UI", 18)
    font_small = pygame.font.SysFont("Segoe UI", 16)
    font_title = pygame.font.SysFont("Segoe UI", 22)
    font_mono = pygame.font.SysFont("Consolas", 16)

    # Layout
    settings_w = 300
    panel_w = 420
    mapa_rect = pygame.Rect(settings_w, 0, W - panel_w - settings_w, H)
    panel_rect = pygame.Rect(W - panel_w, 0, panel_w, H)
    settings_rect = pygame.Rect(0, 0, settings_w, H)

    # Stanje simulacije
    def reset(settings_current, start_spade: bool = True) -> Tuple[List[KucaAgent], Simulacija, int, List[str], Dict[Tuple[str, str], Dogadjaj], List[str], int, int, float, Dict[str, Dict[str, int]], List[float], List[float], str, Dict[Tuple[str, str], Dict[str, int]], Dict[str, Dict[str, int]], SpadeSession | None, Queue, dict]:
        agenti_local = kreiraj_agente(settings_current)
        sim_local = Simulacija(MATRICA_ISPLATE)
        sezona_local = 0
        kuce = [a.naziv for a in agenti_local]
        zadnji_ishodi: Dict[Tuple[str, str], Dogadjaj] = {}
        log: List[str] = []
        total_suradnje = 0
        total_poteza = 0
        last_season_pct = 0.0
        agent_stats, global_pct_by_season, learning_pct_by_season, learning_rank_by_season, learning_agent, pair_stats, rank_stats = ui_stats.init_stats(agenti_local)
        spade_session = None
        spade_result_q: Queue = Queue()
        spade_state = {"in_flight": False, "last_error": None, "last_ok": None}
        if USE_SPADE and start_spade:
            spade_defs = _build_spade_kuca_defs(settings_current)
            spade_session = SpadeSession(auto_register=True, kuca_defs=spade_defs)
            spade_session.start()
        return (
            agenti_local,
            sim_local,
            sezona_local,
            kuce,
            zadnji_ishodi,
            log,
            total_suradnje,
            total_poteza,
            last_season_pct,
            agent_stats,
            global_pct_by_season,
            learning_pct_by_season,
            learning_rank_by_season,
            learning_agent,
            pair_stats,
            rank_stats,
            spade_session,
            spade_result_q,
            spade_state,
        )

    settings_current = _build_default_settings()
    settings_draft = deepcopy(settings_current)
    settings_pending = None
    pending_message = ""
    game_mode = None
    screen_mode = "menu"
    era_progress = 0
    era_points: Dict[str, int] = {}
    noise_rate = 0.0
    noise_pending = None
    got_noise_base = 0.0
    got_bonus_8 = False
    got_bonus_4 = False

    (
        agenti,
        sim,
        sezona,
        kuce,
        zadnji_ishodi,
        log,
        total_suradnje,
        total_poteza,
        last_season_pct,
        agent_stats,
        global_pct_by_season,
        learning_pct_by_season,
        learning_rank_by_season,
        learning_agent,
        pair_stats,
        rank_stats,
        spade_session,
        spade_result_q,
        spade_state,
    ) = reset(settings_current, start_spade=False)

    pozicije = pozicioniraj_kuce(
        kuce,
        cx=mapa_rect.centerx,
        cy=mapa_rect.centery,
        radius=min(mapa_rect.width, mapa_rect.height) // 3
    )
    grbovi = ucitaj_grbove(kuce)

    pauza = True
    brzina = 1.0  # sezona u sekundi
    akumulirano = 0.0
    show_stats = False
    stats_tab = 0
    settings_controls = []
    menu_buttons = []

    # za "blink" efekat aktivnog događaja u sezoni
    aktivne_veze: List[Tuple[str, str]] = []

    def _apply_pending_if_ready() -> bool:
        nonlocal settings_current, settings_draft, settings_pending, pending_message
        nonlocal agenti, sim, sezona, kuce, zadnji_ishodi, log
        nonlocal total_suradnje, total_poteza, last_season_pct
        nonlocal agent_stats, global_pct_by_season, learning_pct_by_season, learning_rank_by_season, learning_agent
        nonlocal pair_stats, rank_stats, spade_session, spade_result_q, spade_state, pozicije, grbovi
        nonlocal noise_rate, noise_pending, got_noise_base, got_bonus_8, got_bonus_4

        if not settings_pending or spade_state["in_flight"]:
            return False

        if spade_session:
            spade_session.stop()

        settings_current = settings_pending
        settings_draft = deepcopy(settings_current)
        settings_pending = None
        pending_message = ""
        if noise_pending is not None:
            noise_rate = noise_pending
            noise_pending = None
            if game_mode == "got":
                got_noise_base = noise_rate
                got_bonus_8 = False
                got_bonus_4 = False

        (
            agenti,
            sim,
            sezona,
            kuce,
            zadnji_ishodi,
            log,
            total_suradnje,
            total_poteza,
            last_season_pct,
            agent_stats,
            global_pct_by_season,
            learning_pct_by_season,
            learning_rank_by_season,
            learning_agent,
            pair_stats,
            rank_stats,
            spade_session,
            spade_result_q,
            spade_state,
        ) = reset(settings_current)

        pozicije = pozicioniraj_kuce(
            kuce,
            cx=mapa_rect.centerx,
            cy=mapa_rect.centery,
            radius=min(mapa_rect.width, mapa_rect.height) // 3
        )
        grbovi = ucitaj_grbove(kuce)
        era_reset()
        return True

    def era_reset():
        nonlocal era_progress, era_points
        era_progress = 0
        era_points = {a.naziv: 0 for a in agenti}

    era_reset()

    def _calc_season_points(dog):
        points = {}
        for a, b, _pa, _pb, ba, bb in dog:
            points[a] = points.get(a, 0) + ba
            points[b] = points.get(b, 0) + bb
        return points

    def _eliminate_if_needed(season_points):
        nonlocal agenti, kuce, pozicije, grbovi
        nonlocal era_progress, era_points, zadnji_ishodi
        nonlocal noise_rate, noise_pending, got_noise_base, got_bonus_8, got_bonus_4
        nonlocal agent_stats, rank_stats
        if game_mode != "got":
            return
        if not season_points:
            return
        for k, v in season_points.items():
            era_points[k] = era_points.get(k, 0) + v
        era_progress += 1
        if era_progress < ERA_LEN or len(agenti) <= 1:
            return
        elim_name = min(era_points.items(), key=lambda x: x[1])[0]
        log.insert(0, f"[S{sezona}] Eliminacija: {elim_name}")
        del log[60:]
        agenti = [a for a in agenti if a.naziv != elim_name]
        kuce = [a.naziv for a in agenti]
        zadnji_ishodi = {
            k: v for k, v in zadnji_ishodi.items()
            if elim_name not in k
        }
        pozicije = pozicioniraj_kuce(
            kuce,
            cx=mapa_rect.centerx,
            cy=mapa_rect.centery,
            radius=min(mapa_rect.width, mapa_rect.height) // 3
        )
        grbovi = ucitaj_grbove(kuce)
        if elim_name in agent_stats:
            del agent_stats[elim_name]
        rank_stats["top3"].pop(elim_name, None)
        rank_stats["last"].pop(elim_name, None)
        for a in agenti:
            a.bodovi = 0
        era_reset()
        if game_mode == "got":
            n = len(agenti)
            if n <= 8 and not got_bonus_8:
                got_bonus_8 = True
                noise_rate = got_noise_base + 0.02
            if n <= 4 and not got_bonus_4:
                got_bonus_8 = True
                got_bonus_4 = True
                noise_rate = got_noise_base + 0.02 + 0.03
            noise_rate = min(0.50, max(0.0, noise_rate))
            noise_pending = None

    def _primijeni_sezonu(dog):
        nonlocal sezona, aktivne_veze, total_suradnje, total_poteza, last_season_pct
        nonlocal agent_stats, global_pct_by_season, learning_pct_by_season, learning_rank_by_season, learning_agent, pair_stats, rank_stats

        sezona += 1
        aktivne_veze = []

        # uzmi zadnje ishode po paru (za crtanje veza)
        for (a, b, pa, pb, ba, bb) in dog:
            key = tuple(sorted((a, b)))
            zadnji_ishodi[key] = Dogadjaj(a=a, b=b, potez_a=pa, potez_b=pb, bod_a=ba, bod_b=bb)
            aktivne_veze.append(key)

        season_suradnje, season_poteza, last_season_pct = ui_stats.update_stats_for_season(
            dog,
            agent_stats,
            global_pct_by_season,
            learning_pct_by_season,
            learning_rank_by_season,
            learning_agent,
            pair_stats,
            rank_stats,
            agenti,
        )
        total_suradnje += season_suradnje
        total_poteza += season_poteza

        # log: uzmi par najzanimljivijih događaja (npr. izdaje) + 3 random
        dogadjaji = [zadnji_ishodi[tuple(sorted((d[0], d[1])))] for d in dog]
        izdaje = [d for d in dogadjaji if (d.potez_a, d.potez_b) in [("I", "S"), ("S", "I")]]
        # najnoviji log na vrh
        for d in (izdaje[:4] + dogadjaji[:3]):
            log.insert(0, f"[S{sezona}] {tekst_dogadjaja(d)}")
        del log[60:]  # ograniči log
        season_points = _calc_season_points(dog)
        _eliminate_if_needed(season_points)

    def odigraj_jednu_sezonu():
        _apply_pending_if_ready()
        dog = sim.odigraj_sezonu_sa_dogadjajima(agenti)
        _primijeni_sezonu(dog)

    def _start_spade_sezonu():
        nonlocal spade_state
        _apply_pending_if_ready()
        if spade_state["in_flight"] or not spade_session:
            return
        spade_state["in_flight"] = True
        spade_state["last_error"] = None

        def _worker():
            try:
                aktivni = [a.naziv for a in agenti]
                rezultat = spade_session.play_season_sync(active_names=aktivni, noise_rate=noise_rate)
                spade_result_q.put(("ok", rezultat))
            except Exception as exc:
                spade_result_q.put(("err", exc))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _poll_spade_rezultat():
        nonlocal spade_state
        try:
            status, payload = spade_result_q.get_nowait()
        except Empty:
            return False
        spade_state["in_flight"] = False
        if status == "ok":
            spade_state["last_ok"] = time.time()
            dog = payload["dogadjaji"]
            bodovi = payload["bodovi"]
            learning_stats = payload.get("learning_stats", {})
            for a in agenti:
                a.bodovi += bodovi.get(a.naziv, 0)
                if a.naziv in learning_stats:
                    _merge_learning_stats(a.statistika_ucenja, learning_stats[a.naziv])
            _primijeni_sezonu(dog)
        else:
            spade_state["last_error"] = str(payload)
            log.insert(0, f"[S{sezona}] SPADE greška: {payload}")
            del log[60:]
        return True


    def _merge_learning_stats(target, incoming):
        for protivnik, potezi in incoming.items():
            if protivnik not in target:
                target[protivnik] = {
                    "S": {"n": 0.0, "avg": 0.0},
                    "I": {"n": 0.0, "avg": 0.0},
                }
            for potez in ("S", "I"):
                inc = potezi.get(potez, {"n": 0.0, "avg": 0.0})
                tgt = target[protivnik][potez]
                n_old = tgt.get("n", 0.0)
                avg_old = tgt.get("avg", 0.0)
                n_add = inc.get("n", 0.0)
                avg_add = inc.get("avg", 0.0)
                if n_add <= 0:
                    continue
                n_new = n_old + n_add
                avg_new = avg_old + (avg_add - avg_old) * (n_add / n_new)
                tgt["n"] = n_new
                tgt["avg"] = avg_new
            for pref_key in ("pref_after_s", "pref_after_i"):
                if pref_key in potezi:
                    target[protivnik][pref_key] = potezi[pref_key]
            for pct_key in ("pct_s_after_s", "pct_i_after_i"):
                if pct_key in potezi:
                    target[protivnik][pct_key] = potezi[pct_key]

    def nacrtaj():
        screen.fill(BOJA_POZADINA)

        if screen_mode == "menu":
            title = font_title.render("Odaberi mod", True, BOJA_TEKST)
            screen.blit(title, (mapa_rect.centerx - title.get_width() // 2, 120))
            btn_w = 320
            btn_h = 48
            btn_x = mapa_rect.centerx - btn_w // 2
            btn_y = 200
            menu_buttons.clear()
            sim_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            got_rect = pygame.Rect(btn_x, btn_y + 70, btn_w, btn_h)
            pygame.draw.rect(screen, (50, 90, 140), sim_rect)
            pygame.draw.rect(screen, (90, 120, 160), sim_rect, 1)
            pygame.draw.rect(screen, (50, 90, 140), got_rect)
            pygame.draw.rect(screen, (90, 120, 160), got_rect, 1)
            sim_txt = font_small.render("Simulacija strategija", True, BOJA_TEKST)
            got_txt = font_small.render("Game of Thrones", True, BOJA_TEKST)
            screen.blit(sim_txt, (sim_rect.centerx - sim_txt.get_width() // 2, sim_rect.centery - sim_txt.get_height() // 2))
            screen.blit(got_txt, (got_rect.centerx - got_txt.get_width() // 2, got_rect.centery - got_txt.get_height() // 2))
            menu_buttons.append(("sim", sim_rect))
            menu_buttons.append(("got", got_rect))
            pygame.display.flip()
            return

        def nacrtaj_postavke():
            nonlocal settings_controls, pending_message
            settings_controls = []
            pygame.draw.rect(screen, BOJA_PANEL, settings_rect)

            screen.blit(font_title.render("Postavke", True, BOJA_TEKST), (settings_rect.x + 16, 14))
            screen.blit(font_small.render("Globalne strategije", True, BOJA_SUBT), (settings_rect.x + 16, 42))

            x = settings_rect.x + 16
            y = settings_rect.y + 70
            row_h = 22
            sub_h = 16
            sub_gap = 6
            checkbox = 14
            btn_w = 18

            for sid in STRATEGIJA_ORDER:
                cfg = settings_draft.get(sid, {"enabled": False, "count": 0})
                label = STRATEGIJA_LABELS.get(sid, sid)
                cb = pygame.Rect(x, y + 3, checkbox, checkbox)
                pygame.draw.rect(screen, BOJA_SUBT, cb, 1)
                if cfg["enabled"]:
                    pygame.draw.rect(screen, BOJA_SS, cb.inflate(-4, -4))
                settings_controls.append(("toggle", sid, cb))

                label_surf = font_small.render(label, True, BOJA_TEKST)
                screen.blit(label_surf, (x + checkbox + 8, y))

                minus_rect = pygame.Rect(settings_rect.right - 78, y, btn_w, btn_w)
                plus_rect = pygame.Rect(settings_rect.right - 52, y, btn_w, btn_w)
                pygame.draw.rect(screen, BOJA_SUBT, minus_rect, 1)
                pygame.draw.rect(screen, BOJA_SUBT, plus_rect, 1)
                screen.blit(font_small.render("-", True, BOJA_TEKST), (minus_rect.x + 5, minus_rect.y - 1))
                screen.blit(font_small.render("+", True, BOJA_TEKST), (plus_rect.x + 4, plus_rect.y - 1))

                settings_controls.append(("dec", sid, minus_rect))
                settings_controls.append(("inc", sid, plus_rect))

                count_txt = font_small.render(str(cfg["count"]), True, BOJA_TEKST)
                screen.blit(count_txt, (settings_rect.right - 28, y))

                y += row_h
                if sid in PARAM_META:
                    for meta in PARAM_META[sid]:
                        key = meta["key"]
                        pval = cfg.get(key, meta["min"])
                        ptxt = meta["fmt"].format(pval * 100.0) if meta["fmt"].endswith("%") else meta["fmt"].format(pval)
                        line = f"{meta['label']}={ptxt}"
                        line_surf = font_small.render(line, True, BOJA_SUBT)
                        screen.blit(line_surf, (x + checkbox + 8, y))

                        p_minus = pygame.Rect(settings_rect.right - 78, y, btn_w, btn_w)
                        p_plus = pygame.Rect(settings_rect.right - 52, y, btn_w, btn_w)
                        pygame.draw.rect(screen, BOJA_SUBT, p_minus, 1)
                        pygame.draw.rect(screen, BOJA_SUBT, p_plus, 1)
                        screen.blit(font_small.render("-", True, BOJA_TEKST), (p_minus.x + 5, p_minus.y - 1))
                        screen.blit(font_small.render("+", True, BOJA_TEKST), (p_plus.x + 4, p_plus.y - 1))
                        settings_controls.append(("dec_param", sid, key, p_minus))
                        settings_controls.append(("inc_param", sid, key, p_plus))
                        y += sub_h + sub_gap

            y += 12
            show_noise = noise_rate if noise_pending is None else noise_pending
            noise_label = f"Pogreska: {int(round(show_noise * 100))}%"
            screen.blit(font_small.render(noise_label, True, BOJA_TEKST), (x, y))
            n_minus = pygame.Rect(settings_rect.right - 78, y, btn_w, btn_w)
            n_plus = pygame.Rect(settings_rect.right - 52, y, btn_w, btn_w)
            pygame.draw.rect(screen, BOJA_SUBT, n_minus, 1)
            pygame.draw.rect(screen, BOJA_SUBT, n_plus, 1)
            screen.blit(font_small.render("-", True, BOJA_TEKST), (n_minus.x + 5, n_minus.y - 1))
            screen.blit(font_small.render("+", True, BOJA_TEKST), (n_plus.x + 4, n_plus.y - 1))
            settings_controls.append(("dec_noise", None, n_minus))
            settings_controls.append(("inc_noise", None, n_plus))

            save_rect = pygame.Rect(settings_rect.x + 16, settings_rect.bottom - 60, settings_rect.width - 32, 28)
            pygame.draw.rect(screen, (50, 90, 140), save_rect)
            pygame.draw.rect(screen, (90, 120, 160), save_rect, 1)
            save_text = font_small.render("Spremi", True, BOJA_TEKST)
            screen.blit(save_text, (save_rect.centerx - save_text.get_width() // 2, save_rect.centery - save_text.get_height() // 2))
            settings_controls.append(("save", None, save_rect))

            if pending_message:
                msg_x = settings_rect.x + 16
                msg_y = save_rect.y - 34
                if isinstance(pending_message, list):
                    for line in pending_message:
                        msg = font_small.render(line, True, BOJA_SUBT)
                        screen.blit(msg, (msg_x, msg_y))
                        msg_y += 16
                else:
                    msg = font_small.render(pending_message, True, BOJA_SUBT)
                    screen.blit(msg, (msg_x, msg_y))
            if noise_pending is not None:
                msg = font_small.render("Promjena pogreske je na cekanju", True, BOJA_SUBT)
                screen.blit(msg, (settings_rect.x + 16, save_rect.y - 50))

        nacrtaj_postavke()

        # Panel
        pygame.draw.rect(screen, BOJA_PANEL, panel_rect)

        # Naslov
        t = font_title.render("GoT Axelrod — Mapa", True, BOJA_TEKST)
        screen.blit(t, (panel_rect.x + 16, 14))
        if game_mode:
            mode_label = "Simulacija strategija" if game_mode == "sim" else "Game of Thrones"
            mode_text = font_small.render(mode_label, True, BOJA_SUBT)
            screen.blit(mode_text, (mapa_rect.centerx - mode_text.get_width() // 2, 12))
        sub = font_small.render(f"Sezona: {sezona} | {'PAUZA' if pauza else 'RUN'} | brzina: {brzina:.1f}/s", True, BOJA_SUBT)
        screen.blit(sub, (panel_rect.x + 16, 44))

        # Kontrole
        ctrl1 = font_small.render("SPACE: pauza  |  N: step  |  +/-: brzina   |   R: reset", True, BOJA_SUBT)
        ctrl2 = font_small.render("S: screenshot  |  T: stats  |  E: export  |  ESC: izlaz", True, BOJA_SUBT)
        screen.blit(ctrl1, (panel_rect.x + 16, 70))
        screen.blit(ctrl2, (panel_rect.x + 16, 92))

        # Legenda boja (desno, uz mapu)
        legend_x = mapa_rect.right - 160
        legend_y = mapa_rect.y + 14
        legend_items = [
            (BOJA_SS, "Savez (S,S)"),
            (BOJA_IZDAJA, "Izdaja (S/I)"),
            (BOJA_II, "Sukob (I,I)"),
        ]
        for i, (col, label) in enumerate(legend_items):
            y = legend_y + i * 18
            pygame.draw.circle(screen, col, (legend_x + 6, y + 6), 5)
            txt = font_small.render(label, True, BOJA_SUBT)
            text_y = y + 6 - (txt.get_height() // 2)
            screen.blit(txt, (legend_x + 20, text_y))

        mx, my = pygame.mouse.get_pos()
        base_r = RADIUS_CVOR
        max_extra = 20
        poredak = sorted(agenti, key=lambda x: x.bodovi, reverse=True)
        radius_map = {}
        n = len(poredak)
        for idx, a in enumerate(poredak):
            if n > 1:
                scale = (n - 1 - idx) / (n - 1)
            else:
                scale = 0.0
            radius_map[a.naziv] = int(base_r + max_extra * scale)

        # Veze (mapa)
        # crtaj sve parove za koje imamo zadnji ishod
        hovered_edge_text = None
        hovered_edge_dist = 9999.0
        for key, d in zadnji_ishodi.items():
            a, b = key
            if a not in pozicije or b not in pozicije:
                continue
            x1, y1 = pozicije[a]
            x2, y2 = pozicije[b]
            col = boja_veze(d.potez_a, d.potez_b)

            # debljina linije: jače za saveze/izdaje
            if col == BOJA_SS:
                w = 3
            elif col == BOJA_IZDAJA:
                w = 3
            else:
                w = 2

            # malo "naglašavanje" aktivnih veza u ovoj sezoni
            if key in aktivne_veze:
                pygame.draw.line(screen, col, (x1, y1), (x2, y2), w + 1)
            else:
                pygame.draw.line(screen, col, (x1, y1), (x2, y2), w)

            if (d.potez_a, d.potez_b) in [("I", "S"), ("S", "I")]:
                if d.potez_a == "I":
                    izdajnik = d.a
                    zrtva = d.b
                else:
                    izdajnik = d.b
                    zrtva = d.a
                nacrtaj_strelicu(
                    screen,
                    pozicije[izdajnik],
                    pozicije[zrtva],
                    BOJA_IZDAJA,
                    radius_map.get(zrtva, RADIUS_CVOR),
                )

            dist = udaljenost_tocke_od_duzine(mx, my, x1, y1, x2, y2)
            if dist < 6 and dist < hovered_edge_dist:
                hovered_edge_dist = dist
                if d.potez_a == "S" and d.potez_b == "S":
                    hovered_edge_text = f"Savez: {d.a} <-> {d.b}"
                elif d.potez_a == "I" and d.potez_b == "I":
                    hovered_edge_text = f"Sukob: {d.a} x {d.b}"
                elif d.potez_a == "I" and d.potez_b == "S":
                    hovered_edge_text = f"Izdaja: {d.a} -> {d.b}"
                else:
                    hovered_edge_text = f"Izdaja: {d.b} -> {d.a}"

        # Čvorovi kuća
        hovered = None
        for a in agenti:
            x, y = pozicije[a.naziv]
            r = radius_map.get(a.naziv, RADIUS_CVOR)
            dist = (mx - x) ** 2 + (my - y) ** 2
            if dist <= (r + 6) ** 2:
                hovered = a.naziv

        for a in agenti:
            x, y = pozicije[a.naziv]
            r = radius_map.get(a.naziv, RADIUS_CVOR)
            col = BOJA_CVOR_AKT if a.naziv == hovered else BOJA_CVOR
            pygame.draw.circle(screen, col, (x, y), r)
            icon = grbovi.get(a.naziv)
            if icon:
                size = max(8, r * 2 - 6)
                icon_c = napravi_kruzni_grb(icon, size)
                screen.blit(icon_c, (x - icon_c.get_width() // 2, y - icon_c.get_height() // 2))
            outline_col = BOJA_CVOR_UCENJE if a.je_ucenje else (10, 10, 10)
            outline_w = 3 if a.je_ucenje else 2
            pygame.draw.circle(screen, outline_col, (x, y), r, outline_w)

            if a.je_ucenje:
                t = pygame.time.get_ticks() / 1000.0
                pulse = int(4 * (0.5 + 0.5 * math.sin(t * 4.0)))
                pygame.draw.circle(screen, BOJA_CVOR_UCENJE, (x, y), r + 6 + pulse, 2)

            label = font_small.render(a.naziv, True, BOJA_TEKST)
            screen.blit(label, (x - label.get_width() // 2, y + r + 6))

        # Tooltip
        if hovered:
            a = next(x for x in agenti if x.naziv == hovered)
            tip1 = font.render(f"{a.naziv}", True, BOJA_TEKST)
            tip2 = font_small.render(f"Strategija: {a.naziv_strategije}", True, BOJA_SUBT)
            tip3 = font_small.render(f"Bodovi: {a.bodovi}", True, BOJA_SUBT)

            tx, ty = mx + 12, my + 12
            w = max(tip1.get_width(), tip2.get_width(), tip3.get_width()) + 14
            h = tip1.get_height() + tip2.get_height() + tip3.get_height() + 14
            pygame.draw.rect(screen, (0, 0, 0), (tx, ty, w, h), border_radius=8)
            pygame.draw.rect(screen, (90, 90, 90), (tx, ty, w, h), 1, border_radius=8)
            screen.blit(tip1, (tx + 7, ty + 6))
            screen.blit(tip2, (tx + 7, ty + 6 + tip1.get_height()))
            screen.blit(tip3, (tx + 7, ty + 6 + tip1.get_height() + tip2.get_height()))
        elif hovered_edge_text:
            tip = font_small.render(hovered_edge_text, True, BOJA_TEKST)
            tx, ty = mx + 12, my + 12
            w = tip.get_width() + 14
            h = tip.get_height() + 12
            pygame.draw.rect(screen, (0, 0, 0), (tx, ty, w, h), border_radius=8)
            pygame.draw.rect(screen, (90, 90, 90), (tx, ty, w, h), 1, border_radius=8)
            screen.blit(tip, (tx + 7, ty + 6))

        # Sažetak sezone
        summary_y = 118
        total_pct = 100.0 * total_suradnje / total_poteza if total_poteza > 0 else 0.0
        sum1 = font_small.render(f"Suradnja (zadnja sezona): {last_season_pct:.1f}%", True, BOJA_SUBT)
        sum2 = font_small.render(f"Suradnja (ukupno): {total_pct:.1f}%", True, BOJA_SUBT)
        screen.blit(sum1, (panel_rect.x + 16, summary_y))
        screen.blit(sum2, (panel_rect.x + 16, summary_y + 20))

        if USE_SPADE:
            status_y = summary_y + 40
            if spade_state["in_flight"]:
                status_text = "SPADE: sezona u tijeku..."
                status_col = BOJA_SUBT
            elif spade_state["last_error"]:
                status_text = "SPADE: greška (vidi log)"
                status_col = BOJA_IZDAJA
            elif spade_state["last_ok"]:
                status_text = "SPADE: OK"
                status_col = BOJA_SS
            else:
                status_text = "SPADE: spremno"
                status_col = BOJA_SUBT
            screen.blit(font_small.render(status_text, True, status_col), (panel_rect.x + 16, status_y + 8))

        # Leaderboard
        y0 = 170
        if USE_SPADE:
            y0 += 18
        screen.blit(font.render("Leaderboard", True, BOJA_TEKST), (panel_rect.x + 16, y0))
        poredak = sorted(agenti, key=lambda x: x.bodovi, reverse=True)
        y = y0 + 28
        for idx, a in enumerate(poredak[:12], start=1):
            strategija = a.naziv_strategije[:16]
            txt = f"{idx:>2}. {a.naziv:<10} {strategija:<16} {a.bodovi:>5}"
            line = font_mono.render(txt, True, BOJA_TEKST)
            screen.blit(line, (panel_rect.x + 16, y))
            y += 18

                # Event log
        y_log = y + 12
        screen.blit(font.render("Događaji (zadnje)", True, BOJA_TEKST), (panel_rect.x + 16, y_log))
        y = y_log + 28
        line_h = 18
        max_lines = max(0, (panel_rect.bottom - 12 - y) // line_h)
        for s in log[:max_lines]:
            line = font_small.render(s[:44] + ("…" if len(s) > 44 else ""), True, BOJA_SUBT)
            screen.blit(line, (panel_rect.x + 16, y))
            y += line_h


        if show_stats:
            agent_rows, strategija_rows = ui_stats.build_stats(agenti, agent_stats, sezona)
            pair_rows = ui_stats.build_pair_stats(pair_stats)
            learning_rows = ui_stats.build_learning_stats(agenti, learning_agent)
            rank_rows = ui_stats.build_rank_stats(rank_stats)
            ui_stats.draw_stats_overlay(
                screen, W, H, font_title, font_small, font_mono,
                BOJA_TEKST, BOJA_SUBT, agent_rows, strategija_rows,
                pair_rows, learning_rows, rank_rows, stats_tab
            )

        pygame.display.flip()

    # Main loop
    last = time.time()
    while True:
        dt = time.time() - last
        last = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if spade_session:
                    spade_session.stop()
                pygame.quit()
                sys.exit(0)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if spade_session:
                        spade_session.stop()
                    pygame.quit()
                    sys.exit(0)
                if screen_mode == "menu":
                    continue
                elif event.key == pygame.K_SPACE:
                    pauza = not pauza
                elif event.key == pygame.K_n:
                    if USE_SPADE:
                        _start_spade_sezonu()
                    else:
                        odigraj_jednu_sezonu()
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    brzina = min(20.0, brzina + 0.5)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    brzina = max(0.5, brzina - 0.5)
                elif event.key == pygame.K_r:
                    if spade_session:
                        spade_session.stop()
                    settings_draft = deepcopy(settings_current)
                    pending_message = ""
                    agenti, sim, sezona, kuce, zadnji_ishodi, log, total_suradnje, total_poteza, last_season_pct, agent_stats, global_pct_by_season, learning_pct_by_season, learning_rank_by_season, learning_agent, pair_stats, rank_stats, spade_session, spade_result_q, spade_state = reset(settings_current)
                    era_reset()
                    if game_mode == "got":
                        got_noise_base = noise_rate
                        got_bonus_8 = False
                        got_bonus_4 = False
                    pozicije = pozicioniraj_kuce(
                        kuce,
                        cx=mapa_rect.centerx,
                        cy=mapa_rect.centery,
                        radius=min(mapa_rect.width, mapa_rect.height) // 3
                    )
                    grbovi = ucitaj_grbove(kuce)
                elif event.key == pygame.K_s:
                    os.makedirs("screenshots", exist_ok=True)
                    filename = os.path.join("screenshots", f"mapa_sezona_{sezona}.png")
                    pygame.image.save(screen, filename)
                elif event.key == pygame.K_t:
                    show_stats = not show_stats
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and show_stats:
                    if event.key == pygame.K_LEFT:
                        stats_tab = (stats_tab - 1) % 5
                    else:
                        stats_tab = (stats_tab + 1) % 5
                elif event.key == pygame.K_e:
                    ui_stats.export_stats(
                        agenti,
                        agent_stats,
                        sezona,
                        global_pct_by_season,
                        learning_pct_by_season,
                        learning_rank_by_season,
                        learning_agent,
                        pair_stats,
                        rank_stats,
                    )

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if screen_mode == "menu":
                    mode_id = None
                    for mid, rect in menu_buttons:
                        if rect.collidepoint(mx, my):
                            mode_id = mid
                            break
                    if mode_id is None:
                        continue
                    # set mode and reset state
                    screen_mode = "sim"
                    game_mode = mode_id
                    if game_mode == "got":
                        got_noise_base = noise_rate
                        got_bonus_8 = False
                        got_bonus_4 = False
                    if spade_session:
                        spade_session.stop()
                    settings_draft = deepcopy(settings_current)
                    pending_message = ""
                    (
                        agenti,
                        sim,
                        sezona,
                        kuce,
                        zadnji_ishodi,
                        log,
                        total_suradnje,
                        total_poteza,
                        last_season_pct,
                        agent_stats,
                        global_pct_by_season,
                        learning_pct_by_season,
                        learning_rank_by_season,
                        learning_agent,
                        pair_stats,
                        rank_stats,
                        spade_session,
                        spade_result_q,
                        spade_state,
                    ) = reset(settings_current)
                    era_reset()
                    pozicije = pozicioniraj_kuce(
                        kuce,
                        cx=mapa_rect.centerx,
                        cy=mapa_rect.centery,
                        radius=min(mapa_rect.width, mapa_rect.height) // 3
                    )
                    grbovi = ucitaj_grbove(kuce)
                    continue

                for control in settings_controls:
                    if len(control) == 3:
                        action, sid, rect = control
                        key = None
                    else:
                        action, sid, key, rect = control
                    if not rect.collidepoint(mx, my):
                        continue
                    if action == "toggle" and sid in settings_draft:
                        settings_draft[sid]["enabled"] = not settings_draft[sid]["enabled"]
                    elif action == "dec" and sid in settings_draft:
                        settings_draft[sid]["count"] = max(0, settings_draft[sid]["count"] - 1)
                    elif action == "inc" and sid in settings_draft:
                        max_count = STRATEGIJA_MAX.get(sid, 0)
                        settings_draft[sid]["count"] = min(max_count, settings_draft[sid]["count"] + 1)
                    elif action == "dec_noise":
                        noise_pending = noise_rate if noise_pending is None else noise_pending
                        noise_pending = max(0.0, noise_pending - 0.01)
                    elif action == "inc_noise":
                        noise_pending = noise_rate if noise_pending is None else noise_pending
                        noise_pending = min(0.50, noise_pending + 0.01)
                    elif action == "dec_param" and sid in settings_draft:
                        metas = PARAM_META.get(sid, [])
                        if key:
                            meta = next((m for m in metas if m["key"] == key), None)
                            if meta:
                                cur = settings_draft[sid].get(key, meta["min"])
                                cur = max(meta["min"], cur - meta["step"])
                                settings_draft[sid][key] = cur
                    elif action == "inc_param" and sid in settings_draft:
                        metas = PARAM_META.get(sid, [])
                        if key:
                            meta = next((m for m in metas if m["key"] == key), None)
                            if meta:
                                cur = settings_draft[sid].get(key, meta["min"])
                                cur = min(meta["max"], cur + meta["step"])
                                settings_draft[sid][key] = cur
                    elif action == "save":
                        settings_pending = deepcopy(settings_draft)
                        pending_message = ["Promjene ce se primijeniti", "na pocetku nove sezone"]

        if screen_mode != "menu" and not pauza:
            akumulirano += dt
            period = 1.0 / brzina
            if akumulirano >= period:
                akumulirano = 0.0
                if USE_SPADE:
                    _start_spade_sezonu()
                else:
                    odigraj_jednu_sezonu()

        if screen_mode != "menu" and USE_SPADE:
            _poll_spade_rezultat()

        nacrtaj()
        clock.tick(60)


if __name__ == "__main__":
    main()
