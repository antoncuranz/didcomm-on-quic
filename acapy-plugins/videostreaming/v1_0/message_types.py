
# TODO: replace DID
PROTOCOL_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/videostreaming/1.0"

REQUEST_STREAM = f"{PROTOCOL_URI}/requeststream"
REQUEST_STREAM_RESPONSE = f"{PROTOCOL_URI}/requeststream_response"
FETCH_CHUNK = f"{PROTOCOL_URI}/fetchchunk"
FETCH_CHUNK_RESPONSE = f"{PROTOCOL_URI}/fetchchunk_response"

PROTOCOL_PACKAGE = "acapy-plugins.videostreaming.v1_0"

MESSAGE_TYPES = {
    REQUEST_STREAM: f"{PROTOCOL_PACKAGE}.messages.requeststream.RequestStream",
    REQUEST_STREAM_RESPONSE: f"{PROTOCOL_PACKAGE}.messages.requeststream_response.RequestStreamResponse",
    FETCH_CHUNK: f"{PROTOCOL_PACKAGE}.messages.fetchchunk.FetchChunk",
    FETCH_CHUNK_RESPONSE: f"{PROTOCOL_PACKAGE}.messages.fetchchunk_response.FetchChunkResponse",
}
