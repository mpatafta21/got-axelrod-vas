
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

from agent import KucaAgent
from engine import Simulacija
import strategije as st

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


@dataclass
class Dogadjaj:
    a: str
    b: str
    potez_a: Potez
    potez_b: Potez
    bod_a: int
    bod_b: int


def kreiraj_agente() -> List[KucaAgent]:
    # 12 kuća
    agenti = [
        KucaAgent("Stark",      "TFT",                 st.tit_for_tat),
        KucaAgent("Arryn",      "TFT",                 st.tit_for_tat),
        KucaAgent("Tully",      "TFT-2T",              st.tit_for_two_tats),
        KucaAgent("Mormont",    "Uvijek surađuj",      st.uvijek_suradjuj),

        KucaAgent("Tyrell",     "WSLS (Pavlov)",       st.win_stay_lose_shift),
        KucaAgent("Martell",    "Slučajno (60% S)",    lambda moja, protiv: st.slucajna_strategija(moja, protiv, 0.60)),
        KucaAgent("Greyjoy",    "Sumnjivi TFT",        st.sumnjivi_tit_for_tat),
        KucaAgent("Frey",       "JOSS (10% I)",        lambda moja, protiv: st.joss(moja, protiv, p_izdaje_nakon_suradnje=0.10)),

        KucaAgent("Lannister",  "Uvijek izdaja",       st.uvijek_izdaj),
        KucaAgent("Bolton",     "Uvijek izdaja",       st.uvijek_izdaj),
        KucaAgent("Baratheon",  "Grim Trigger",        st.grim_trigger),

        KucaAgent("Targaryen",  "Učenje (ε=0.10)",     st.tit_for_tat, je_ucenje=True, epsilon=0.10),
    ]
    return agenti


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


def tekst_dogadjaja(d: Dogadjaj) -> str:
    if d.potez_a == "S" and d.potez_b == "S":
        return f"Savez: {d.a} ↔ {d.b}  (+{d.bod_a}/+{d.bod_b})"
    if d.potez_a == "I" and d.potez_b == "I":
        return f"Sukob: {d.a} ⚔ {d.b}  (+{d.bod_a}/+{d.bod_b})"
    # izdaja
    if d.potez_a == "I" and d.potez_b == "S":
        return f"Izdaja: {d.a} izdao {d.b}  (+{d.bod_a}/+{d.bod_b})"
    if d.potez_a == "S" and d.potez_b == "I":
        return f"Izdaja: {d.b} izdao {d.a}  (+{d.bod_a}/+{d.bod_b})"
    return f"{d.a} vs {d.b}: {d.potez_a}/{d.potez_b}"


def main() -> None:
    pygame.init()
    pygame.display.set_caption("GoT Axelrod VAS — Mapa")

    W, H = 1200, 700
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Segoe UI", 18)
    font_small = pygame.font.SysFont("Segoe UI", 16)
    font_title = pygame.font.SysFont("Segoe UI", 22)
    font_mono = pygame.font.SysFont("Consolas", 16)

    # Layout
    panel_w = 360
    mapa_rect = pygame.Rect(0, 0, W - panel_w, H)
    panel_rect = pygame.Rect(W - panel_w, 0, panel_w, H)

    # Stanje simulacije
    def reset() -> Tuple[List[KucaAgent], Simulacija, int, List[str], Dict[Tuple[str, str], Dogadjaj], List[str], int, int, float]:
        agenti_local = kreiraj_agente()
        sim_local = Simulacija(MATRICA_ISPLATE)
        sezona_local = 0
        kuce = [a.naziv for a in agenti_local]
        zadnji_ishodi: Dict[Tuple[str, str], Dogadjaj] = {}
        log: List[str] = []
        total_suradnje = 0
        total_poteza = 0
        last_season_pct = 0.0
        return agenti_local, sim_local, sezona_local, kuce, zadnji_ishodi, log, total_suradnje, total_poteza, last_season_pct

    agenti, sim, sezona, kuce, zadnji_ishodi, log, total_suradnje, total_poteza, last_season_pct = reset()

    pozicije = pozicioniraj_kuce(
        kuce,
        cx=mapa_rect.centerx,
        cy=mapa_rect.centery,
        radius=min(mapa_rect.width, mapa_rect.height) // 3
    )

    pauza = True
    brzina = 1.0  # sezona u sekundi
    akumulirano = 0.0

    # za "blink" efekat aktivnog događaja u sezoni
    aktivne_veze: List[Tuple[str, str]] = []

    def odigraj_jednu_sezonu():
        nonlocal sezona, aktivne_veze, total_suradnje, total_poteza, last_season_pct
        sezona += 1
        aktivne_veze = []
        season_suradnje = 0
        season_poteza = 0

        dog = sim.odigraj_sezonu_sa_dogadjajima(agenti)
        # uzmi zadnje ishode po paru (za crtanje veza)
        for (a, b, pa, pb, ba, bb) in dog:
            key = tuple(sorted((a, b)))
            zadnji_ishodi[key] = Dogadjaj(a=a, b=b, potez_a=pa, potez_b=pb, bod_a=ba, bod_b=bb)
            aktivne_veze.append(key)
            season_suradnje += (1 if pa == "S" else 0) + (1 if pb == "S" else 0)
            season_poteza += 2

        total_suradnje += season_suradnje
        total_poteza += season_poteza
        if season_poteza > 0:
            last_season_pct = 100.0 * season_suradnje / season_poteza
        else:
            last_season_pct = 0.0

        # log: uzmi par najzanimljivijih događaja (npr. izdaje) + 3 random
        dogadjaji = [zadnji_ishodi[tuple(sorted((d[0], d[1])))] for d in dog]
        izdaje = [d for d in dogadjaji if (d.potez_a, d.potez_b) in [("I", "S"), ("S", "I")]]
        # najnoviji log na vrh
        for d in (izdaje[:4] + dogadjaji[:3]):
            log.insert(0, f"[S{sezona}] {tekst_dogadjaja(d)}")
        del log[60:]  # ograniči log

    def nacrtaj():
        screen.fill(BOJA_POZADINA)

        # Panel
        pygame.draw.rect(screen, BOJA_PANEL, panel_rect)

        # Naslov
        t = font_title.render("GoT Axelrod — Mapa", True, BOJA_TEKST)
        screen.blit(t, (panel_rect.x + 16, 14))
        sub = font_small.render(f"Sezona: {sezona} | {'PAUZA' if pauza else 'RUN'} | brzina: {brzina:.1f}/s", True, BOJA_SUBT)
        screen.blit(sub, (panel_rect.x + 16, 44))

        # Kontrole
        ctrl1 = font_small.render("SPACE: pauza  |  N: step  |  +/-: brzina", True, BOJA_SUBT)
        ctrl2 = font_small.render("R: reset  |  S: screenshot  |  ESC: izlaz", True, BOJA_SUBT)
        screen.blit(ctrl1, (panel_rect.x + 16, 70))
        screen.blit(ctrl2, (panel_rect.x + 16, 92))

        # Legenda boja 
        legend_x = 16
        legend_y = 16
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

        # Veze (mapa)
        # crtaj sve parove za koje imamo zadnji ishod
        for key, d in zadnji_ishodi.items():
            a, b = key
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

        # Čvorovi kuća
        mx, my = pygame.mouse.get_pos()
        hovered = None
        for a in agenti:
            x, y = pozicije[a.naziv]
            dist = (mx - x) ** 2 + (my - y) ** 2
            if dist <= (RADIUS_CVOR + 6) ** 2:
                hovered = a.naziv

        for a in agenti:
            x, y = pozicije[a.naziv]
            col = BOJA_CVOR_AKT if a.naziv == hovered else BOJA_CVOR
            pygame.draw.circle(screen, col, (x, y), RADIUS_CVOR)
            outline_col = BOJA_CVOR_UCENJE if a.je_ucenje else (10, 10, 10)
            outline_w = 3 if a.je_ucenje else 2
            pygame.draw.circle(screen, outline_col, (x, y), RADIUS_CVOR, outline_w)

            if a.je_ucenje:
                t = pygame.time.get_ticks() / 1000.0
                pulse = int(4 * (0.5 + 0.5 * math.sin(t * 4.0)))
                pygame.draw.circle(screen, BOJA_CVOR_UCENJE, (x, y), RADIUS_CVOR + 6 + pulse, 2)

            label = font_small.render(a.naziv, True, BOJA_TEKST)
            screen.blit(label, (x - label.get_width() // 2, y + RADIUS_CVOR + 6))

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

        # Sažetak sezone
        summary_y = 118
        total_pct = 100.0 * total_suradnje / total_poteza if total_poteza > 0 else 0.0
        sum1 = font_small.render(f"Suradnja (zadnja sezona): {last_season_pct:.1f}%", True, BOJA_SUBT)
        sum2 = font_small.render(f"Suradnja (ukupno): {total_pct:.1f}%", True, BOJA_SUBT)
        screen.blit(sum1, (panel_rect.x + 16, summary_y))
        screen.blit(sum2, (panel_rect.x + 16, summary_y + 20))

        # Leaderboard
        y0 = 170
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


        pygame.display.flip()

    # Main loop
    last = time.time()
    while True:
        dt = time.time() - last
        last = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                elif event.key == pygame.K_SPACE:
                    pauza = not pauza
                elif event.key == pygame.K_n:
                    odigraj_jednu_sezonu()
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    brzina = min(20.0, brzina + 0.5)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    brzina = max(0.5, brzina - 0.5)
                elif event.key == pygame.K_r:
                    agenti, sim, sezona, kuce, zadnji_ishodi, log, total_suradnje, total_poteza, last_season_pct = reset()
                    pozicije = pozicioniraj_kuce(
                        kuce,
                        cx=mapa_rect.centerx,
                        cy=mapa_rect.centery,
                        radius=min(mapa_rect.width, mapa_rect.height) // 3
                    )
                elif event.key == pygame.K_s:
                    os.makedirs("screenshots", exist_ok=True)
                    filename = os.path.join("screenshots", f"mapa_sezona_{sezona}.png")
                    pygame.image.save(screen, filename)

        if not pauza:
            akumulirano += dt
            period = 1.0 / brzina
            if akumulirano >= period:
                akumulirano = 0.0
                odigraj_jednu_sezonu()

        nacrtaj()
        clock.tick(60)


if __name__ == "__main__":
    main()
