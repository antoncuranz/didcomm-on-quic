from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.registerservice import RegisterService
from ..models import RegisteredServiceRecord

class RegisterServiceHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"RegisterServiceHandler called")
        assert isinstance(context.message, RegisterService)

        self._logger.info(
            "Received serviceregistry message from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        msg = RegisteredServiceRecord(schema=context.message.schema, did=context.connection_record.their_did, credentials=[])

        try:
            async with context.profile.session() as session:
                await msg.save(session, reason="Registered new service")
                self._logger.info(msg)

            self._logger.info("Send webhook with topic registered_service")
            await responder.send_webhook("registered_service", msg.serialize())
        except Exception as err:
            self._logger.error(err)
            raise err
