from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.fetchchunk_response import FetchChunkResponse

class FetchChunkResponseHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):
        self._logger.info("FetchChunkResponseHandler called")
        assert isinstance(context.message, FetchChunkResponse)

        self._logger.info(
            "Received videostreaming response from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        self._logger.info("Send webhook with topic fetchchunk_result")
        await responder.send_webhook(
            "fetchchunk_result",
            {
                "status": context.message.status,
                "chunk": context.message.chunk,
                "data": context.message.data
            },
        )
