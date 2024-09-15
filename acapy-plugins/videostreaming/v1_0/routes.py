import base64
import re

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


@docs(tags=["video streaming"], summary="Fetch a Chunk")
@match_info_schema(ConnIdMatchInfoSchema())
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

    event_bus = context.inject(EventBus)
    with event_bus.wait_for_event(
            context.profile,
            re.compile("^acapy::webhook::fetchchunk_result$"),
            lambda event: event.payload.get("chunk") == chunk
    ) as await_event:
        event = await await_event
        if event.payload["status"] == 200:
            try:
                file_content = base64.b64decode(event.payload["data"])
            except (TypeError, ValueError) as e:
                return web.Response(status=400, text="Invalid base64 content")

            return web.Response(
                body=file_content,
                status=200,
                headers={
                    'Content-Disposition': f'attachment; filename="{event.payload["chunk"]}"',
                    'Content-Type': 'application/octet-stream'
                }
            )
        else:
            return web.Response(text="Error", status=event.payload["status"])


async def register(app: web.Application):
    """Register routes."""

    app.add_routes([
        web.get("/connections/{conn_id}/videostreaming/{chunk}", fetch_chunk),
    ])
