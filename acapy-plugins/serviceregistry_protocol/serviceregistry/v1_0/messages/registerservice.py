"""Represents a Privacy Preserving Machine Learning Message"""

from ..message_types import REGISTER_SERVICE, PROTOCOL_PACKAGE

from marshmallow import fields


from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.registerservice_handler.RegisterServiceHandler"


class RegisterService(AgentMessage):

    class Meta:
        handler_class = HANDLER_CLASS
        message_type = REGISTER_SERVICE
        schema_class = "RegisterServiceSchema"

    def __init__(self, *, schema: str = None, **kwargs):
        super(RegisterService, self).__init__(**kwargs)
        self.schema = schema


class RegisterServiceSchema(AgentMessageSchema):

    class Meta:
        model_class = RegisterService

    schema = fields.Str(
        required=False,
        description="Filter for specific DIDComm schema",
        allow_none=True
    )
