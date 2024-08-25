import logging

from services.common.aries_agent import AriesAgent

logging.basicConfig(level=logging.WARNING)
LOGGER = logging.getLogger(__name__)


class Agent(AriesAgent):
    def __init__(
            self,
            ident: str,
            genesis_data: str,
            seed: str = "discovery00000000000000000000000",
            http_port: int = 8020,
            admin_port: int = 8021,
            no_auto: bool = False,
            aip: int = 20,
            **kwargs,
    ):
        super().__init__(
            ident,
            http_port,
            admin_port,
            genesis_data=genesis_data,
            no_auto=no_auto,
            seed=seed,
            aip=aip,
            **kwargs,
        )
        self.log_callback = None
        self.log_cache = []

    def set_log_callback(self, log_callback):
        self.log_callback = log_callback
        for log in self.log_cache:
            self.log_msg(log)
        self.log_cache = []

    def log_msg(self, msg, color=None):
        if isinstance(msg, list):
            msg = str(" ".join(msg))#.rstrip()
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

