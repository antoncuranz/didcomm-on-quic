"""Http outbound transport."""

import logging
from typing import Optional, Union

from aiohttp import ClientSession, DummyCookieJar, TCPConnector

from aries_cloudagent.core.profile import Profile
from aries_cloudagent.transport.stats import StatsTracer
from aries_cloudagent.transport.wire_format import DIDCOMM_V0_MIME_TYPE, DIDCOMM_V1_MIME_TYPE
from aries_cloudagent.transport.outbound.base import BaseOutboundTransport, OutboundTransportError
from .config import get_config


class HttpsTransport(BaseOutboundTransport):
    """Http outbound transport class."""

    schemes = ("http", "https")
    is_external = False

    def __init__(self, **kwargs) -> None:
        """Initialize an `HttpTransport` instance."""
        super().__init__(**kwargs)
        self.client_session: Optional[ClientSession] = None
        self.connector: Optional[TCPConnector] = None
        self.logger = logging.getLogger(__name__)
        self.force_close = get_config(self.root_profile.context.settings).force_close

    async def start(self):
        """Start the transport."""
        self.connector = TCPConnector(limit=200, limit_per_host=50, verify_ssl=False, force_close=self.force_close)
        session_args = {
            "cookie_jar": DummyCookieJar(),
            "connector": self.connector,
            "trust_env": True,
        }
        if self.collector:
            session_args["trace_configs"] = [
                StatsTracer(self.collector, "outbound-http:")
            ]
        self.client_session = ClientSession(**session_args)
        return self

    async def stop(self):
        """Stop the transport."""
        await self.client_session.close()
        self.client_session = None

    async def handle_message(
        self,
        profile: Profile,
        payload: Union[str, bytes],
        endpoint: str,
        metadata: Optional[dict] = None,
        api_key: Optional[str] = None,
    ):
        """Handle message from queue.

        Args:
            profile: the profile that produced the message
            payload: message payload in string or byte format
            endpoint: URI endpoint for delivery
            metadata: Additional metadata associated with the payload
            api_key: API key for the endpoint
        """
        if not endpoint:
            raise OutboundTransportError("No endpoint provided")
        headers = metadata or {}
        if api_key is not None:
            headers["x-api-key"] = api_key
        if isinstance(payload, bytes):
            if profile.settings.get("emit_new_didcomm_mime_type"):
                headers["Content-Type"] = DIDCOMM_V1_MIME_TYPE
            else:
                headers["Content-Type"] = DIDCOMM_V0_MIME_TYPE
        else:
            headers["Content-Type"] = "application/json"
        self.logger.debug(
            "Posting to %s; Data: %s; Headers: %s", endpoint, payload, headers
        )
        async with self.client_session.post(
            endpoint, data=payload, headers=headers
        ) as response:
            if response.status < 200 or response.status > 299:
                raise OutboundTransportError(
                    (
                        f"Unexpected response status {response.status}, "
                        f"caused by: {response.reason}"
                    )
                )
