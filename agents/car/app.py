import base64

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Input, Button

from agents.common.app_base import AppBase
from .agent import Agent


class CarApp(AppBase):

    def __init__(self, agent: Agent):
        super().__init__("Car Agent", agent)
        self.credential_table = None
        self.service_input = None
        self.register_btn = None
        self.access_btn = None
        self.agent.set_webhook_callback("issue_credential_v2_0", self.handle_credentials)
        self.agent.set_webhook_callback("requeststream_result", self.handle_stream_result)

    def compose_ui(self) -> ComposeResult:
        yield Horizontal(
            Input(id="service_input", placeholder="Service"),
            Button("Register", id="register_btn"),
            Button("Access Stream", id="access_btn"),
        )
        yield DataTable(id="credential_table", cursor_type="row")

    def on_mount(self) -> None:
        super().on_mount()

        self.credential_table = self.query_one("#credential_table", DataTable)
        self.credential_table.add_columns("State", "Schema", "Attributes")

        self.service_input = self.query_one("#service_input", Input)
        self.register_btn = self.query_one("#register_btn", Button)
        self.access_btn = self.query_one("#access_btn", Button)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        conn_id = self.get_focused_connection()

        if button == "register_btn":
            service = self.service_input.value
            self.run_worker(self.agent.register_service(conn_id, service), exit_on_error=False)
        elif button == "access_btn":
            self.log_msg("Requesting stream from connection {}".format(conn_id))
            self.run_worker(self.agent.request_video_stream(conn_id), exit_on_error=False)

    def handle_credentials(self, credential):
        if credential["state"] == "done":
            self.log_msg("Adding new credential to table")

            state = credential["state"]
            schema = credential["by_format"]["cred_issue"]["indy"]["schema_id"]
            attributes = credential["by_format"]["cred_issue"]["indy"]["values"]
            attributes_str = ", ".join([f"{key}={value["raw"]}" for key, value in attributes.items()])

            self.credential_table.add_row(state, schema, attributes_str)

    def handle_stream_result(self, message):
        file_content = base64.b64decode(message["data"])
        base_url = "http://0.0.0.0:{}/connections/{}/videostreaming/".format(self.agent.admin_port, message["conn_id"])
        # TODO: use self.agent.external_host instead of 0.0.0.0?

        with open("recvd/stream.mpd", "wb") as file:
            modified = file_content.replace(b"media=\"", b"media=\"" + base_url.encode())\
                .replace(b"initialization=\"", b"initialization=\"" + base_url.encode())
            file.write(modified)
