from aiohttp import web
from aiohttp_apispec import docs, match_info_schema, request_schema, response_schema
from aries_cloudagent.connections.models.conn_record import ConnRecord
from aries_cloudagent.core.event_bus import EventBus
from aries_cloudagent.messaging.valid import UUIDFour
from aries_cloudagent.storage.error import StorageNotFoundError
from marshmallow import fields, Schema

from .messages.fetchchunk import FetchChunk


class ConnIdMatchInfoSchema(Schema):
    """Path parameters and validators for request taking connection id."""

    conn_id = fields.Str(
        description="Connection identifier", required=True, example=UUIDFour.EXAMPLE
    )
    chunk = fields.Str(
        description="Chunk name", required=True, example="track_1234.m4s"
    )


class FetchChunkRequestResponseSchema(Schema):
    thread_id = fields.Str(required=False, description="Thread ID of the ping message")


@docs(tags=["video streaming"], summary="Fetch a Chunk")
@match_info_schema(ConnIdMatchInfoSchema())
@response_schema(FetchChunkRequestResponseSchema(), 200)
async def fetch_chunk(request: web.BaseRequest):
    context = request["context"]
    connection_id = request.match_info["conn_id"]
    chunk = request.match_info["chunk"]
    outbound_handler = request["outbound_message_router"]

    try:
        async with context.profile.session() as session:
            connection = await ConnRecord.retrieve_by_id(session, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    if not connection.is_ready:
        raise web.HTTPBadRequest()

    msg = FetchChunk(chunk=chunk)
    await outbound_handler(msg, connection_id=connection_id)

    # test = context.inject(EventBus).wait_for_event(context.profile, "fetchchunk_result")

    return web.json_response({"thread_id": msg._thread_id})


async def register(app: web.Application):
    """Register routes."""

    app.add_routes([
        web.get("/connections/{conn_id}/videostreaming/{chunk}", fetch_chunk),
        # web.post("/connections/{conn_id}/videostreaming/subscribe", subscribe_to_chunks),
    ])
