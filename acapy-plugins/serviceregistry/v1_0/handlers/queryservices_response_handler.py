from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.queryservices_response import QueryServicesResponse


class QueryServicesResponseHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):
        self._logger.info("QueryServicesResponseHandler called")
        assert isinstance(context.message, QueryServicesResponse)

        self._logger.info(
            "Received serviceregistry response from: %s with content - %s", context.message_receipt.sender_did,
            context.message
        )

        services = [service.serialize() for service in context.message.services]

        self._logger.info("Send webhook with topic queryservices_result")
        await responder.send_webhook(
            "queryservices_result",
            {
                "services": services
            },
        )
