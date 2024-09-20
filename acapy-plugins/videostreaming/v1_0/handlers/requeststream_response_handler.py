from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.requeststream_response import RequestStreamResponse

class RequestStreamResponseHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):
        self._logger.info("RequestStreamResponseHandler called")
        assert isinstance(context.message, RequestStreamResponse)

        self._logger.info(
            "Received videostreaming response from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        self._logger.info("Send webhook with topic requeststream_result")
        await responder.send_webhook(
            "requeststream_result",
            {
                "name": context.message.name,
                "data": context.message.data,
                "conn_id": context.connection_record.connection_id
            },
        )
