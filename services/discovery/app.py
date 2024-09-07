from textual.app import ComposeResult
from textual.widgets import DataTable

from services.common.app_base import AppBase
from .agent import Agent

ROWS = [
    ("did:indy:xyz", "FRONT_CAM_STREAM", "(D) B-AB 1234", "Daimler", "(timestamp)"),
    ("did:indy:abc", "FRONT_CAM_STREAM", "UNVERIFIED", "UNVERIFIED", "(timestamp)"),
]


class DiscoveryService(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Discovery Service", agent)
        self.service_table = None
        self.connection_table = None
        self.agent.set_webhook_callback("connections", self.handle_connections)

    def compose_ui(self) -> ComposeResult:
        yield DataTable(id="service_table", cursor_type="row")
        yield DataTable(id="connection_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

        self.service_table = self.query_one("#service_table", DataTable)
        self.service_table.add_columns("DID", "Service", "Registration", "Manufacturer", "Expires")
        self.service_table.add_rows(ROWS)

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("Label", "Public DID", "DID", "State")
        # self.connections.add_rows(ROWS)

    def handle_connections(self, connection):
        if connection["state"] == "active":
            self.log_msg("Adding new connection to table")

            label = connection.get("their_label", "-")
            public_did = connection.get("their_public_did", "-")
            did = connection.get("their_did", "-")
            state = connection["state"]

            if state != "invitation":
                self.connection_table.add_row(label, public_did, did, state)
