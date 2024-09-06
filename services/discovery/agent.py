import asyncio
import json
import logging
import random
import socket

from services.common.aries_agent import AriesAgent

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)
BROADCAST_PORT = 8023


class Agent(AriesAgent):
    def __init__(
            self,
            ident: str,
            genesis_data: str,
            http_port: int = 8020,
            broadcast_invitations: bool = False,
            receive_invitations: bool = False,
            create_schemas: bool = False,
            **kwargs,
    ):
        super().__init__( # TODO: move default options to AriesAgent
            ident,
            http_port,
            http_port+1,
            genesis_data=genesis_data,
            seed=ident.zfill(32),
            aip=20,
            public_did_connections=True,
            extra_args=[
                "--auto-accept-invites",
                "--auto-accept-requests",
                "--auto-store-credential",
                "--public-invites",
                "--invite-public",
                "--requests-through-public-did"
            ],
            **kwargs,
        )
        self.broadcast_invitations = broadcast_invitations
        self.receive_invitations = receive_invitations
        self.create_schemas = create_schemas

        # self.webhook_callbacks = {}
        self.log_callback = None
        self.log_cache = []
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

        invitation = await self.get_invite(label="service-discovery")
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

    def set_log_callback(self, log_callback):
        self.log_callback = log_callback
        for log in self.log_cache:
            self.log_msg(log)
        self.log_cache = []

    # def set_webhook_callback(self, topic, webhook_callback):
    #     self.webhook_callbacks[topic] = webhook_callback

    def log_msg(self, msg, color=None):
        if isinstance(msg, list):
            msg = str(" ".join(msg))
        else:
            msg = str(msg).rstrip()

        if color is not None:
            msg = color + msg

        if self.log_callback is None:
            self.log_cache.append(msg)
            return

        self.log_callback(msg)

    def log_json(self, *msg, **kwargs):
        pass


def is_invitation_with_label(invitation, label):
    if not invitation.keys() & {"@type", "@id", "label"}:
        return False

    if invitation["@type"] != "https://didcomm.org/out-of-band/1.1/invitation":
        return False

    return invitation["label"] == label
