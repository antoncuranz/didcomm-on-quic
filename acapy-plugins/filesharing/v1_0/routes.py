import base64
import re
import time

from aiohttp import web
from aiohttp_apispec import docs, match_info_schema
from aries_cloudagent.connections.models.conn_record import ConnRecord
from aries_cloudagent.core.event_bus import EventBus, Event
from aries_cloudagent.messaging.valid import UUIDFour
from aries_cloudagent.storage.error import StorageNotFoundError
from marshmallow import fields, Schema

from .messages.retrievefile import RetrieveFile


class ConnIdMatchInfoSchema(Schema):
    """Path parameters and validators for request taking connection id."""

    conn_id = fields.Str(
        description="Connection identifier", required=True, example=UUIDFour.EXAMPLE
    )
    filename = fields.Str(
        description="Filename", required=True, example="README.md"
    )


@docs(tags=["file sharing"], summary="Retrieve a file")
@match_info_schema(ConnIdMatchInfoSchema())
async def retrieve_file(request: web.BaseRequest):
    context = request["context"]
    connection_id = request.match_info["conn_id"]
    filename = request.match_info["filename"]
    outbound_handler = request["outbound_message_router"]

    try:
        async with context.profile.session() as session:
            connection = await ConnRecord.retrieve_by_id(session, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    if not connection.is_ready:
        raise web.HTTPBadRequest()

    msg = RetrieveFile(filename=filename)
    req_time = time.perf_counter()
    await outbound_handler(msg, connection_id=connection_id)

    event_bus = context.inject(EventBus)
    with event_bus.wait_for_event(
            context.profile,
            re.compile("^acapy::webhook::retrievefile_result$"),
            lambda event: event.payload.get("filename") == filename
    ) as await_event:
        event = await await_event
        if event.payload["status"] == 200:
            rsp_time = time.perf_counter()
            msg = "BM(file): {};{};{};{}".format(filename, req_time, rsp_time, rsp_time-req_time)
            await event_bus.notify(context.profile, Event("acapy::webhook::retrievefile_metrics", msg))
            
            try:
                file_content = base64.b64decode(event.payload["data"])
            except (TypeError, ValueError) as e:
                return web.Response(status=400, text="Invalid base64 content")

            return web.Response(
                body=file_content,
                status=200,
                headers={
                    'Content-Disposition': f'attachment; filename="{event.payload["filename"]}"',
                    'Content-Type': 'application/octet-stream'
                }
            )
        else:
            return web.Response(text="Error", status=event.payload["status"])


async def register(app: web.Application):
    """Register routes."""

    app.add_routes([
        web.get("/connections/{conn_id}/filesharing/{filename:.*}", retrieve_file),
    ])
