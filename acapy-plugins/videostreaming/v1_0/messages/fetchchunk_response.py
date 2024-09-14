from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import FETCH_CHUNK_RESPONSE, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.fetchchunk_response_handler.FetchChunkResponseHandler"


class FetchChunkResponse(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = FETCH_CHUNK_RESPONSE
        schema_class = "FetchChunkResponseSchema"

    def __init__(self, *, chunk: str, **kwargs):
        super(FetchChunkResponse, self).__init__(kwargs)
        self.chunk = chunk


class FetchChunkResponseSchema(AgentMessageSchema):
    class Meta:
        model_class = FetchChunkResponse

    chunk = fields.Str(
        required=True,
        description="Encoded chunk content"
    )
