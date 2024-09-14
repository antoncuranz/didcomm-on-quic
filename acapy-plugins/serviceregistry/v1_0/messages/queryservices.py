from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema
from marshmallow import fields

from ..message_types import QUERY_SERVICES, PROTOCOL_PACKAGE

HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.queryservices_handler.QueryServicesHandler"


class QueryServices(AgentMessage):
    class Meta:
        handler_class = HANDLER_CLASS
        message_type = QUERY_SERVICES
        schema_class = "QueryServicesSchema"

    def __init__(self, *, schema: str = None, **kwargs):
        super(QueryServices, self).__init__(**kwargs)
        self.schema = schema


class QueryServicesSchema(AgentMessageSchema):
    class Meta:
        model_class = QueryServices

    schema = fields.Str(
        required=False,
        description="Filter for specific DIDComm schema",
        allow_none=True
    )
