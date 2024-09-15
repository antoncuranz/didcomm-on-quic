from os import urandom

from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)
from aries_cloudagent.messaging.decorators.attach_decorator import AttachDecorator
from aries_cloudagent.protocols.present_proof.v2_0.manager import V20PresManager
from aries_cloudagent.protocols.present_proof.v2_0.messages.pres_format import V20PresFormat
from aries_cloudagent.protocols.present_proof.v2_0.messages.pres_request import V20PresRequest

from ..messages.registerservice import RegisterService
from ..models import RegisteredServiceRecord


class RegisterServiceHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"RegisterServiceHandler called")
        assert isinstance(context.message, RegisterService)

        self._logger.info(
            "Received serviceregistry message from: %s with content - %s", context.message_receipt.sender_did,
            context.message
        )

        msg = RegisteredServiceRecord(schema=context.message.schema, did=context.connection_record.their_did,
                                      credentials=[])

        try:
            async with context.profile.session() as session:
                await msg.save(session, reason="Registered new service")
                self._logger.info(msg)

            self._logger.info("Send webhook with topic registered_service")
            await responder.send_webhook("registered_service", msg.serialize())

            restrictions = [{"issuer_did": "NB5Rjw6kpkMcwmcUQeLhKt"}]

            # VC 1
            await self.send_present_proof_request(context, responder, {
                "0_car_registration": {
                    "name": "registration",
                    "restrictions": restrictions
                }
            })

            # VC 2
            await self.send_present_proof_request(context, responder, {
                "0_car_make": {
                    "name": "make",
                    "restrictions": restrictions
                },
                "0_car_model": {
                    "name": "model",
                    "restrictions": restrictions
                },
                "0_car_year": {
                    "name": "year",
                    "restrictions": restrictions
                }
            })

            # TODO: update record once proof was presented

        except Exception as err:
            self._logger.error(err)
            raise err

    async def send_present_proof_request(self, context, responder, requested_attributes):
        pres_manager = V20PresManager(context.profile)

        request = {
            "name": "Proof of Identity",
            "version": "1.0",
            "requested_attributes": requested_attributes,
            "requested_predicates": {},
            "nonce": str(int.from_bytes(urandom(10), "big"))
        }

        pres_request_message = V20PresRequest(
            formats=[V20PresFormat(
                attach_id="indy",
                format_="hlindy/proof-req@v2.0"
            )],
            request_presentations_attach=[AttachDecorator.data_base64(mapping=request, ident="indy")]
        )

        await pres_manager.create_exchange_for_request(
            connection_id=context.connection_record.connection_id,
            pres_request_message=pres_request_message
        )

        # pres_request_message.assign_thread_from(context.message)
        pres_request_message.assign_trace_from(context.message)
        await responder.send_reply(pres_request_message)
