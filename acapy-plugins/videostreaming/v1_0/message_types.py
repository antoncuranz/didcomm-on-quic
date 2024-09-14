
# TODO: replace DID
PROTOCOL_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/videostreaming/1.0"

FETCH_CHUNK = f"{PROTOCOL_URI}/fetchchunk"
FETCH_CHUNK_RESPONSE = f"{PROTOCOL_URI}/fetchchunk_response"

PROTOCOL_PACKAGE = "videostreaming.v1_0"

MESSAGE_TYPES = {
    FETCH_CHUNK: f"{PROTOCOL_PACKAGE}.messages.fetchchunk.FetchChunk",
    FETCH_CHUNK_RESPONSE: f"{PROTOCOL_PACKAGE}.messages.fetchchunk_response.FetchChunkResponse",
}
