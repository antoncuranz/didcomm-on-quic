from textual.app import ComposeResult
from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist

from agents.common.app_base import AppBase
from .agent import Agent


class DiscoveryApp(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Discovery Service", agent)
        self.service_table = None
        self.agent.set_webhook_callback("service_registry", self.handle_service_registry)

    def compose_ui(self) -> ComposeResult:
        yield DataTable(id="service_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

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
