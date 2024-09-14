from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.fetchchunk_response import FetchChunkResponse
from ..messages.fetchchunk import FetchChunk


class FetchChunkHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"QueryServicesHandler called")
        assert isinstance(context.message, FetchChunk)

        self._logger.info(
            "Received videostreaming message from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        if not context.connection_ready:
            self._logger.info(
                "Connection not active, skipping videostreaming response: %s",
                context.message_receipt.sender_did,
            )
            return

        try:
            reply = FetchChunkResponse(chunk="chunk")
            reply.assign_thread_from(context.message)
            reply.assign_trace_from(context.message)
            await responder.send_reply(reply)

        except Exception as err:
            self._logger.error("Error replying to FetchChunk message: " + str(err))
