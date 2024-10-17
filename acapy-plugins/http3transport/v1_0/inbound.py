"""Http3 Transport classes and functions."""

import logging
from typing import Coroutine, Any, Optional

from aiohttp import web
from aioquic.asyncio import serve
from aioquic.asyncio.server import QuicServer
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.logger import QuicFileLogger
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from aries_cloudagent.messaging.error import MessageParseError
from aries_cloudagent.transport.error import WireFormatParseError
from aries_cloudagent.transport.wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE
from aries_cloudagent.transport.inbound.base import BaseInboundTransport, InboundTransportSetupError
from .http3_protocol import Http3ServerProtocol

LOGGER = logging.getLogger(__name__)


class Http3Transport(BaseInboundTransport):
    """Http3 Transport class."""

    def __init__(self, host: str, port: int, create_session, **kwargs) -> None:
        """Initialize an inbound HTTP/3 transport instance.

        Args:
            host: Host to listen on
            port: Port to listen on
            create_session: Method to create a new inbound session

        """
        super().__init__("http3", create_session, **kwargs)
        self.host = host
        self.port = port
        self.coroutine: Optional[Coroutine[Any, Any, QuicServer]] = None

    def make_application(self) -> Starlette:
        """Construct the starlette application."""
        return Starlette(
            routes=[
                Route("/", self.invite_message_handler, methods=["GET"]),
                Route("/", self.inbound_message_handler, methods=["POST"]),
            ]
        )

    def create_protocol(self, *args, **kwargs):
        app = self.make_application()
        protocol = Http3ServerProtocol(*args, **kwargs)
        protocol.set_app(app)
        return protocol

    async def start(self) -> None:
        """Start this transport.

        Raises:
            InboundTransportSetupError: If there was an error starting the webserver

        """
        configuration = QuicConfiguration(
            alpn_protocols=H3_ALPN,
            max_datagram_frame_size=65536,
            is_client=False,
            # quic_logger=QuicFileLogger("logs")
        )

        configuration.load_cert_chain("certs/ssl.crt", "certs/ssl.key")

        try:
            self.coroutine = await serve(
                self.host,
                self.port,
                configuration=configuration,
                create_protocol=self.create_protocol,
            )
        except OSError:
            raise InboundTransportSetupError(
                "Unable to start webserver with host "
                + f"'{self.host}' and port '{self.port}'\n"
            )

    async def stop(self) -> None:
        """Stop this transport."""
        self.coroutine.close()

    async def inbound_message_handler(self, request: Request):
        """Message handler for inbound messages.

        Args:
            request: aiohttp request object

        Returns:
            The web response

        """
        body = await request.body()

        client_info = {"host": request.url.netloc, "remote": request.client.host}

        session = await self.create_session(
            accept_undelivered=True, can_respond=True, client_info=client_info
        )

        async with session:
            try:
                inbound = await session.receive(body)
            except (MessageParseError, WireFormatParseError):
                raise web.HTTPBadRequest()

            if inbound.receipt.direct_response_requested:
                # Wait for the message to be processed. Only send a response if a response
                # buffer is present.
                await inbound.wait_processing_complete()
                response = (
                    await session.wait_response() if session.response_buffer else None
                )

                # no more responses
                session.can_respond = False
                session.clear_response()

                if response:
                    if isinstance(response, bytes):
                        return Response(
                            content=response,
                            status_code=200,
                            headers={
                                "content-type": (
                                    DIDCOMM_V1_MIME_TYPE
                                    if session.profile.settings.get(
                                        "emit_new_didcomm_mime_type"
                                    )
                                    else DIDCOMM_V0_MIME_TYPE
                                )
                            },
                        )
                    else:
                        return Response(
                            content=response,
                            status_code=200,
                            headers={"content-type": "application/json"},
                        )
        return Response(status_code=200)

    async def invite_message_handler(self, request: Request):
        """Message handler for invites.

        Args:
            request: aiohttp request object

        Returns:
            The web response

        """
        if request.query_params.get("c_i"):
            return web.Response(
                text="You have received a connection invitation. To accept the "
                "invitation, paste it into your agent application."
            )
        else:
            return Response(status_code=200)
