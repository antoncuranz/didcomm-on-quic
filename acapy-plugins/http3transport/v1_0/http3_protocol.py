import asyncio
import time
from email.utils import formatdate
from typing import Callable, Dict, cast, Optional

import aioquic
from aioquic.asyncio import QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DataReceived,
    H3Event,
    HeadersReceived, WebTransportStreamDataReceived, DatagramReceived,
)
from aioquic.h3.exceptions import NoAvailablePushIDError
from aioquic.quic.events import ProtocolNegotiated, DatagramFrameReceived, QuicEvent

SERVER_NAME = "aioquic/" + aioquic.__version__


class HttpRequestHandler:
    def __init__(
            self,
            *,
            authority: bytes,
            connection: H3Connection,
            protocol: QuicConnectionProtocol,
            scope: Dict,
            stream_ended: bool,
            stream_id: int,
            transmit: Callable[[], None],
    ) -> None:
        self.authority = authority
        self.connection = connection
        self.protocol = protocol
        self.queue: asyncio.Queue[Dict] = asyncio.Queue()
        self.scope = scope
        self.stream_id = stream_id
        self.transmit = transmit

        if stream_ended:
            self.queue.put_nowait({"type": "http.request"})

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, DataReceived):
            self.queue.put_nowait(
                {
                    "type": "http.request",
                    "body": event.data,
                    "more_body": not event.stream_ended,
                }
            )
        elif isinstance(event, HeadersReceived) and event.stream_ended:
            self.queue.put_nowait(
                {"type": "http.request", "body": b"", "more_body": False}
            )

    async def run_asgi(self, app: Callable) -> None:
        await app(self.scope, self.receive, self.send)

    async def receive(self) -> Dict:
        return await self.queue.get()

    async def send(self, message: Dict) -> None:
        if message["type"] == "http.response.start":
            self.connection.send_headers(
                stream_id=self.stream_id,
                headers=[
                            (b":status", str(message["status"]).encode()),
                            (b"server", SERVER_NAME.encode()),
                            (b"date", formatdate(time.time(), usegmt=True).encode()),
                        ]
                        + [(k, v) for k, v in message["headers"]],
            )
        elif message["type"] == "http.response.body":
            self.connection.send_data(
                stream_id=self.stream_id,
                data=message.get("body", b""),
                end_stream=not message.get("more_body", False),
            )
        elif message["type"] == "http.response.push" and isinstance(
                self.connection, H3Connection
        ):
            request_headers = [
                                  (b":method", b"GET"),
                                  (b":scheme", b"https"),
                                  (b":authority", self.authority),
                                  (b":path", message["path"].encode()),
                              ] + [(k, v) for k, v in message["headers"]]

            # send push promise
            try:
                push_stream_id = self.connection.send_push_promise(
                    stream_id=self.stream_id, headers=request_headers
                )
            except NoAvailablePushIDError:
                return

            # fake request
            cast(Http3ServerProtocol, self.protocol).http_event_received(
                HeadersReceived(
                    headers=request_headers, stream_ended=True, stream_id=push_stream_id
                )
            )
        self.transmit()


class Http3ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handlers: Dict[int, HttpRequestHandler] = {}
        self._http: Optional[H3Connection] = None
        self.app: Optional[Callable] = None

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived) and event.stream_id not in self._handlers:
            authority = None
            headers = []
            http_version = "3"
            raw_path = b""
            method = ""
            for header, value in event.headers:
                if header == b":authority":
                    authority = value
                    headers.append((b"host", value))
                elif header == b":method":
                    method = value.decode()
                elif header == b":path":
                    raw_path = value
                elif header and not header.startswith(b":"):
                    headers.append((header, value))

            if b"?" in raw_path:
                path_bytes, query_string = raw_path.split(b"?", maxsplit=1)
            else:
                path_bytes, query_string = raw_path, b""
            path = path_bytes.decode()
            self._quic._logger.info("HTTP request %s %s", method, path)

            # FIXME: add a public API to retrieve peer address
            client_addr = self._http._quic._network_paths[0].addr
            client = (client_addr[0], client_addr[1])

            scope: Dict
            extensions: Dict[str, Dict] = {}
            if isinstance(self._http, H3Connection):
                extensions["http.response.push"] = {}
            scope = {
                "client": client,
                "extensions": extensions,
                "headers": headers,
                "http_version": http_version,
                "method": method,
                "path": path,
                "query_string": query_string,
                "raw_path": raw_path,
                "root_path": "",
                "scheme": "https",
                "type": "http",
            }
            handler = HttpRequestHandler(
                authority=authority,
                connection=self._http,
                protocol=self,
                scope=scope,
                stream_ended=event.stream_ended,
                stream_id=event.stream_id,
                transmit=self.transmit,
            )
            self._handlers[event.stream_id] = handler
            asyncio.ensure_future(handler.run_asgi(self.app))
        elif (
                isinstance(event, (DataReceived, HeadersReceived))
                and event.stream_id in self._handlers
        ):
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)
        elif isinstance(event, DatagramReceived):
            handler = self._handlers[event.stream_id]
            handler.http_event_received(event)
        elif isinstance(event, WebTransportStreamDataReceived):
            handler = self._handlers[event.session_id]
            handler.http_event_received(event)

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            if event.alpn_protocol in H3_ALPN:
                self._http = H3Connection(self._quic)
        elif isinstance(event, DatagramFrameReceived):
            if event.data == b"quack":
                self._quic.send_datagram_frame(b"quack-ack")

        #  pass event to the HTTP layer
        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)

    def set_app(self, app):
        self.app = app
