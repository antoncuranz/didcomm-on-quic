
# TODO: replace DID
PROTOCOL_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/filesharing/1.0"

RETRIEVE_FILE = f"{PROTOCOL_URI}/retrievefile"
RETRIEVE_FILE_RESPONSE = f"{PROTOCOL_URI}/retrievefile_response"

PROTOCOL_PACKAGE = "acapy-plugins.filesharing.v1_0"

MESSAGE_TYPES = {
    RETRIEVE_FILE: f"{PROTOCOL_PACKAGE}.messages.retrievefile.RetrieveFile",
    RETRIEVE_FILE_RESPONSE: f"{PROTOCOL_PACKAGE}.messages.retrievefile_response.RetrieveFileResponse",
}
