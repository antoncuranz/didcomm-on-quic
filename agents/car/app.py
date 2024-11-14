import asyncio
import base64
import subprocess
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Button, Log, Checkbox, Label

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
        self.bm_pres_times = {}
        self.bm_conn_count = None
        self.bm_pres_batch_cb = None
        self.agent.set_webhook_callback("issue_credential_v2_0", self.handle_credentials)
        self.agent.set_webhook_callback("requeststream_result", self.handle_stream_result)
        self.agent.set_webhook_callback("queryservices_result", self.handle_available_services)
        self.agent.set_webhook_callback("fetchchunk_metrics", self.log_msg)
        self.agent.set_webhook_callback("presentation_metrics", self.log_msg)
        self.bm_connections = {}
        self.bm_repeat_count = 0

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
        with Vertical():
            with Horizontal():
                yield Input("PhbGmg1H53KupchWiZSyk1", id="bm_input", placeholder="Connect to DID", classes="input")
                yield Button("Connect", id="bm_connect")
                yield Input("1", id="bm_conn_count", placeholder="Count", classes="input")
            with Horizontal():
                yield Button("Request Proof", id="bm_presreq")
                yield Checkbox("Batch", id="bm_pres_batch")

    def on_mount(self) -> None:
        self.credential_table = self.query_one("#credential_table", DataTable)
        self.credential_table.add_columns("State", "Schema", "Attributes")

        self.service_input = self.query_one("#service_input", Input)
        self.display_cb = self.query_one("#display_cb", Checkbox)
        self.bm_input = self.query_one("#bm_input", Input)
        self.bm_conn_count = self.query_one("#bm_conn_count", Input)
        self.bm_pres_batch_cb = self.query_one("#bm_pres_batch", Checkbox)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "bm_connect":
            did = self.bm_input.value
            self.bm_repeat_count = int(self.bm_conn_count.value) - 1
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)
            return

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
        elif button == "bm_presreq":
            if self.bm_pres_batch_cb.value:
                count = int(self.bm_conn_count.value)
            else:
                self.bm_repeat_count = int(self.bm_conn_count.value)
                count = 1
            self.batch_request_presentations(conn_id, count)

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

        if not self.benchmark_mode.value:
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
    
    def handle_connections(self, connection):
        super().handle_connections(connection)
        
        state = connection["state"]
        if state == "active":
            conn_id = connection["connection_id"]
            did = connection["their_did"].split(":")[-1]
            
            if did in self.bm_connections:
                req_time = self.bm_connections[did]
                rsp_time = time.perf_counter()
                self.log_msg("BM(conn): {};{};{};{}".format(connection["their_did"], req_time, rsp_time, rsp_time-req_time))
                del self.bm_connections[did]
                
            if self.benchmark_mode.value:
                self.run_worker(self.agent.delete_connection(conn_id), exit_on_error=False)
                
        elif state == "deleted" and self.bm_repeat_count > 0:
            did = connection["their_did"].split(":")[-1]
            self.bm_repeat_count -= 1

            async def wait_and_connect(did):
                await asyncio.sleep(self.agent.keepalive_timeout + 0.5)
                self.bm_connections[did] = time.perf_counter()
                await self.agent.create_connection(did)

            self.run_worker(wait_and_connect(did), exit_on_error=False)

    def batch_request_presentations(self, conn_id, count):
        self.bm_pres_times = dict(init=time.perf_counter(), count=count)

        def done_callback(task, req_time):
            pres_ex_id = task.result()["pres_ex_id"]
            self.bm_pres_times[pres_ex_id] = dict(req_time=req_time)

        for i in range(count):
            req_time = time.perf_counter()
            task = asyncio.create_task(self.agent.request_presentation(conn_id))
            task.add_done_callback(lambda task: done_callback(task, req_time))

    def handle_present_proof(self, message):
        super().handle_present_proof(message)

        if message["state"] != "done":
            return

        pres_ex_id = message["pres_ex_id"]
        rsp_time = time.perf_counter()
        if pres_ex_id in self.bm_pres_times:
            req_time = self.bm_pres_times.pop(pres_ex_id)["req_time"]
            self.log_msg( "BM(pres): done;{};{};{};{}".format(pres_ex_id, req_time, rsp_time, rsp_time-req_time))
            if self.bm_repeat_count > 0:
                self.bm_repeat_count -= 1
                async def wait_and_request_pres(conn_id):
                    await asyncio.sleep(self.agent.keepalive_timeout + 0.5)
                    self.batch_request_presentations(conn_id, 1)

                self.run_worker(wait_and_request_pres(message["connection_id"]), exit_on_error=False)

        if self.bm_pres_batch_cb.value and len(self.bm_pres_times.keys()) == 2: # only init and count
            req_time = self.bm_pres_times["init"]
            self.log_msg("BM(pres): batch-done;{};{};{};{}".format(self.bm_pres_times["count"], req_time, rsp_time, rsp_time-req_time))

