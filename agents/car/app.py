import asyncio
import base64
import subprocess
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Button, Log, Checkbox, Label, Collapsible

from agents.common.app_base import AppBase
from .agent import Agent


class VideoStreamScreen(ModalScreen):
    CSS_PATH = "modal.tcss"

    def __init__(self, agent, stream_file, display_stream):
        super().__init__()
        self.agent = agent
        self.stream_file = stream_file
        self.vo = "" if display_stream else "null"
        self.proc = None
        self.stream_log = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Log(id="stream_log"),
            Button("Close Stream", variant="error", id="close"),
        )

    async def on_mount(self) -> None:
        self.stream_log = self.query_one(Log)
        self.proc = subprocess.Popen(["mpv", "-vo=" + self.vo, self.stream_file],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE
        )
        for handle in [self.proc.stdout, self.proc.stderr]:
            asyncio.get_event_loop().run_in_executor(
                self.agent.thread_pool_executor,
                self.handle_stdout, handle
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=1.5)
            self.proc.stdout.close()
            self.proc.stderr.close()
            self.app.pop_screen()
        except subprocess.TimeoutExpired:
            msg = "Process did not terminate in time"
            print(msg)
            raise Exception(msg)

    def handle_stdout(self, handle):
        while not handle.closed:
            try:
                line = self.custom_readline(handle)
                lines = self.stream_log._lines

                if len(lines) > 0 and line.startswith("V: ") and lines[-1].startswith("V: "):
                    self.stream_log._lines[-1] = line
                    self.stream_log.refresh_lines(len(lines) - 1)
                elif len(line) > 0:
                    self.stream_log.write_line(line)
            except:
                pass

    def custom_readline(self, handle):
        line = ""
        while not handle.closed:
            char = handle.read(1)
            if char == b'\n' or char == b'\r':
                return line.removeprefix("\x1b[K").rstrip()
            else:
                line += char.decode()


class CarApp(AppBase):
    CSS_PATH = "style.tcss"

    def __init__(self, agent: Agent):
        super().__init__("Car Agent", agent)
        self.credential_table = None
        self.service_input = None
        self.register_btn = None
        self.access_btn = None
        self.display_cb = None
        self.bm_input = None
        self.agent.set_webhook_callback("issue_credential_v2_0", self.handle_credentials)
        self.agent.set_webhook_callback("requeststream_result", self.handle_stream_result)
        self.agent.set_webhook_callback("queryservices_result", self.handle_available_services)

    def compose_ui(self) -> ComposeResult:
        yield Horizontal(
            Input(id="service_input", placeholder="Service"),
            Button("Register", id="register_btn"),
            Button("Query", id="query_btn"),
            Button("Access Stream", id="access_btn"),
            Checkbox("Display", id="display_cb")
        )
        yield Label("Credentials")
        yield DataTable(id="credential_table", cursor_type="row", name="Credentials")
        
    def compose_benchmark_ui(self) -> ComposeResult:
        yield Input("9HktKFSbBsrxQJ6tTKq7SU", id="bm_input", placeholder="Connect to DID", classes="input")
        yield Button("Connect", id="bm_connect")
        yield Button("Request Cred", id="bm_reqest_cred")

    def on_mount(self) -> None:
        self.credential_table = self.query_one("#credential_table", DataTable)
        self.credential_table.add_columns("State", "Schema", "Attributes")

        self.service_input = self.query_one("#service_input", Input)
        self.register_btn = self.query_one("#register_btn", Button)
        self.access_btn = self.query_one("#access_btn", Button)
        self.display_cb = self.query_one("#display_cb", Checkbox)
        self.bm_input = self.query_one("#bm_input", Input)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        conn_id = self.get_focused_connection()

        if button == "register_btn":
            service = self.service_input.value
            self.run_worker(self.agent.register_service(conn_id, service), exit_on_error=False)
        elif button == "query_btn":
            service = self.service_input.value
            self.run_worker(self.agent.query_services(conn_id, service), exit_on_error=False)
        elif button == "access_btn":
            self.log_msg("Requesting stream from connection {}".format(conn_id))
            self.run_worker(self.agent.request_video_stream(conn_id), exit_on_error=False)
        elif button == "bm_connect":
            did = self.bm_input.value
            self.log_msg("BM: Connecting to " + did + " at time " + str(time.perf_counter()))
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)

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

        stream_file = "recvd/stream.mpd"
        with open(stream_file, "wb") as file:
            modified = file_content.replace(b"media=\"", b"media=\"" + base_url.encode()) \
                .replace(b"initialization=\"", b"initialization=\"" + base_url.encode())
            file.write(modified)

        self.push_screen(VideoStreamScreen(self.agent, stream_file, self.display_cb.value))

    def handle_available_services(self, message):
        connections = list(self.connection_table.get_column_at(2))
        services = message["services"]

        if len(services) == 0:
            self.notify("No services available")

        for service in services:
            did = service["did"]
            if did not in connections and self.agent.did not in did:
                self.log_msg("Connecting to " + did)
                self.notify("Connecting to " + did)
                self.run_worker(self.agent.create_connection(did), exit_on_error=False)
            else:
                self.notify("Not connecting to " + did)
