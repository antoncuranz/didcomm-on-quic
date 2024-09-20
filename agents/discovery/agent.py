import asyncio
import json
import logging
import socket

from agents.common.webhook_agent_base import WebhookAgentBase

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)
BROADCAST_PORT = 8023


class Agent(WebhookAgentBase):
    def __init__(
            self,
            ident: str,
            ledger_url: str,
            external_host: str = "localhost",
            http_port: int = 8020,
            broadcast_invitations: bool = False,
    ):
        super().__init__(ident, http_port, external_host=external_host, ledger_url=ledger_url, seed=ident.zfill(32))

        self.broadcast_invitations = broadcast_invitations

        self.cred_def_type = None
        self.cred_def_reg = None

    async def initialize(self):
        await super().initialize()
        self.log_msg("Agent initialized")

        if self.broadcast_invitations:
            asyncio.create_task(self._broadcast_invitations())
            self.log_msg("Started broadcasting invitations on port: " + str(BROADCAST_PORT))

    async def _broadcast_invitations(self):
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        broadcast_sock.setblocking(False)
        loop = asyncio.get_event_loop()

        invitation = await self.get_invite()
        self.log_msg(invitation)

        while True:
            await loop.sock_sendto(broadcast_sock, json.dumps(invitation["invitation"]).encode(), ("255.255.255.255", BROADCAST_PORT))
            await asyncio.sleep(5)
