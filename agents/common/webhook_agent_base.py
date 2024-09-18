import asyncio
import json

from aiohttp import (
    ClientRequest,
    web,
)

from agents.common.agent_base import AgentBase


class WebhookAgentBase(AgentBase):
    def __init__(
            self,
            ident: str,
            http_port: int,
            internal_host: str = "127.0.0.1",
            external_host: str = "localhost",
            ledger_url: str = None,
            genesis_data: str = None,
            seed: str = None,
            transport_type: str = "http",
            extra_args=None,
    ):
        super().__init__(ident, http_port, internal_host, external_host, ledger_url, genesis_data, seed, transport_type,
                         extra_args)

        self.webhook_port = None
        self.webhook_url = None
        self.webhook_site = None
        self.webhook_callbacks = {}

    async def initialize(self):
        await self.listen_webhooks(self.http_port + 2)
        await super().initialize()

    def set_webhook_callback(self, topic, webhook_callback):
        self.webhook_callbacks[topic] = webhook_callback

    def get_agent_args(self):
        result = super().get_agent_args()
        if self.webhook_url:
            result.append(("--webhook-url", self.webhook_url))
        return result

    async def terminate(self):
        # shut down web hooks first
        if self.webhook_site:
            await self.webhook_site.stop()
            await asyncio.sleep(0.5)

        await super().terminate()

    async def listen_webhooks(self, webhook_port):
        self.webhook_port = webhook_port
        self.webhook_url = f"http://{self.external_host}:{str(webhook_port)}/webhooks"
        app = web.Application()
        app.add_routes([web.post("/webhooks/topic/{topic}/", self._receive_webhook)])
        runner = web.AppRunner(app)
        await runner.setup()
        self.webhook_site = web.TCPSite(runner, "0.0.0.0", webhook_port)
        await self.webhook_site.start()
        self.log_msg("Started webhook listener on port: " + str(webhook_port))

    async def _receive_webhook(self, request: ClientRequest):
        topic = request.match_info["topic"].replace("-", "_")
        payload = await request.json()
        await self.handle_webhook(topic, payload, request.headers)
        return web.Response(status=200)

    async def handle_webhook(self, topic: str, payload, headers: dict):
        if topic != "webhook":  # would recurse
            handler = f"handle_{topic}"

            method = getattr(self, handler, None)
            if method:
                asyncio.get_event_loop().create_task(method(payload))
            else:
                self.log_msg(
                    f"Error: agent {self.ident} "
                    f"has no method {handler} "
                    f"to handle webhook on topic {topic}"
                )

            if topic in self.webhook_callbacks:
                self.webhook_callbacks[topic](payload)

    async def handle_problem_report(self, message):
        self.log_msg(
            f"Received problem report: {message['description']['en']}\n",
            source="stderr",
        )

    async def handle_endorse_transaction(self, message):
        self.log_msg("Received endorse transaction ...\n", source="stderr")

    async def handle_revocation_registry(self, message):
        reg_id = message.get("revoc_reg_id", "(undetermined)")
        self.log_msg(f"Revocation registry: {reg_id} state: {message['state']}")

    async def handle_mediation(self, message):
        self.log_msg("Received mediation message ...\n")

    async def handle_keylist(self, message):
        self.log_msg("Received handle_keylist message ...\n")
        self.log_msg(json.dumps(message))

    async def handle_out_of_band(self, message):
        self.log_msg("Received out of band webhook ...\n")

    async def handle_issue_credential_v2_0(self, message):
        self.log_msg("Received issue-credential-2.0 webhook ...\n")

    async def handle_registered_service(self, message):
        self.log_msg("Received registered_service message ...\n")
        self.log_msg(json.dumps(message))

    async def handle_queryservices_result(self, message):
        self.log_msg("Received queryservices_result message ...\n")
        self.log_msg(json.dumps(message))

    async def handle_fetchchunk_result(self, message):
        self.log_msg("Received fetchchunk_result message (chunk = {}; status = {})...\n".format(
            message["chunk"], message["status"]))

    async def handle_connections(self, message):
        # accept invitations with public did
        if message["rfc23_state"] == "invitation-received":
            await self.accept_invitation(message["connection_id"], self.did)
        elif message["rfc23_state"] == "request-received":
            await self.accept_conn_request(message["connection_id"], use_public_did=True)

        if "their_public_did" not in message:
            return
        their_did = message["their_did"] if "their_did" in message else message["their_public_did"]
        self.log_msg("Connection webhook: did = {}; state = {};".format(their_did, message["state"]))

    async def handle_present_proof_v2_0(self, message):
        self.log_msg("Present-Proof webhook: pres_ex_id = {}; state = {};".format(message["pres_ex_id"], message["state"]))
