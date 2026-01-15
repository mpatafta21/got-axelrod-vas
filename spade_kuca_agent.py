"""SPADE agent representing a single house with a fixed strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Literal
import random

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import json

import strategije as st

Potez = Literal["S", "I"]
Stanje = Literal["START", "S", "I"]


STRATEGIJE = {
    "uvijek_suradjuj": st.uvijek_suradjuj,
    "uvijek_izdaj": st.uvijek_izdaj,
    "always_defect": st.uvijek_izdaj,
    "tit_for_tat": st.tit_for_tat,
    "learning_tft": st.tit_for_tat,
    "sumnjivi_tit_for_tat": st.sumnjivi_tit_for_tat,
    "tit_for_two_tats": st.tit_for_two_tats,
    "grim_trigger": st.grim_trigger,
    "joss": st.joss,
    "win_stay_lose_shift": st.win_stay_lose_shift,
    "slucajna_0_60": lambda moja, protiv: st.slucajna_strategija(moja, protiv, 0.60),
}


@dataclass
class KucaKonfig:
    naziv: str
    strategija_id: str
    je_ucenje: bool = False
    epsilon: float = 0.10
    alpha: float = 0.20
    gamma: float = 0.90
    p_suradnje: float = 0.60
    p_joss: float = 0.10


class KucaSpadeAgent(Agent):
    """One SPADE agent per house; replies to REQUEST_MOVE with "S" or "I"."""

    def __init__(self, jid: str, password: str, config: KucaKonfig):
        super().__init__(jid, password)
        self.config = config
        if config.strategija_id == "slucajna_0_60":
            self._strategija = lambda moja, protiv: st.slucajna_strategija(moja, protiv, config.p_suradnje)
        elif config.strategija_id == "joss":
            self._strategija = lambda moja, protiv: st.joss(moja, protiv, p_izdaje_nakon_suradnje=config.p_joss)
        else:
            self._strategija = STRATEGIJE[config.strategija_id]
        self._povijest: Dict[str, Tuple[List[Potez], List[Potez]]] = {}
        self._q: Dict[str, Dict[Stanje, Dict[Potez, float]]] = {}
        self._last_state: Dict[str, Stanje] = {}
        self._last_action: Dict[str, Potez] = {}
        self._beh_counts: Dict[str, Dict[Stanje, Dict[Potez, int]]] = {}

    def _history_for(self, protivnik: str) -> Tuple[List[Potez], List[Potez]]:
        return self._povijest.get(protivnik, ([], []))

    def _record(self, protivnik: str, moj: Potez, njihov: Potez) -> None:
        moja, protivnikova = self._history_for(protivnik)
        moja.append(moj)
        protivnikova.append(njihov)
        self._povijest[protivnik] = (moja, protivnikova)

    def _inicijaliziraj_q(self, protivnik: str) -> None:
        if protivnik not in self._q:
            self._q[protivnik] = {
                "START": {"S": 0.0, "I": 0.0},
                "S": {"S": 0.0, "I": 0.0},
                "I": {"S": 0.0, "I": 0.0},
            }
        if protivnik not in self._beh_counts:
            self._beh_counts[protivnik] = {
                "START": {"S": 0, "I": 0},
                "S": {"S": 0, "I": 0},
                "I": {"S": 0, "I": 0},
            }

    def _odaberi_potez_ucenje(self, protivnik: str) -> Potez:
        self._inicijaliziraj_q(protivnik)
        moja, protivnikova = self._history_for(protivnik)
        stanje: Stanje = protivnikova[-1] if protivnikova else "START"
        self._last_state[protivnik] = stanje

        if random.random() < self.config.epsilon:
            potez: Potez = random.choice(["S", "I"])
        else:
            q_state = self._q[protivnik][stanje]
            if q_state["S"] == q_state["I"]:
                potez = "S"
            else:
                potez = "S" if q_state["S"] > q_state["I"] else "I"

        self._last_action[protivnik] = potez
        self._beh_counts[protivnik][stanje][potez] += 1
        return potez

    def _azuriraj_ucenje(self, protivnik: str, nagrada: float, njihov: Potez) -> None:
        if not self.config.je_ucenje:
            return
        if protivnik not in self._last_state or protivnik not in self._last_action:
            return

        self._inicijaliziraj_q(protivnik)
        stanje = self._last_state[protivnik]
        akcija = self._last_action[protivnik]
        sljedece: Stanje = njihov

        q_state = self._q[protivnik][stanje][akcija]
        q_next = self._q[protivnik][sljedece]
        max_next = max(q_next["S"], q_next["I"])
        alfa = self.config.alpha
        gamma = self.config.gamma
        novo = q_state + alfa * (nagrada + gamma * max_next - q_state)
        self._q[protivnik][stanje][akcija] = novo

    def _learning_snapshot(self):
        snapshot = {}
        for protivnik, q_states in self._q.items():
            s_pref = _pref_from_q(q_states.get("S", {}))
            i_pref = _pref_from_q(q_states.get("I", {}))
            s_counts = self._beh_counts.get(protivnik, {}).get("S", {"S": 0, "I": 0})
            i_counts = self._beh_counts.get(protivnik, {}).get("I", {"S": 0, "I": 0})
            total_s = s_counts["S"] + s_counts["I"]
            total_i = i_counts["S"] + i_counts["I"]
            pct_s_after_s = (s_counts["S"] / total_s) * 100.0 if total_s > 0 else 0.0
            pct_i_after_i = (i_counts["I"] / total_i) * 100.0 if total_i > 0 else 0.0
            snapshot[protivnik] = {
                "pref_after_s": s_pref,
                "pref_after_i": i_pref,
                "pct_s_after_s": pct_s_after_s,
                "pct_i_after_i": pct_i_after_i,
            }
        return snapshot

    class MoveBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if not msg:
                return

            if msg.body:
                try:
                    payload = json.loads(msg.body)
                except json.JSONDecodeError:
                    payload = None

                if isinstance(payload, dict):
                    msg_type = payload.get("type")
                    if msg_type == "UPDATE_RESULT":
                        protivnik = payload.get("opponent")
                        moj = payload.get("my")
                        njihov = payload.get("their")
                        nagrada = payload.get("reward")
                        if protivnik and moj and njihov:
                            self.agent._record(protivnik, moj, njihov)
                            if nagrada is not None:
                                self.agent._azuriraj_ucenje(protivnik, float(nagrada), njihov)
                        return
                    if msg_type == "REQUEST_MOVE":
                        meta = msg.metadata or {}
                        if (
                            meta.get("performative") != "request"
                            or meta.get("protocol") != "axelrod-move-v1"
                            or "conversation-id" not in meta
                        ):
                            return
                        protivnik = payload.get("opponent", str(msg.sender).split("/")[0])
                        moja, protivnikova = self.agent._history_for(protivnik)
                        if self.agent.config.je_ucenje:
                            potez = self.agent._odaberi_potez_ucenje(protivnik)
                        else:
                            potez = self.agent._strategija(moja, protivnikova)
                        print(f"[{self.agent.config.naziv}] potez protiv {protivnik}: {potez}")

                        reply = Message(to=str(msg.sender))
                        reply.metadata = {
                            "performative": "inform",
                            "protocol": "axelrod-move-v1",
                            "conversation-id": meta["conversation-id"],
                        }
                        reply.body = json.dumps({"type": "MOVE", "move": potez})
                        await self.send(reply)
                        return
                    if msg_type == "REQUEST_LEARNING_STATS":
                        meta = msg.metadata or {}
                        if (
                            meta.get("performative") != "request"
                            or meta.get("protocol") != "axelrod-learning-v1"
                            or "conversation-id" not in meta
                        ):
                            return
                        reply = Message(to=str(msg.sender))
                        reply.metadata = {
                            "performative": "inform",
                            "protocol": "axelrod-learning-v1",
                            "conversation-id": meta["conversation-id"],
                        }
                        reply.body = json.dumps(
                            {"type": "LEARNING_STATS", "stats": self.agent._learning_snapshot()}
                        )
                        await self.send(reply)
                        return

            if msg.body != "REQUEST_MOVE":
                return

            protivnik = str(msg.sender).split("/")[0]
            moja, protivnikova = self.agent._history_for(protivnik)
            potez = self.agent._strategija(moja, protivnikova)

            reply = Message(to=str(msg.sender))
            reply.metadata = {"performative": "inform"}
            reply.body = potez
            await self.send(reply)

    async def setup(self):
        self.add_behaviour(self.MoveBehaviour())


def _pref_from_q(q_state):
    s = q_state.get("S", 0.0)
    i = q_state.get("I", 0.0)
    if s == i:
        return "S"
    return "S" if s > i else "I"
