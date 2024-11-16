from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import RETRIEVE_FILE, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.retrievefile_handler.RetrieveFileHandler"


class RetrieveFile(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = RETRIEVE_FILE
        schema_class = "RetrieveFileSchema"

    def __init__(self, *, filename: str = None, **kwargs):
        super(RetrieveFile, self).__init__(**kwargs)
        self.filename = filename


class RetrieveFileSchema(AgentMessageSchema):
    class Meta:
        model_class = RetrieveFile

    filename = fields.Str(
        required=False,
        description="Filename",
        allow_none=True
    )
