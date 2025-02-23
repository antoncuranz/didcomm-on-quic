from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Label, Input, Button
from textual.widgets._data_table import RowDoesNotExist

from agents.common.app_base import AppBase
from .agent import Agent


class DiscoveryApp(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Discovery Service", agent)
        self.service_table = None
        self.agent.set_webhook_callback("service_registry", self.handle_service_registry)
        self.bm_input = None

    def compose_ui(self) -> ComposeResult:
        yield Label("Registered Services")
        yield DataTable(id="service_table", cursor_type="row")
    
    def compose_benchmark_ui(self) -> ComposeResult:
        with Horizontal():
            yield Input("9HktKFSbBsrxQJ6tTKq7SU", id="bm_input", placeholder="Connect to DID", classes="input")
            yield Button("Connect", id="bm_connect")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        self.bm_input = self.query_one("#bm_input", Input)

        if button == "bm_connect":
            did = self.bm_input.value
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)

    def on_mount(self) -> None:
        self.service_table = self.query_one("#service_table", DataTable)
        self.service_table.add_columns("DID", "Service", "Registration", "Type")

    def handle_service_registry(self, service):
        row_key = service["did"] + service["schema"]
        try:
            self.service_table.remove_row(row_key)
            self.log_msg("Deleted old service from table")
        except RowDoesNotExist:
            pass

        if service["state"] != "deleted":
            type = self._get_credential_value(service, "car-type")
            reg = self._get_credential_value(service, "car-registration")
            self.service_table.add_row(service["did"], service["schema"], reg, type, key=row_key)
            self.log_msg("Inserted new service")

    def _get_credential_value(self, service, cred_pattern):
        credentials = service["credentials"]
        type_cred = next((cred for cred in credentials if cred_pattern in cred), None)
        if type_cred:
            return credentials[type_cred]
        else:
            return "UNVERIFIED"
