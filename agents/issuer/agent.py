import logging
import random

from agents.common.webhook_agent_base import WebhookAgentBase

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)


class Agent(WebhookAgentBase):
    def __init__(
            self,
            ident: str,
            ledger_url: str,
            external_host: str = "localhost",
            http_port: int = 8020,
            create_schemas: bool = True
    ):
        super().__init__(ident, http_port, external_host=external_host, ledger_url=ledger_url, seed=ident.zfill(32))

        self.create_schemas = create_schemas
        self.cred_def_name = None
        self.cred_def_type = None
        self.cred_def_reg = None

    async def initialize(self):
        await super().initialize()

        if self.create_schemas:
            version = format("%d.%d.%d"
                % (random.randint(1, 101), random.randint(1, 101), random.randint(1, 101))
            )
            self.cred_def_name = await self.register_schema_and_creddef(
                "name", version, ["first_name", "last_name"]
            )
            self.cred_def_type = await self.register_schema_and_creddef(
                "car-type", version, ["make", "model", "year"]
            )
            self.cred_def_reg = await self.register_schema_and_creddef(
                "car-registration", version, ["registration", "expiration"]
            )

        self.log_msg("Agent initialized")
