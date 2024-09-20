from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import REQUEST_STREAM_RESPONSE, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.requeststream_response_handler.RequestStreamResponseHandler"


class RequestStreamResponse(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = REQUEST_STREAM_RESPONSE
        schema_class = "RequestStreamResponseSchema"

    def __init__(self, *, name: str, data: str = None, **kwargs):
        super(RequestStreamResponse, self).__init__(kwargs)
        self.name = name
        self.data = data


class RequestStreamResponseSchema(AgentMessageSchema):
    class Meta:
        model_class = RequestStreamResponse

    name = fields.Str(
        required=False,
        description="Stream name"
    )
    data = fields.Str(
        required=False,
        description="Base64 encoded manifest data"
    )
