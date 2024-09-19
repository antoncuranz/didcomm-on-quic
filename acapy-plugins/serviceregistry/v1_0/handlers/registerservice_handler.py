import asyncio
import re
from os import urandom

from aries_cloudagent.core.event_bus import EventBus
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

        msg = RegisteredServiceRecord(schema=context.message.schema, did=context.connection_record.their_did)

        try:
            async with context.profile.session() as session:
                await msg.save(session, reason="Registered new service")
                self._logger.info(msg)

            self._logger.info("Send webhook with topic registered_service")
            await responder.send_webhook("service_registry", msg.serialize_with_state("created"))

            restrictions = [{"issuer_did": "NB5Rjw6kpkMcwmcUQeLhKt"}]

            # VC 1
            task1 = await self.send_present_proof_request(context, responder, msg, {
                "1_car_registration": {
                    "name": "registration",
                    "restrictions": restrictions
                },
                "2_car_reg_expiration": {
                    "name": "expiration",
                    "restrictions": restrictions
                }
            })

            # VC 2
            task2 = await self.send_present_proof_request(context, responder, msg, {
                "1_car_make": {
                    "name": "make",
                    "restrictions": restrictions
                },
                "2_car_model": {
                    "name": "model",
                    "restrictions": restrictions
                },
                "3_car_year": {
                    "name": "year",
                    "restrictions": restrictions
                }
            })

            await asyncio.gather(task1, task2)

        except Exception as err:
            self._logger.error(err)
            raise err

    async def send_present_proof_request(self, context, responder, msg, requested_attributes):
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

        pres_ex_record = await pres_manager.create_exchange_for_request(
            connection_id=context.connection_record.connection_id,
            pres_request_message=pres_request_message
        )

        # pres_request_message.assign_thread_from(context.message)
        pres_request_message.assign_trace_from(context.message)
        await responder.send_reply(pres_request_message)

        # update record once proof was presented
        return asyncio.create_task(
            self._wait_for_event_and_update_record(context, responder, msg, pres_ex_record.pres_ex_id)
        )

    async def _wait_for_event_and_update_record(self, context, responder, msg, pres_ex_id):
        event_bus = context.inject(EventBus)
        with event_bus.wait_for_event(
                context.profile,
                re.compile("^acapy::record::present_proof_v2_0::done$"),
                lambda event: event.payload.get("pres_ex_id") == pres_ex_id
        ) as await_event:
            event = await await_event

            indy = event.payload["by_format"]["pres"]["indy"]
            schema = indy["identifiers"][0]["schema_id"]
            attrs = indy["requested_proof"]["revealed_attrs"]
            attrs = dict(sorted(attrs.items())).values()
            attrs_concat = " ".join([attr["raw"] for attr in attrs])

            async with context.profile.session() as session:
                msg.credentials[schema] = attrs_concat
                await msg.save(session, reason="Updated service after Proof")
                self._logger.info(msg)
                await responder.send_webhook("service_registry", msg.serialize_with_state("updated"))
