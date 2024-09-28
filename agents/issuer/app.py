from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.widgets import Input, Button

from agents.common.app_base import AppBase
from .agent import Agent


class IssuerApp(AppBase):
    def __init__(self, agent: Agent):
        super().__init__("Issuer", agent)
        self.service_table = None
        self.input_connect = None

    def compose_ui(self) -> ComposeResult:
        yield Horizontal(
            Input("9HktKFSbBsrxQJ6tTKq7SU", id="input_connect", placeholder="Connect to DID", classes="input"),
            Button("Connect", id="connect"),
        )
        yield Horizontal(
            Input("Anton", id="input_first_name", placeholder="First Name"),
            Input("Curanz", id="input_last_name", placeholder="Last Name"),
            Button("Issue", id="issue_name"),
            classes="issue_name"
        )
        yield Horizontal(
            Input("VW", id="input_make", placeholder="Make"),
            Input("Golf", id="input_model", placeholder="Model"),
            Input("2019", id="input_year", placeholder="Year"),
            Button("Issue", id="issue_type"),
            classes="issue_type"
        )
        yield Horizontal(
            Input("(D) B-C 1234", id="input_reg", placeholder="Registration"),
            Input("2025", id="input_exp", placeholder="Expiration"),
            Button("Issue", id="issue_reg"),
            classes="issue_reg"
        )

    def on_mount(self) -> None:
        self.input_first_name = self.query_one("#input_first_name", Input)
        self.input_last_name = self.query_one("#input_last_name", Input)
        self.input_connect = self.query_one("#input_connect", Input)
        self.input_make = self.query_one("#input_make", Input)
        self.input_model = self.query_one("#input_model", Input)
        self.input_year = self.query_one("#input_year", Input)
        self.input_reg = self.query_one("#input_reg", Input)
        self.input_exp = self.query_one("#input_exp", Input)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id

        if button == "connect":
            did = self.input_connect.value
            self.log_msg("Connecting to " + did)
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)
            return

        conn_id = self.get_focused_connection()

        if button == "issue_name":
            self.log_msg("Issuing Name Credential to connection " + conn_id)
            attributes = [
                {"name": "first_name", "value": self.input_first_name.value},
                {"name": "last_name", "value": self.input_last_name.value},
            ]
            self.run_worker(self.agent.issue_credential(conn_id, self.agent.cred_def_name, attributes), exit_on_error=False)

        elif button == "issue_type":
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
