import asyncio
import logging
from collections import deque, OrderedDict
from typing import Deque, Dict, Optional
from urllib.parse import urlparse

import aioquic
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import (
    DataReceived,
    H3Event,
    HeadersReceived,
)
from aioquic.quic.events import QuicEvent

logger = logging.getLogger("client")

USER_AGENT = "aioquic/" + aioquic.__version__


class Http3Client(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.pushes: Dict[int, Deque[H3Event]] = {}
        self._http: Optional[H3Connection] = None
        self._request_events: Dict[int, Deque[H3Event]] = {}
        self._request_waiter: Dict[int, asyncio.Future[Deque[H3Event]]] = {}
        self._http = H3Connection(self._quic)
        self.http_response_headers = OrderedDict()
        self.http_response_data = bytearray()

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, (HeadersReceived, DataReceived)):
            stream_id = event.stream_id
            if stream_id in self._request_events:
                self._request_events[event.stream_id].append(event)
                if event.stream_ended:
                    request_waiter = self._request_waiter.pop(stream_id)
                    request_waiter.set_result(self._request_events.pop(stream_id))

        if isinstance(event, DataReceived):
            self.http_response_data.extend(event.data)

        if isinstance(event, HeadersReceived):
            for k, v in event.headers:
                self.http_response_headers[k.decode()] = v.decode()

    def quic_event_received(self, event: QuicEvent) -> None:
        #  pass event to the HTTP layer
        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)

    async def send_http_request(self, url: str, method: str = "GET", data: Optional[str] = None, headers: Optional[Dict] = None):
        if headers is None:
            headers = {}

        parsed = urlparse(url)
        authority = parsed.netloc
        path = parsed.path or "/"

        stream_id = self._quic.get_next_available_stream_id()
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                        (b":method", method.encode()),
                        (b":scheme", b"https"),
                        (b":authority", authority.encode()),
                        (b":path", path.encode()),
                        (b"user-agent", USER_AGENT.encode()),
                    ]
                    + [(k.encode(), v.encode()) for (k, v) in headers.items()],
            end_stream=not data,
        )
        if data:
            self._http.send_data(
                stream_id=stream_id, data=data, end_stream=True  # TODO: encode data if type is str
            )

        waiter = self._loop.create_future()
        self._request_events[stream_id] = deque()
        self._request_waiter[stream_id] = waiter
        self.transmit()

        await asyncio.shield(waiter)

        return self.http_response_data, self.http_response_headers
