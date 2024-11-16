import asyncio
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Button

from .agent import Agent
from .app import CarApp


class BenchmarkCarApp(CarApp):

    def __init__(self, agent: Agent):
        super().__init__(agent)
        self.bm_input = None
        self.bm_pres_times = {}
        self.bm_repeat_count = None
        self.bm_pres_batch_size = None
        self.bm_connections = {}
        self.bm_repeat_remaining = 0
        self.agent.set_webhook_callback("fetchchunk_metrics", self.log_msg)
        self.agent.set_webhook_callback("retrievefile_metrics", self.log_msg)
        self.agent.set_webhook_callback("presentation_metrics", self.log_msg)
        self.agent.set_webhook_callback("retrievefile_result", self.handle_retrievefile_results)

    def compose_benchmark_ui(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield Input("PhbGmg1H53KupchWiZSyk1", id="bm_input", placeholder="Connect to DID", classes="input")
                yield Button("Connect", id="bm_connect")
            with Horizontal():
                yield Input("100", id="bm_pres_batch_size", placeholder="Size", classes="input")
                yield Button("Request Proof Batch", id="bm_pres_batch_btn")
            with Horizontal():
                yield Input("1", id="bm_repeat_count", placeholder="Count", classes="input")
                yield Button("Repeat Count", disabled=True)

    def on_mount(self) -> None:
        super().on_mount()
        self.bm_input = self.query_one("#bm_input", Input)
        self.bm_repeat_count = self.query_one("#bm_repeat_count", Input)
        self.bm_pres_batch_size = self.query_one("#bm_pres_batch_size", Input)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        
        if button == "bm_connect":
            did = self.bm_input.value
            self.bm_repeat_remaining = int(self.bm_repeat_count.value) - 1
            self.run_worker(self.agent.create_connection(did), exit_on_error=False)
            
        elif button == "bm_pres_batch_btn":
            conn_id = self.get_focused_connection()
            self.bm_repeat_remaining = int(self.bm_repeat_count.value) - 1
            self.batch_request_presentations(conn_id)
            
        elif button == "file_btn":
            self.bm_repeat_remaining = int(self.bm_repeat_count.value) - 1

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
                
        elif state == "deleted" and self.bm_repeat_remaining > 0:
            did = connection["their_did"].split(":")[-1]
            self.bm_repeat_remaining -= 1

            async def wait_and_connect(did):
                if self.agent.keepalive_timeout is not None:
                    await asyncio.sleep(self.agent.keepalive_timeout + 0.5)
                self.bm_connections[did] = time.perf_counter()
                await self.agent.create_connection(did)

            self.run_worker(wait_and_connect(did), exit_on_error=False)

    def batch_request_presentations(self, conn_id):
        batch_size = int(self.bm_pres_batch_size.value)
        self.bm_pres_times = dict(init=time.perf_counter(), count=batch_size)

        def done_callback(task, req_time):
            pres_ex_id = task.result()["pres_ex_id"]
            self.bm_pres_times[pres_ex_id] = dict(req_time=req_time)

        for i in range(batch_size):
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

        if len(self.bm_pres_times.keys()) == 2: # only init and count
            count = self.bm_pres_times["count"]
            if count > 1:
                req_time = self.bm_pres_times["init"]
                self.log_msg("BM(pres): batch-done;{};{};{};{}".format(count, req_time, rsp_time, rsp_time-req_time))
                self.notify("BM(pres): batch-done in {}".format(rsp_time-req_time))

            if self.bm_repeat_remaining > 0:
                self.bm_repeat_remaining -= 1
                async def wait_and_request_pres(conn_id):
                    if self.agent.keepalive_timeout is not None:
                        await asyncio.sleep(self.agent.keepalive_timeout + 0.5)
                    self.batch_request_presentations(conn_id)

                self.run_worker(wait_and_request_pres(message["connection_id"]), exit_on_error=False)
    
    def handle_retrievefile_results(self, message):
        if self.bm_repeat_remaining <= 0:
            return
        
        self.bm_repeat_remaining -= 1

        async def wait_and_download(conn_id, filename):
            if self.agent.keepalive_timeout is not None:
                await asyncio.sleep(self.agent.keepalive_timeout + 0.5)
            await self.agent.retrieve_file(conn_id, filename)

        self.run_worker(wait_and_download(message["conn_id"], message["filename"]), exit_on_error=False)
