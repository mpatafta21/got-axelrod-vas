import asyncio
import json
import spade
import time
import threading
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
        "config": KucaKonfig("Targaryen", "tit_for_tat")
    }
]

ORCHESTRATOR_JID = "orchestrator@localhost"
ORCHESTRATOR_PASSWORD = "orchestrator"
MOVE_TIMEOUT_S = 8.0

# ---------- HELPERS ----------
async def odigraj_sezonu(behaviour, kuca_agenti):
    dogadjaji = []
    bodovi = {a.config.naziv: 0 for a in kuca_agenti}
    pending_moves: dict[str, list[str]] = {}

    for a, b in combinations(kuca_agenti, 2):
        await _posalji_request(behaviour, a, b)
        await _posalji_request(behaviour, b, a)

        potez_a = await _cekaj_potez(behaviour, str(a.jid), pending_moves)
        potez_b = await _cekaj_potez(behaviour, str(b.jid), pending_moves)

        bod_a, bod_b = izracunaj_isplatu(DEFAULT_MATRICA_ISPLATE, potez_a, potez_b)
        bodovi[a.config.naziv] += bod_a
        bodovi[b.config.naziv] += bod_b
        dogadjaji.append((a.config.naziv, b.config.naziv, potez_a, potez_b, bod_a, bod_b))

        await _posalji_update(behaviour, a, b, potez_a, potez_b)
        await _posalji_update(behaviour, b, a, potez_b, potez_a)

    return {"dogadjaji": dogadjaji, "bodovi": bodovi}


async def _posalji_request(behaviour, agent, protivnik):
    msg = Message(to=str(agent.jid))
    msg.body = json.dumps({
        "type": "REQUEST_MOVE",
        "opponent": str(protivnik.jid),
    })
    await behaviour.send(msg)


async def _cekaj_potez(behaviour, sender_jid: str, pending_moves: dict[str, list[str]]):
    start = time.monotonic()
    while True:
        if sender_jid in pending_moves and pending_moves[sender_jid]:
            return pending_moves[sender_jid].pop(0)
        if time.monotonic() - start > MOVE_TIMEOUT_S:
            raise TimeoutError(f"Timeout čekanja poteza od {sender_jid}")
        msg = await behaviour.receive(timeout=1)
        if not msg:
            continue
        sender = str(msg.sender).split("/")[0]
        if sender != sender_jid:
            data = json.loads(msg.body)
            if data.get("type") == "MOVE":
                pending_moves.setdefault(sender, []).append(data["move"])
            continue
        data = json.loads(msg.body)
        if data.get("type") == "MOVE":
            return data["move"]


async def _posalji_update(behaviour, agent, protivnik, moj, njihov):
    msg = Message(to=str(agent.jid))
    msg.body = json.dumps({
        "type": "UPDATE_RESULT",
        "opponent": str(protivnik.jid),
        "my": moj,
        "their": njihov,
    })
    await behaviour.send(msg)

# ---------- ORCHESTRATOR ----------
class SpadeOrchestrator:
    def __init__(self):
        self.agenti = []

    async def pokreni_agente(self, auto_register: bool):
        for k in KUCe:
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

            result = await odigraj_sezonu(self, self.agent.kuca_agenti)
            await self.agent.result_q.put(result)

    async def setup(self):
        if self.mode == "cli":
            self.add_behaviour(self.DuelBehaviour())
        if self.mode == "session":
            self.add_behaviour(self.SeasonBehaviour())


class SpadeSession:
    def __init__(self, auto_register: bool):
        self.auto_register = auto_register
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

    def play_season_sync(self):
        if not self._loop or not self._request_q or not self._result_q:
            raise RuntimeError("SPADE session is not started.")
        asyncio.run_coroutine_threadsafe(
            self._request_q.put({"type": "PLAY_SEASON"}), self._loop
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

        orchestrator = SpadeOrchestrator()
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
