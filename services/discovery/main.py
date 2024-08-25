import asyncio
import logging
import os

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, TabbedContent, TabPane, RichLog

from .agent import Agent
from services.common.aries_agent import fetch_genesis_txns

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

ROWS = [
    ("DID", "Service", "Registration", "Manufacturer", "Expires"),
    ("did:indy:xyz", "FRONT_CAM_STREAM", "(D) B-AB 1234", "Daimler", "(timestamp)"),
    ("did:indy:abc", "FRONT_CAM_STREAM", "UNVERIFIED", "UNVERIFIED", "(timestamp)"),
]


class DiscoveryService(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent
        self.table = None
        self.rich_log = None

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="logs"):
            with TabPane("Services", id="services"):
                yield DataTable(cursor_type="row")
            with TabPane("Logs", id="logs"):
                yield RichLog(highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        self.title = "Discovery Service"
        self.sub_title = "IP: 0.0.0.0 Port: 1234"
        self.query_one(Header).tall = True

        self.table = self.query_one(DataTable)
        self.table.add_columns(*ROWS[0])
        self.table.add_rows(ROWS[1:2])

        self.rich_log = self.query_one(RichLog)
        self.agent.set_log_callback(self.on_log_message)

    def on_log_message(self, msg):
        self.rich_log.write(msg)


async def main(args):
    genesis_data = await fetch_genesis_txns("http://test.bcovrin.vonx.io/genesis")
    agent = Agent("discovery", genesis_data)
    app = DiscoveryService(agent)

    await asyncio.gather(
        agent.start_process(),
        app.run_async()
    )


if __name__ == "__main__":
    args = None

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("Interrupted")
        os._exit(1)
