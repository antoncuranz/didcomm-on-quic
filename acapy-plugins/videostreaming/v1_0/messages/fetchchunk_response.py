from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import FETCH_CHUNK_RESPONSE, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.fetchchunk_response_handler.FetchChunkResponseHandler"


class FetchChunkResponse(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = FETCH_CHUNK_RESPONSE
        schema_class = "FetchChunkResponseSchema"

    def __init__(self, *, status: int, chunk: str = None, data: str = None, **kwargs):
        super(FetchChunkResponse, self).__init__(kwargs)
        self.status = status
        self.chunk = chunk
        self.data = data


class FetchChunkResponseSchema(AgentMessageSchema):
    class Meta:
        model_class = FetchChunkResponse

    status = fields.Int(
        required=True,
        description="Status code"
    )
    chunk = fields.Str(
        required=False,
        description="Filename of chunk"
    )
    data = fields.Str(
        required=False,
        description="Base64 encoded chunk data"
    )
