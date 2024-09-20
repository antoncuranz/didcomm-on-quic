from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema

from ..message_types import PROTOCOL_PACKAGE, REQUEST_STREAM

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.requeststream_handler.RequestStreamHandler"


class RequestStream(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = REQUEST_STREAM
        schema_class = "RequestStreamSchema"


class RequestStreamSchema(AgentMessageSchema):
    class Meta:
        model_class = RequestStream
