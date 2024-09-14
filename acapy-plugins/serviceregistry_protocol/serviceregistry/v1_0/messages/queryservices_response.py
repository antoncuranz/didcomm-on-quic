
from marshmallow import fields

from aries_cloudagent.messaging.agent_message import AgentMessage, AgentMessageSchema

from ..models import RegisteredServiceRecord, RegisteredServiceRecordSchema

from ..message_types import QUERY_SERVICES_RESPONSE, PROTOCOL_PACKAGE


HANDLER_CLASS = f"{PROTOCOL_PACKAGE}.handlers.queryservices_response_handler.QueryServicesResponseHandler"


class QueryServicesResponse(AgentMessage):

    class Meta:
        handler_class = HANDLER_CLASS
        message_type = QUERY_SERVICES_RESPONSE
        schema_class = "QueryServicesResponseSchema"

    def __init__(self, *, services: list[RegisteredServiceRecord], **kwargs):
        super(QueryServicesResponse, self).__init__(kwargs)
        self.services = services


class QueryServicesResponseSchema(AgentMessageSchema):

    class Meta:
        model_class = QueryServicesResponse

    services = fields.List(
        fields.Nested(RegisteredServiceRecordSchema()),
        required=True,
        description="List of registered services"
    )

