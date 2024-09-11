import json

from textual.app import ComposeResult
from textual.widgets import DataTable

from agents.common.app_base import AppBase
from .agent import Agent

ROWS = [
    ("did:indy:xyz", "FRONT_CAM_STREAM", "(D) B-AB 1234", "Daimler", "(timestamp)"),
    ("did:indy:abc", "FRONT_CAM_STREAM", "UNVERIFIED", "UNVERIFIED", "(timestamp)"),
]


class DiscoveryApp(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Discovery Service", agent)
        self.service_table = None
        self.connection_table = None
        self.agent.set_webhook_callback("connections", self.handle_connections)
        self.agent.set_webhook_callback("issue_credential_v2_0", self.handle_credentials)

    def compose_ui(self) -> ComposeResult:
        yield DataTable(id="service_table", cursor_type="row")
        yield DataTable(id="connection_table", cursor_type="row")
        yield DataTable(id="credential_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

        self.service_table = self.query_one("#service_table", DataTable)
        self.service_table.add_columns("DID", "Service", "Registration", "Manufacturer", "Expires")
        self.service_table.add_rows(ROWS)

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("State", "Label", "DID", "Connection")

        self.credential_table = self.query_one("#credential_table", DataTable)
        self.credential_table.add_columns("State", "Schema", "Attributes")

    def handle_connections(self, connection):
        if connection["state"] == "active":
            self.log_msg("Adding new connection to table")

            label = connection.get("their_label", "-")
            did = connection.get("their_did", "-")
            state = connection["state"]
            conn_id = connection["connection_id"]

            if state != "invitation": # dumb
                self.connection_table.add_row(state, label, did, conn_id)

    def handle_credentials(self, credential):
        if credential["state"] == "done":
            self.log_msg("Adding new credential to table")

            state = credential["state"]
            schema = credential["by_format"]["cred_issue"]["indy"]["schema_id"]
            attributes = credential["by_format"]["cred_issue"]["indy"]["values"]
            attributes_str = ", ".join([f"{key}={value["raw"]}" for key, value in attributes.items()])

            self.credential_table.add_row(state, schema, attributes_str)
