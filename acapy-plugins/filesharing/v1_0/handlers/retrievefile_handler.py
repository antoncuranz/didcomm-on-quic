import base64
from urllib.parse import unquote

from aries_cloudagent.messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..messages.retrievefile_response import RetrieveFileResponse
from ..messages.retrievefile import RetrieveFile


class RetrieveFileHandler(BaseHandler):

    async def handle(self, context: RequestContext, responder: BaseResponder):

        self._logger.info(f"RetrieveFileHandler called")
        assert isinstance(context.message, RetrieveFile)

        self._logger.info(
            "Received filesharing message from: %s with content - %s", context.message_receipt.sender_did, context.message
        )

        if not context.connection_ready:
            self._logger.info(
                "Connection not active, skipping filesharing response: %s",
                context.message_receipt.sender_did,
            )
            return

        filename = context.message.filename

        try:
            data = self.encode_file_to_base64(filename)
            reply = RetrieveFileResponse(status=200, filename=filename, data=data)
        except Exception as err:
            self._logger.error("Error encoding file: " + str(err))
            reply = RetrieveFileResponse(status=404, filename=filename)

        try:
            reply.assign_thread_from(context.message)
            reply.assign_trace_from(context.message)
            await responder.send_reply(reply)
        except Exception as err:
            self._logger.error("Error replying to RetrieveFile message: " + str(err))


    def encode_file_to_base64(self, file_path):
        # Read the file in binary mode
        with open(unquote(file_path), "rb") as file:
            file_content = file.read()

        # Encode the file content to Base64
        encoded_content = base64.b64encode(file_content)

        # Convert bytes to string
        encoded_string = encoded_content.decode("utf-8")

        return encoded_string
