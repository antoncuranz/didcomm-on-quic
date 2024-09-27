import base64
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

from ..messages.requeststream_response import RequestStreamResponse
from ..messages.requeststream import RequestStream


class RequestStreamHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"RequestStreamHandler called")
        assert isinstance(context.message, RequestStream)

        self._logger.info(
            "Received videostreaming message from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        if not context.connection_ready:
            self._logger.info(
                "Connection not active, skipping videostreaming response: %s",
                context.message_receipt.sender_did,
            )
            return

        restrictions = [{"issuer_did": "NB5Rjw6kpkMcwmcUQeLhKt"}]

        await self.send_present_proof_request_and_wait(context, responder, {
            "1_first_name": {
                "name": "first_name",
                "restrictions": restrictions
            },
            "2_last_name": {
                "name": "last_name",
                "restrictions": restrictions
            }
        })

        try:
            manifest = "stream.mpd"
            data = self.encode_file_to_base64(manifest)
            reply = RequestStreamResponse(name=manifest, data=data)
        except Exception as err:
            self._logger.error("Error encoding file: " + str(err))
            reply = RequestStreamResponse(name="ERROR", data=None)

        try:
            reply.assign_thread_from(context.message)
            reply.assign_trace_from(context.message)
            await responder.send_reply(reply)
        except Exception as err:
            self._logger.error("Error replying to RequestStream message: " + str(err))

    def encode_file_to_base64(self, file_path):
        # Read the file in binary mode
        with open(file_path, "rb") as file:
            file_content = file.read()

        # Encode the file content to Base64
        encoded_content = base64.b64encode(file_content)

        # Convert bytes to string
        encoded_string = encoded_content.decode("utf-8")

        return encoded_string

    async def send_present_proof_request_and_wait(self, context, responder, requested_attributes):
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

        # wait for proof
        event_bus = context.inject(EventBus)
        with event_bus.wait_for_event(
                context.profile,
                re.compile("^acapy::record::present_proof_v2_0::done$"),
                lambda event: event.payload.get("pres_ex_id") == pres_ex_record.pres_ex_id
        ) as await_event:
            await await_event
