import time
from datetime import datetime

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Header, TabbedContent, TabPane, RichLog, Label, Button, DataTable, Collapsible, Checkbox
from textual.widgets._data_table import RowDoesNotExist
from textual.worker import Worker, WorkerState

from agents.common.webhook_agent_base import WebhookAgentBase

class PresentProofScreen(ModalScreen):
    CSS_PATH = "modal.tcss"

    def __init__(self, agent, pres_ex_id):
        super().__init__()
        self.agent = agent
        self.pres_ex_id = pres_ex_id

        self.credentials = []
        self.requested_attributes = []
        self.credential_table = None

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("New Present-Proof request:", id="question"),
            DataTable(id="credential_table", cursor_type="row"),
            Button("Refuse", variant="error", id="refuse"),
            Button("Present", variant="primary", id="present"),
            id="dialog",
        )

    async def on_mount(self) -> None:
        self.credentials = await self.agent.get_credentials_for_pres_req(self.pres_ex_id)
        self.requested_attributes = list(self.credentials[0]["cred_info"]["attrs"].keys()) if len(self.credentials) > 0 else []

        self.credential_table = self.query_one("#credential_table", DataTable)
        self.credential_table.add_columns(*(["Credential"] + self.requested_attributes))
        rows = [tuple([cred["cred_info"]["cred_def_id"].split(":")[-1]] + list(cred["cred_info"]["attrs"].values())) for cred in self.credentials]
        self.credential_table.add_rows(rows)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "present":
            await self.agent.send_presentation(self.pres_ex_id, self.credentials[0])

        self.app.pop_screen()

class AppBase(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]
    CSS_PATH = "style.tcss"
    AGENT_INIT_WORKER = "agent-initialize"

    def __init__(self, controller_name: str, agent: WebhookAgentBase):
        super().__init__()
        self.agent = agent
        self.title = "{} ({})".format(controller_name, agent.ident)
        self.sub_title = "IP: {} Port: {} ({})".format(agent.external_host, agent.http_port, agent.transport_type)
        self.connection_table = None
        self.controller_logs = None
        self.agent_logs = None
        self.benchmark_mode = None
        self.agent.set_webhook_callback("connections", self.handle_connections)
        self.agent.set_webhook_callback("present_proof_v2_0", self.handle_present_proof)
        self.controller_log_file = open("logs/{}_{}_{}.txt".format(
            str(datetime.now()).replace(" ", "_"), agent.ident, agent.transport_type), "w")

    def on_load(self) -> None:
        self.run_worker(self.agent.initialize(), name=self.AGENT_INIT_WORKER)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self.notify(str(event.worker.error), severity="error")

        if event.worker.name == self.AGENT_INIT_WORKER and event.state == WorkerState.SUCCESS:
            self.notify("Agent initialized!")

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="ui"):
            with TabPane("User Interface", id="ui"):
                for widget in  self.compose_ui():
                    yield widget
                yield Label("Connections")
                yield DataTable(id="connection_table", cursor_type="row")
                with Collapsible(title="Benchmark", id="benchmark_ui"):
                    with Horizontal():
                        yield Checkbox("Enable", id="benchmark_mode")
                        for widget in self.compose_benchmark_ui():
                            yield widget
            with TabPane("Controller Logs", id="controller"):
                yield RichLog(id="controller_logs", highlight=True, markup=True, wrap=True)
            with TabPane("Agent Logs", id="agent"):
                yield RichLog(id="agent_logs", highlight=True, markup=True, wrap=True)

    def compose_ui(self) -> ComposeResult:
        raise NotImplemented
    
    def compose_benchmark_ui(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        self.query_one(Header).tall = True

        self.connection_table = self.query_one("#connection_table", DataTable)
        self.connection_table.add_columns("State", "Label", "DID", "Connection")

        self.agent_logs = self.query_one("#agent_logs", RichLog)
        self.controller_logs = self.query_one("#controller_logs", RichLog)
        self.agent.set_log_callbacks(self.agent_logs.write, self.log_msg)
        
        self.benchmark_mode = self.query_one("#benchmark_mode", Checkbox)

    def log_msg(self, msg):
        self.controller_logs.write(msg)
        self.controller_log_file.write(msg + '\n')

    def on_key(self, event: events.Key) -> None:
        if event.key != "p":
            return

        message = dict(by_format=dict(pres_request=dict(indy=dict(requested_attributes=dict(foo=dict(name="foo"))))))
        self.push_screen(PresentProofScreen(self.agent, message))

    def get_focused_connection(self):
        cursor_row = self.connection_table.cursor_row
        return self.connection_table.get_cell_at(Coordinate(cursor_row, 3))

    def handle_connections(self, connection):
        state = connection["state"]
        if state == "invitation":
            return

        conn_id = connection["connection_id"]
        if state == "active" and self.benchmark_mode.value:
            self.log_msg("BM(conn): done at " + str(time.perf_counter()))
            self.run_worker(self.agent.delete_connection(conn_id), exit_on_error=False)

        label = connection.get("their_label", "-")
        did = connection.get("their_did", "-")

        try:
            self.connection_table.remove_row(conn_id)
            self.log_msg("Deleted old connection from table")
        except RowDoesNotExist:
            pass

        if state != "deleted":
            self.connection_table.add_row(state, label, did, conn_id, key=conn_id)
            self.log_msg("Inserted new connection")

    def handle_present_proof(self, message):
        if message["state"] != "request-received":
            return
        
        if self.benchmark_mode.value:
            self.run_worker(self.auto_present_credential(message["pres_ex_id"]), exit_on_error=False)
        else:
            self.push_screen(PresentProofScreen(self.agent, message["pres_ex_id"]))
    
    async def auto_present_credential(self, pres_ex_id):
        credentials = await self.agent.get_credentials_for_pres_req(pres_ex_id)
        await self.agent.send_presentation(pres_ex_id, credentials[0])
