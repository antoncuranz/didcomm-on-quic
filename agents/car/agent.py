import asyncio
import json
import logging
import socket

from agents.common.webhook_agent_base import WebhookAgentBase

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)
LISTEN_PORT = 8023


class Agent(WebhookAgentBase):
    def __init__(
            self,
            ident: str,
            ledger_url: str,
            transport_type: str, # must be in ["http", "https", "http3"]
            external_host: str = "localhost",
            http_port: int = 8020,
            receive_invitations: bool = False,
            force_close: bool = False,
            keepalive_timeout=None
    ):
        super().__init__(ident, http_port, transport_type, external_host=external_host, ledger_url=ledger_url, seed=ident.zfill(32), force_close=force_close, keepalive_timeout=keepalive_timeout)
        self.receive_invitations = receive_invitations

    async def initialize(self):
        await super().initialize()
        self.log_msg("Agent initialized")

        if self.receive_invitations:
            asyncio.create_task(self._receive_invitations())
            self.log_msg("Started receiving invitations on port: " + str(LISTEN_PORT))

    async def _receive_invitations(self):
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        broadcast_sock.setblocking(False)
        broadcast_sock.bind(("", LISTEN_PORT))
        loop = asyncio.get_event_loop()

        received = []

        while True:
            data = await loop.sock_recv(broadcast_sock, 1024)
            parsed = json.loads(data.decode())
            if is_invitation_with_label(parsed, "service-discovery") and parsed["@id"] not in received:
                self.log_msg("Received invitation")
                await self.receive_invite(parsed)
                received.append(parsed["@id"])


def is_invitation_with_label(invitation, label):
    if not invitation.keys() & {"@type", "@id", "label"}:
        return False

    if invitation["@type"] != "https://didcomm.org/out-of-band/1.1/invitation":
        return False

    return True #invitation["label"] == label
