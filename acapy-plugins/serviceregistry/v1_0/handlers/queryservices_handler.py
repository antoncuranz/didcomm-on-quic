from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.queryservices import QueryServices
from ..messages.queryservices_response import QueryServicesResponse
from ..models import RegisteredServiceRecord


class QueryServicesHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"QueryServicesHandler called")
        assert isinstance(context.message, QueryServices)

        self._logger.info(
            "Received serviceregistry message from: %s with content - %s", context.message_receipt.sender_did,
            context.message
        )

        if not context.connection_ready:
            self._logger.info(
                "Connection not active, skipping serviceregistry response: %s",
                context.message_receipt.sender_did,
            )
            return

        try:
            async with context.profile.session() as session:
                records = await RegisteredServiceRecord.query(session=session, tag_filter={"schema": context.message.schema})

            reply = QueryServicesResponse(services=records)
            reply.assign_thread_from(context.message)
            reply.assign_trace_from(context.message)
            await responder.send_reply(reply)

        except Exception as err:
            self._logger.error("Error replying to QueryServices message: " + str(err))
