from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Button

from agents.common.app_base import AppBase
from .agent import Agent


class IssuerApp(AppBase):
    def __init__(self, agent: Agent):
        super().__init__("Issuer", agent)
        self.service_table = None
        self.connection_table = None
        self.input_connect = None
        self.agent.set_webhook_callback("connections", self.handle_connections)

    def compose_ui(self) -> ComposeResult:
        yield Horizontal(
            Input(id="input_connect", placeholder="Connect to DID", classes="input"),
            Button("Connect", id="connect"),
        )
        yield Horizontal(
            Input(id="input_make", placeholder="Make"),
            Input(id="input_model", placeholder="Model"),
            Input(id="input_year", placeholder="Year"),
            Button("Issue", id="issue_type"),
            classes="issue_type"
        )
        yield Horizontal(
            Input(id="input_reg", placeholder="Registration"),
            Input(id="input_exp", placeholder="Expiration"),
            Button("Issue", id="issue_reg"),
            classes="issue_reg"
        )
        yield DataTable(id="connection_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("State", "Label", "DID", "Connection")

        self.input_connect = self.query_one("#input_connect", Input)
        self.input_make = self.query_one("#input_make", Input)
        self.input_model = self.query_one("#input_model", Input)
        self.input_year = self.query_one("#input_year", Input)
        self.input_reg = self.query_one("#input_reg", Input)
        self.input_exp = self.query_one("#input_exp", Input)

    def handle_connections(self, connection):
        if connection["state"] == "active":
            self.log_msg("Adding new connection to table")

            label = connection.get("their_label", "-")
            did = connection.get("their_did", "-")
            state = connection["state"]
            conn_id = connection["connection_id"]

            if state != "invitation":
                self.connection_table.add_row(state, label, did, conn_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id

        if button == "connect":
            did = self.input_connect.value
            self.log_msg("Connecting to " + did)
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)
            return

        conn_id = self.get_focused_connection()

        if button == "issue_type":
            self.log_msg("Issuing Type Credential to connection " + conn_id)
            attributes = [
                {"name": "make", "value": self.input_make.value},
                {"name": "model", "value": self.input_model.value},
                {"name": "year", "value": self.input_year.value}
            ]
            self.run_worker(self.agent.issue_credential(conn_id, self.agent.cred_def_type, attributes), exit_on_error=False)

        elif button == "issue_reg":
            self.log_msg("Issuing Registration Credential to connection " + conn_id)
            attributes = [
                {"name": "registration", "value": self.input_reg.value},
                {"name": "expiration", "value": self.input_exp.value},
            ]
            self.run_worker(self.agent.issue_credential(conn_id, self.agent.cred_def_reg, attributes), exit_on_error=False)

    def get_focused_connection(self):
        cursor_row = self.connection_table.cursor_row
        return self.connection_table.get_cell_at(Coordinate(cursor_row, 3))
