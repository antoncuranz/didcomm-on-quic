from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import FETCH_CHUNK, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.fetchchunk_handler.FetchChunkHandler"


class FetchChunk(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = FETCH_CHUNK
        schema_class = "FetchChunkSchema"

    def __init__(self, *, chunk: str = None, **kwargs):
        super(FetchChunk, self).__init__(**kwargs)
        self.chunk = chunk


class FetchChunkSchema(AgentMessageSchema):
    class Meta:
        model_class = FetchChunk

    chunk = fields.Str(
        required=False,
        description="Name of specific chunk",
        allow_none=True
    )
