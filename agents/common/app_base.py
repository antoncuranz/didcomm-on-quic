from textual.app import App, ComposeResult
from textual.widgets import Header, TabbedContent, TabPane, RichLog

from services.common.webhook_agent_base import WebhookAgentBase


class AppBase(App):
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def __init__(self, service_name: str, agent: WebhookAgentBase):
        super().__init__()
        self.agent = agent
        self.service_logs = None
        self.agent_logs = None
        self.title = "{} ({})".format(service_name, agent.ident)
        self.sub_title = "IP: {} Port: {} ({})".format(agent.external_host, agent.http_port, agent.transport_type)

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(initial="service"):
            with TabPane("User Interface", id="ui"):
                for widget in  self.compose_ui():
                    yield widget
            with TabPane("Service Logs", id="service"):
                yield RichLog(id="service_logs", highlight=True, markup=True, wrap=True)
            with TabPane("Agent Logs", id="agent"):
                yield RichLog(id="agent_logs", highlight=True, markup=True, wrap=True)

    def compose_ui(self) -> ComposeResult:
        raise NotImplemented

    def on_mount(self) -> None:
        self.query_one(Header).tall = True

        self.agent_logs = self.query_one("#agent_logs", RichLog)
        self.service_logs = self.query_one("#service_logs", RichLog)
        self.agent.set_log_callback(self.on_log_message)

    def on_log_message(self, msg):
        self.agent_logs.write(msg)

    def log_msg(self, msg):
        self.service_logs.write(msg)
