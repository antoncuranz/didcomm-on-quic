from textual.app import App, ComposeResult
from textual.widgets import Header, TabbedContent, TabPane, RichLog

from services.common.webhook_agent_base import WebhookAgentBase


class AppBase(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def __init__(self, service_name: str, agent: WebhookAgentBase):
        super().__init__()
        self.agent = agent
        self.service_logs = None
        self.actor_logs = None
        self.title = "{} ({})".format(service_name, agent.ident)
        self.sub_title = "IP: {} Port: {} ({})".format(agent.external_host, agent.http_port, agent.transport_type)

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="actor"):
            with TabPane("User Interface", id="services"):
                for widget in  self.compose_ui():
                    yield widget
            with TabPane("Service Logs", id="controller"):
                yield RichLog(id="service_logs", highlight=True, markup=True, wrap=True)
            with TabPane("Actor Logs", id="actor"):
                yield RichLog(id="actor_logs", highlight=True, markup=True, wrap=True)

    def compose_ui(self) -> ComposeResult:
        raise NotImplemented

    def on_mount(self) -> None:
        self.query_one(Header).tall = True

        self.actor_logs = self.query_one("#actor_logs", RichLog)
        self.service_logs = self.query_one("#service_logs", RichLog)
        self.agent.set_log_callback(self.on_log_message)

    def on_log_message(self, msg):
        self.actor_logs.write(msg)
