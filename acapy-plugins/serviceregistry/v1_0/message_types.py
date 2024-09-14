
# TODO: replace DID
PROTOCOL_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/serviceregistry/1.0"

QUERY_SERVICES = f"{PROTOCOL_URI}/queryservices"
QUERY_SERVICES_RESPONSE = f"{PROTOCOL_URI}/queryservices_response"

REGISTER_SERVICE = f"{PROTOCOL_URI}/registerservice"

PROTOCOL_PACKAGE = "serviceregistry.v1_0"

MESSAGE_TYPES = {
    QUERY_SERVICES: f"{PROTOCOL_PACKAGE}.messages.queryservices.QueryServices",
    QUERY_SERVICES_RESPONSE: f"{PROTOCOL_PACKAGE}.messages.queryservices_response.QueryServicesResponse",
    REGISTER_SERVICE: f"{PROTOCOL_PACKAGE}.messages.registerservice.RegisterService",
}
