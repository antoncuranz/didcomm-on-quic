import asyncio
import json
import logging
import random
import socket

from services.common.webhook_agent_base import WebhookAgentBase

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)
BROADCAST_PORT = 8023


class Agent(WebhookAgentBase):
    def __init__(
            self,
            ident: str,
            genesis_data: str,
            external_host: str = "localhost",
            http_port: int = 8020,
            broadcast_invitations: bool = False,
            receive_invitations: bool = False,
            create_schemas: bool = False
    ):
        super().__init__(ident, http_port, external_host=external_host, genesis_data=genesis_data, seed=ident.zfill(32))

        self.broadcast_invitations = broadcast_invitations
        self.receive_invitations = receive_invitations
        self.create_schemas = create_schemas

        self.cred_def_type = None
        self.cred_def_reg = None

    async def initialize(self):
        await self.register_did("http://test.bcovrin.vonx.io") # TODO
        self.log_msg("Created public DID")

        # with log_timer("Startup duration:"):
        await self.listen_webhooks(self.http_port + 2)
        await self.start_process()

        if self.create_schemas:
            version = format("%d.%d.%d"
                % (random.randint(1, 101), random.randint(1, 101), random.randint(1, 101))
            )
            self.cred_def_type = await self.register_schema_and_creddef(
                "car-type", version, ["make", "model", "year"]
            )
            self.cred_def_reg = await self.register_schema_and_creddef(
                "car-registration", version, ["registration", "expiration"]
            )

        self.log_msg("Agent initialized")

        if self.broadcast_invitations:
            asyncio.create_task(self._broadcast_invitations())
            self.log_msg("Started broadcasting invitations on port: " + str(BROADCAST_PORT))
        elif self.receive_invitations:
            asyncio.create_task(self._receive_invitations())
            self.log_msg("Started receiving invitations on port: " + str(BROADCAST_PORT))

    async def _broadcast_invitations(self):
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        broadcast_sock.setblocking(False)
        loop = asyncio.get_event_loop()

        invitation = await self.get_invite() # TODO: goal_code?
        self.log_msg(invitation)

        while True:
            await loop.sock_sendto(broadcast_sock, json.dumps(invitation["invitation"]).encode(), ("255.255.255.255", BROADCAST_PORT))
            await asyncio.sleep(5)

    async def _receive_invitations(self):
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        broadcast_sock.setblocking(False)
        broadcast_sock.bind(("", BROADCAST_PORT))
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
