from textual.app import ComposeResult
from textual.widgets import DataTable

from .agent import Agent
from services.common.app_base import AppBase

ROWS = [
    ("did:indy:xyz", "FRONT_CAM_STREAM", "(D) B-AB 1234", "Daimler", "(timestamp)"),
    ("did:indy:abc", "FRONT_CAM_STREAM", "UNVERIFIED", "UNVERIFIED", "(timestamp)"),
]


class DiscoveryService(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Discovery Service", agent)
        self.service_table = None
        self.connection_table = None

    def compose_ui(self) -> ComposeResult:
        yield DataTable(id="service_table", cursor_type="row")
        yield DataTable(id="connection_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

        self.service_table = self.query_one("#service_table", DataTable)
        self.service_table.add_columns("DID", "Service", "Registration", "Manufacturer", "Expires")
        self.service_table.add_rows(ROWS)

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("Public DID", "DID", "State")
        # self.connections.add_rows(ROWS)
