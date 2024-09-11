from textual.app import App, ComposeResult
from textual.widgets import Header, TabbedContent, TabPane, RichLog
from textual.worker import Worker, WorkerState

from agents.common.webhook_agent_base import WebhookAgentBase


class AppBase(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]
    CSS_PATH = "style.tcss"
    AGENT_INIT_WORKER = "agent-initialize"

    def __init__(self, controller_name: str, agent: WebhookAgentBase):
        super().__init__()
        self.agent = agent
        self.controller_logs = None
        self.agent_logs = None
        self.title = "{} ({})".format(controller_name, agent.ident)
        self.sub_title = "IP: {} Port: {} ({})".format(agent.external_host, agent.http_port, agent.transport_type)

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
            with TabPane("Controller Logs", id="controller"):
                yield RichLog(id="controller_logs", highlight=True, markup=True, wrap=True)
            with TabPane("Agent Logs", id="agent"):
                yield RichLog(id="agent_logs", highlight=True, markup=True, wrap=True)

    def compose_ui(self) -> ComposeResult:
        raise NotImplemented

    def on_mount(self) -> None:
        self.query_one(Header).tall = True

        self.agent_logs = self.query_one("#agent_logs", RichLog)
        self.controller_logs = self.query_one("#controller_logs", RichLog)
        self.agent.set_log_callbacks(self.agent_logs.write, self.controller_logs.write)

    def log_msg(self, msg):
        self.controller_logs.write(msg)