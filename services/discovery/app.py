from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, TabbedContent, TabPane, RichLog

from .agent import Agent

ROWS = [
    ("did:indy:xyz", "FRONT_CAM_STREAM", "(D) B-AB 1234", "Daimler", "(timestamp)"),
    ("did:indy:abc", "FRONT_CAM_STREAM", "UNVERIFIED", "UNVERIFIED", "(timestamp)"),
]

class DiscoveryService(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent
        self.service_table = None
        self.connection_table = None
        self.rich_log = None
        self.title = "Discovery Service ({})".format(agent.ident)
        self.sub_title = "IP: {} Port: {} ({})".format(agent.external_host, agent.http_port, agent.transport_type)

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="actor"):
            with TabPane("User Interface", id="services"):
                yield DataTable(id="service_table", cursor_type="row")
                yield DataTable(id="connection_table", cursor_type="row")
            with TabPane("Controller Logs", id="controller"):
                yield RichLog(id="controller_logs", highlight=True, markup=True, wrap=True)
            with TabPane("Actor Logs", id="actor"):
                yield RichLog(id="actor_logs", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        self.query_one(Header).tall = True

        self.service_table = self.query_one("#service_table", DataTable)
        self.service_table.add_columns("DID", "Service", "Registration", "Manufacturer", "Expires")
        self.service_table.add_rows(ROWS)

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("Public DID", "DID", "State")
        # self.connections.add_rows(ROWS)

        self.rich_log = self.query_one("#actor_logs", RichLog)
        self.agent.set_log_callback(self.on_log_message)

    def on_log_message(self, msg):
        self.rich_log.write(msg)
