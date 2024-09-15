import base64

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

        chunk = context.message.chunk

        try:
            data = self.encode_file_to_base64(chunk)
            reply = FetchChunkResponse(status=200, chunk=chunk, data=data)
        except Exception as err:
            self._logger.error("Error encoding file: " + str(err))
            reply = FetchChunkResponse(status=404, chunk=chunk)

        try:
            reply.assign_thread_from(context.message)
            reply.assign_trace_from(context.message)
            await responder.send_reply(reply)
        except Exception as err:
            self._logger.error("Error replying to FetchChunk message: " + str(err))


    def encode_file_to_base64(self, file_path):
        # Read the file in binary mode
        with open(file_path, "rb") as file:
            file_content = file.read()

        # Encode the file content to Base64
        encoded_content = base64.b64encode(file_content)

        # Convert bytes to string
        encoded_string = encoded_content.decode("utf-8")

        return encoded_string
