"""SPADE agent representing a single house with a fixed strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Literal

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import json

import strategije as st

Potez = Literal["S", "I"]


STRATEGIJE = {
    "uvijek_suradjuj": st.uvijek_suradjuj,
    "uvijek_izdaj": st.uvijek_izdaj,
    "always_defect": st.uvijek_izdaj,
    "tit_for_tat": st.tit_for_tat,
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


class KucaSpadeAgent(Agent):
    """One SPADE agent per house; replies to REQUEST_MOVE with "S" or "I"."""

    def __init__(self, jid: str, password: str, config: KucaKonfig):
        super().__init__(jid, password)
        self.config = config
        self._strategija = STRATEGIJE[config.strategija_id]
        self._povijest: Dict[str, Tuple[List[Potez], List[Potez]]] = {}

    def _history_for(self, protivnik: str) -> Tuple[List[Potez], List[Potez]]:
        return self._povijest.get(protivnik, ([], []))

    def _record(self, protivnik: str, moj: Potez, njihov: Potez) -> None:
        moja, protivnikova = self._history_for(protivnik)
        moja.append(moj)
        protivnikova.append(njihov)
        self._povijest[protivnik] = (moja, protivnikova)

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
                        if protivnik and moj and njihov:
                            self.agent._record(protivnik, moj, njihov)
                        return
                    if msg_type == "REQUEST_MOVE":
                        if msg.metadata and msg.metadata.get("performative") != "request":
                            return
                        protivnik = payload.get("opponent", str(msg.sender).split("/")[0])
                        moja, protivnikova = self.agent._history_for(protivnik)
                        potez = self.agent._strategija(moja, protivnikova)
                        print(f"[{self.agent.config.naziv}] potez protiv {protivnik}: {potez}")

                        reply = Message(to=str(msg.sender))
                        reply.metadata = {"performative": "inform"}
                        reply.body = json.dumps({"type": "MOVE", "move": potez})
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
