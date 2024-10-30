"""Http3 outbound transport."""
import asyncio
import logging
import socket
import ssl
import time
from typing import Union, cast, Tuple, Dict
from urllib.parse import urlparse

from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aries_cloudagent.core.profile import Profile
from aries_cloudagent.transport.outbound.base import BaseOutboundTransport, OutboundTransportError
from aries_cloudagent.transport.wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE

from .http3_client import Http3Client
from .config import get_config


class Http3Transport(BaseOutboundTransport):
    """Http3 outbound transport class."""

    schemes = ("http3",)
    is_external = False

    def __init__(self, **kwargs) -> None:
        """Initialize an `Http3Transport` instance."""
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.open_connections: Dict[str, Tuple[Http3Client, float]] = {}
        self.force_close = get_config(self.root_profile.context.settings).force_close
        self.keepalive_timeout = get_config(self.root_profile.context.settings).keepalive_timeout

    async def start(self):
        """Start the transport."""
        return self

    async def stop(self):
        """Stop the transport."""
        pass

    async def handle_message(
        self,
        profile: Profile,
        payload: Union[str, bytes],
        endpoint: str,
        metadata: dict = None,
        api_key: str = None,
    ):
        """Handle message from queue.

        Args:
            profile: the profile that produced the message
            payload: message payload in string or byte format
            endpoint: URI endpoint for delivery
            metadata: Additional metadata associated with the payload
        """
        if not endpoint:
            raise OutboundTransportError("No endpoint provided")
        headers = metadata or {}
        if api_key is not None:
            headers["x-api-key"] = api_key
        if isinstance(payload, bytes):
            if profile.settings.get("emit_new_didcomm_mime_type"):
                headers["content-type"] = DIDCOMM_V1_MIME_TYPE
            else:
                headers["content-type"] = DIDCOMM_V0_MIME_TYPE
        else:
            headers["content-type"] = "application/json"
        self.logger.debug(
            "Posting to %s; Data: %s; Headers: %s", endpoint, payload, headers
        )

        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port
        
        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=H3_ALPN,
            verify_mode=ssl.CERT_NONE,
            server_name=host
        )
        
        if self.force_close:
            async with (connect(
                    host,
                    port,
                    configuration=configuration,
                    create_protocol=Http3Client,
            ) as client):
                client = cast(Http3Client, client)

                headers["content-length"] = str(len(payload))
                return await client.send_http_request(endpoint, "POST", payload, headers)
        
        client = await self.get_connection(endpoint, host, port, configuration)
        headers["content-length"] = str(len(payload))
        rsp = await client.send_http_request(endpoint, "POST", payload, headers)
        
        self.open_connections[endpoint] = (client, time.monotonic())
        return rsp
    
    async def get_connection(self, endpoint, host, port, configuration) -> Http3Client:
        if endpoint in self.open_connections:
            conn_tuple = self.open_connections[endpoint]
            now = time.monotonic()
            if now - conn_tuple[1] < self.keepalive_timeout:
                return cast(Http3Client, conn_tuple[0])
            else:
                conn_tuple[0].close()
                del self.open_connections[endpoint]

        return cast(Http3Client, await self.create_connection(host, port, configuration))

    async def create_connection(self, host, port, configuration):
        loop = asyncio.get_event_loop()
        local_host = "::"

        # lookup remote address
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_DGRAM)
        addr = infos[0][4]
        if len(addr) == 2:
            addr = ("::ffff:" + addr[0], addr[1], 0, 0)

        # prepare QUIC connection
        connection = QuicConnection(
            configuration=configuration,
        )

        # explicitly enable IPv4/IPv6 dual stack
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        completed = False
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            sock.bind((local_host, 0, 0, 0))
            completed = True
        finally:
            if not completed:
                sock.close()
        # connect
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: Http3Client(connection),
            sock=sock,
        )
        protocol = cast(QuicConnectionProtocol, protocol)
        protocol.connect(addr)
        await protocol.wait_connected()
        return protocol
