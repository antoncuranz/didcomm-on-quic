from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.retrievefile_response import RetrieveFileResponse

class RetrieveFileResponseHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):
        self._logger.info("RetrieveFileResponseHandler called")
        assert isinstance(context.message, RetrieveFileResponse)

        self._logger.info(
            "Received filesharing response from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        self._logger.info("Send webhook with topic retrievefile_result")
        await responder.send_webhook(
            "retrievefile_result",
            {
                "conn_id": context.connection_record.connection_id,
                "status": context.message.status,
                "filename": context.message.filename,
                # "data": context.message.data
            },
        )
