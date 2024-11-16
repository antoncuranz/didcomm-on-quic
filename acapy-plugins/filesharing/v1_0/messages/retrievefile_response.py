from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import RETRIEVE_FILE_RESPONSE, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.retrievefile_response_handler.RetrieveFileResponseHandler"


class RetrieveFileResponse(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = RETRIEVE_FILE_RESPONSE
        schema_class = "RetrieveFileResponseSchema"

    def __init__(self, *, status: int, filename: str = None, data: str = None, **kwargs):
        super(RetrieveFileResponse, self).__init__(kwargs)
        self.status = status
        self.filename = filename
        self.data = data


class RetrieveFileResponseSchema(AgentMessageSchema):
    class Meta:
        model_class = RetrieveFileResponse

    status = fields.Int(
        required=True,
        description="Status code"
    )
    filename = fields.Str(
        required=False,
        description="Filename"
    )
    data = fields.Str(
        required=False,
        description="Base64 encoded file data"
    )
