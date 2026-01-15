import asyncio
import json
import spade
import time
import uuid
import threading
import random
from typing import Optional
from itertools import combinations
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

from spade_kuca_agent import KucaSpadeAgent, KucaKonfig
from engine import DEFAULT_MATRICA_ISPLATE, izracunaj_isplatu


# ---------- KONFIGURACIJA KUĆA ----------
KUCe = [
    {
        "jid": "stark@localhost",
        "password": "stark",
        "config": KucaKonfig("Stark", "tit_for_tat")
    },
    {
        "jid": "arryn@localhost",
        "password": "arryn",
        "config": KucaKonfig("Arryn", "tit_for_tat")
    },
    {
        "jid": "tully@localhost",
        "password": "tully",
        "config": KucaKonfig("Tully", "tit_for_two_tats")
    },
    {
        "jid": "mormont@localhost",
        "password": "mormont",
        "config": KucaKonfig("Mormont", "uvijek_suradjuj")
    },
    {
        "jid": "tyrell@localhost",
        "password": "tyrell",
        "config": KucaKonfig("Tyrell", "win_stay_lose_shift")
    },
    {
        "jid": "martell@localhost",
        "password": "martell",
        "config": KucaKonfig("Martell", "slucajna_0_60")
    },
    {
        "jid": "greyjoy@localhost",
        "password": "greyjoy",
        "config": KucaKonfig("Greyjoy", "sumnjivi_tit_for_tat")
    },
    {
        "jid": "frey@localhost",
        "password": "frey",
        "config": KucaKonfig("Frey", "joss")
    },
    {
        "jid": "lannister@localhost",
        "password": "lannister",
        "config": KucaKonfig("Lannister", "always_defect")
    },
    {
        "jid": "bolton@localhost",
        "password": "bolton",
        "config": KucaKonfig("Bolton", "always_defect")
    },
    {
        "jid": "baratheon@localhost",
        "password": "baratheon",
        "config": KucaKonfig("Baratheon", "grim_trigger")
    },
    {
        "jid": "targaryen@localhost",
        "password": "targaryen",
        "config": KucaKonfig("Targaryen", "learning_tft", je_ucenje=True, epsilon=0.10)
    }
]

ORCHESTRATOR_JID = "orchestrator@localhost"
ORCHESTRATOR_PASSWORD = "orchestrator"
MOVE_TIMEOUT_S = 8.0

# ---------- HELPERS ----------
async def odigraj_sezonu(behaviour, kuca_agenti, active_names=None, noise_rate=0.0):
    dogadjaji = []
    if active_names is None:
        active_names = {a.config.naziv for a in kuca_agenti}
    else:
        active_names = set(active_names)
    aktivni = [a for a in kuca_agenti if a.config.naziv in active_names]
    bodovi = {a.config.naziv: 0 for a in aktivni}
    pending_moves: dict[str, str] = {}
    learning_stats: dict[str, dict[str, dict[str, dict[str, float]]]] = {}

    for a, b in combinations(aktivni, 2):
        conv_a = await _posalji_request(behaviour, a, b)
        conv_b = await _posalji_request(behaviour, b, a)

        potez_a = await _cekaj_potez(behaviour, conv_a, pending_moves)
        potez_b = await _cekaj_potez(behaviour, conv_b, pending_moves)

        exec_a = _apply_noise(potez_a, noise_rate)
        exec_b = _apply_noise(potez_b, noise_rate)

        bod_a, bod_b = izracunaj_isplatu(DEFAULT_MATRICA_ISPLATE, exec_a, exec_b)
        bodovi[a.config.naziv] += bod_a
        bodovi[b.config.naziv] += bod_b
        dogadjaji.append((a.config.naziv, b.config.naziv, exec_a, exec_b, bod_a, bod_b))

        if a.config.je_ucenje:
            _update_learning_stats(learning_stats, a.config.naziv, b.config.naziv, exec_a, bod_a)
        if b.config.je_ucenje:
            _update_learning_stats(learning_stats, b.config.naziv, a.config.naziv, exec_b, bod_b)

        await _posalji_update(behaviour, a, b, exec_a, exec_b, bod_a)
        await _posalji_update(behaviour, b, a, exec_b, exec_a, bod_b)

    learning_stats.update(await _request_learning_stats(behaviour, aktivni))

    return {"dogadjaji": dogadjaji, "bodovi": bodovi, "learning_stats": learning_stats}


def _update_learning_stats(stats, agent_name, protivnik, moj, nagrada):
    if agent_name not in stats:
        stats[agent_name] = {}
    if protivnik not in stats[agent_name]:
        stats[agent_name][protivnik] = {
            "S": {"n": 0.0, "avg": 0.0},
            "I": {"n": 0.0, "avg": 0.0},
        }
    zapis = stats[agent_name][protivnik][moj]
    n_staro = zapis["n"]
    avg_staro = zapis["avg"]
    n_novo = n_staro + 1.0
    avg_novo = avg_staro + (nagrada - avg_staro) / n_novo
    zapis["n"] = n_novo
    zapis["avg"] = avg_novo


def _apply_noise(potez, noise_rate):
    if noise_rate <= 0.0:
        return potez
    if random.random() < noise_rate:
        return "I" if potez == "S" else "S"
    return potez

async def _request_learning_stats(behaviour, kuca_agenti):
    learning = [a for a in kuca_agenti if getattr(a.config, "je_ucenje", False)]
    if not learning:
        return {}
    jid_to_name = {str(a.jid): a.config.naziv for a in kuca_agenti}
    pending = {}
    stats = {}
    for a in learning:
        conv = await _posalji_learning_request(behaviour, a)
        pending[conv] = a.config.naziv
    while pending:
        msg = await behaviour.receive(timeout=5)
        if not msg:
            break
        meta = msg.metadata or {}
        if (
            meta.get("performative") != "inform"
            or meta.get("protocol") != "axelrod-learning-v1"
            or "conversation-id" not in meta
        ):
            continue
        conv_id = meta["conversation-id"]
        if conv_id not in pending:
            continue
        data = json.loads(msg.body)
        if data.get("type") != "LEARNING_STATS":
            continue
        agent_name = pending.pop(conv_id)
        agent_stats = stats.setdefault(agent_name, {})
        raw = data.get("stats", {})
        for protivnik, vals in raw.items():
            protivnik_name = jid_to_name.get(protivnik, protivnik)
            entry = agent_stats.setdefault(
                protivnik_name,
                {"S": {"n": 0.0, "avg": 0.0}, "I": {"n": 0.0, "avg": 0.0}},
            )
            entry["pref_after_s"] = vals.get("pref_after_s", "-")
            entry["pref_after_i"] = vals.get("pref_after_i", "-")
            entry["pct_s_after_s"] = vals.get("pct_s_after_s", 0.0)
            entry["pct_i_after_i"] = vals.get("pct_i_after_i", 0.0)
    return stats


async def _posalji_request(behaviour, agent, protivnik):
    conv_id = str(uuid.uuid4())
    msg = Message(to=str(agent.jid))
    msg.metadata = {
        "performative": "request",
        "protocol": "axelrod-move-v1",
        "conversation-id": conv_id,
    }
    msg.body = json.dumps({
        "type": "REQUEST_MOVE",
        "opponent": str(protivnik.jid),
    })
    await behaviour.send(msg)
    return conv_id


async def _posalji_learning_request(behaviour, agent):
    conv_id = str(uuid.uuid4())
    msg = Message(to=str(agent.jid))
    msg.metadata = {
        "performative": "request",
        "protocol": "axelrod-learning-v1",
        "conversation-id": conv_id,
    }
    msg.body = json.dumps({"type": "REQUEST_LEARNING_STATS"})
    await behaviour.send(msg)
    return conv_id


async def _cekaj_potez(behaviour, conv_id: str, pending_moves: dict[str, str]):
    start = time.monotonic()
    while True:
        if conv_id in pending_moves:
            return pending_moves.pop(conv_id)
        if time.monotonic() - start > MOVE_TIMEOUT_S:
            raise TimeoutError(f"Timeout čekanja poteza za conversation-id {conv_id}")
        msg = await behaviour.receive(timeout=1)
        if not msg:
            continue
        meta = msg.metadata or {}
        if (
            meta.get("performative") != "inform"
            or meta.get("protocol") != "axelrod-move-v1"
            or "conversation-id" not in meta
        ):
            continue
        data = json.loads(msg.body)
        if data.get("type") == "MOVE":
            pending_moves[meta["conversation-id"]] = data["move"]


async def _posalji_update(behaviour, agent, protivnik, moj, njihov, nagrada):
    msg = Message(to=str(agent.jid))
    msg.body = json.dumps({
        "type": "UPDATE_RESULT",
        "opponent": str(protivnik.jid),
        "my": moj,
        "their": njihov,
        "reward": nagrada,
    })
    await behaviour.send(msg)

# ---------- ORCHESTRATOR ----------
class SpadeOrchestrator:
    def __init__(self, kuca_defs=None):
        self.agenti = []
        self.kuca_defs = kuca_defs or KUCe

    async def pokreni_agente(self, auto_register: bool):
        for k in self.kuca_defs:
            agent = KucaSpadeAgent(
                jid=k["jid"],
                password=k["password"],
                config=k["config"]
            )
            await agent.start(auto_register=auto_register)
            self.agenti.append(agent)

        # kratko čekanje da se agenti spoje
        await asyncio.sleep(1)

    async def ugasi_agente(self):
        for agent in self.agenti:
            await agent.stop()

class OrchestratorAgent(Agent):
    def __init__(
        self,
        jid: str,
        password: str,
        kuca_agenti: list[KucaSpadeAgent],
        request_q: Optional[asyncio.Queue],
        result_q: Optional[asyncio.Queue],
        mode: str,
    ):
        super().__init__(jid, password)
        self.kuca_agenti = kuca_agenti
        self.request_q = request_q
        self.result_q = result_q
        self.mode = mode

    class DuelBehaviour(OneShotBehaviour):
        async def run(self):
            result = await odigraj_sezonu(self, self.agent.kuca_agenti)
            dog = result["dogadjaji"]
            bodovi = result["bodovi"]

            print("\nPokrećem turnir (svatko sa svakim)")
            for a, b, pa, pb, ba, bb in dog:
                print(f"ISHOD: {a} {pa} vs {b} {pb} -> {ba}/{bb}")

            print("\n=== Leaderboard ===")
            poredak = sorted(bodovi.items(), key=lambda x: x[1], reverse=True)
            for idx, (naziv, bod) in enumerate(poredak, start=1):
                print(f"{idx:>2}. {naziv:<10} {bod}")

            await self.agent.stop()

    class SeasonBehaviour(CyclicBehaviour):
        async def run(self):
            if not self.agent.request_q or not self.agent.result_q:
                return
            cmd = await self.agent.request_q.get()
            if not isinstance(cmd, dict) or cmd.get("type") != "PLAY_SEASON":
                return

            active_names = cmd.get("active_names")
            noise_rate = cmd.get("noise_rate", 0.0)
            result = await odigraj_sezonu(
                self, self.agent.kuca_agenti, active_names=active_names, noise_rate=noise_rate
            )
            await self.agent.result_q.put(result)

    async def setup(self):
        if self.mode == "cli":
            self.add_behaviour(self.DuelBehaviour())
        if self.mode == "session":
            self.add_behaviour(self.SeasonBehaviour())


class SpadeSession:
    def __init__(self, auto_register: bool, kuca_defs=None):
        self.auto_register = auto_register
        self.kuca_defs = kuca_defs
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._request_q = None
        self._result_q = None
        self._stop_event = None

    def start(self):
        if self._thread:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait()

    def stop(self):
        if not self._loop or not self._stop_event:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        self._thread.join(timeout=5)

    def play_season_sync(self, active_names=None, noise_rate=0.0):
        if not self._loop or not self._request_q or not self._result_q:
            raise RuntimeError("SPADE session is not started.")
        asyncio.run_coroutine_threadsafe(
            self._request_q.put(
                {"type": "PLAY_SEASON", "active_names": active_names, "noise_rate": noise_rate}
            ),
            self._loop
        ).result()
        fut = asyncio.run_coroutine_threadsafe(self._result_q.get(), self._loop)
        return fut.result()

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        loop.run_until_complete(self._runner())

    async def _runner(self):
        self._request_q = asyncio.Queue()
        self._result_q = asyncio.Queue()
        self._stop_event = asyncio.Event()

        orchestrator = SpadeOrchestrator(self.kuca_defs)
        await orchestrator.pokreni_agente(auto_register=self.auto_register)

        ctrl = OrchestratorAgent(
            ORCHESTRATOR_JID,
            ORCHESTRATOR_PASSWORD,
            orchestrator.agenti,
            self._request_q,
            self._result_q,
            mode="session",
        )
        await ctrl.start(auto_register=self.auto_register)

        self._ready.set()
        await self._stop_event.wait()

        await ctrl.stop()
        await orchestrator.ugasi_agente()


# ---------- MAIN ----------
async def main():
    orchestrator = SpadeOrchestrator()
    await orchestrator.pokreni_agente(auto_register=True)

    print("\n Pokrećem turnir (svatko sa svakim)")
    ctrl = OrchestratorAgent(
        ORCHESTRATOR_JID,
        ORCHESTRATOR_PASSWORD,
        orchestrator.agenti,
        None,
        None,
        mode="cli",
    )
    await ctrl.start(auto_register=True)
    while ctrl.is_alive():
        await asyncio.sleep(0.1)

    await asyncio.sleep(1)
    await orchestrator.ugasi_agente()


if __name__ == "__main__":
    spade.run(main())
