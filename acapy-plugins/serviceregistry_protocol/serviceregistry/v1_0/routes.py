"""Protocol example admin routes."""

from aiohttp import web
from aiohttp_apispec import docs, match_info_schema, request_schema, response_schema
from marshmallow import fields, Schema

from aries_cloudagent.connections.models.conn_record import ConnRecord
from aries_cloudagent.messaging.valid import UUIDFour
from aries_cloudagent.messaging.models.base import BaseModelError
from aries_cloudagent.storage.error import StorageError, StorageNotFoundError

from serviceregistry.v1_0.messages.registerservice import RegisterService
from serviceregistry.v1_0.models import RegisteredServiceRecord

from .messages.queryservices import QueryServices


class ConnIdMatchInfoSchema(Schema):
    """Path parameters and validators for request taking connection id."""

    conn_id = fields.Str(
        description="Connection identifier", required=True, example=UUIDFour.EXAMPLE
    )


class QueryServicesRequestSchema(Schema):
    schema = fields.Str(required=False, description="Filter for specific DIDComm schema")


class QueryServicesRequestResponseSchema(Schema):
    thread_id = fields.Str(required=False, description="Thread ID of the ping message")

@docs(tags=["service registry"], summary="Query registered services")
@match_info_schema(ConnIdMatchInfoSchema())
@request_schema(QueryServicesRequestSchema())
@response_schema(QueryServicesRequestResponseSchema(), 200)
async def query_services(request: web.BaseRequest):
    context = request["context"]
    connection_id = request.match_info["conn_id"]
    outbound_handler = request["outbound_message_router"]
    body = await request.json()
    schema = body.get("schema")

    try:
        async with context.profile.session() as session:
            connection = await ConnRecord.retrieve_by_id(session, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    if not connection.is_ready:
        raise web.HTTPBadRequest()

    msg = QueryServices(schema=schema)
    await outbound_handler(msg, connection_id=connection_id)

    return web.json_response({"thread_id": msg._thread_id})


class RegisterServiceRequestSchema(Schema):
    schema = fields.Str(required=True, description="DIDComm schema of service to register")


class RegisterServiceRequestResponseSchema(Schema):
    thread_id = fields.Str(required=False, description="Thread ID of the ping message")


@docs(tags=["service registry"], summary="Register a service")
@match_info_schema(ConnIdMatchInfoSchema())
@request_schema(RegisterServiceRequestSchema())
@response_schema(RegisterServiceRequestResponseSchema(), 200)
async def register_service(request: web.BaseRequest):
    context = request["context"]
    connection_id = request.match_info["conn_id"]
    outbound_handler = request["outbound_message_router"]
    body = await request.json()
    schema = body.get("schema")

    try:
        async with context.profile.session() as session:
            connection = await ConnRecord.retrieve_by_id(session, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    if not connection.is_ready:
        raise web.HTTPBadRequest()

    msg = RegisterService(schema=schema)
    await outbound_handler(msg, connection_id=connection_id)

    return web.json_response({"thread_id": msg._thread_id})


@docs(tags=["service registry"], summary="List registered services")
async def list_services(request: web.BaseRequest):
    context = request["context"]

    try:
        async with context.profile.session() as session:
            records = await RegisteredServiceRecord.query(session=session)

        results = [record.serialize() for record in records]
        # return sorted by most recent first
        # results.sort(key=lambda x: str_to_epoch(x["created_at"]), reverse=True)
    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"services": results})


async def register(app: web.Application):
    """Register routes."""

    app.add_routes([
        web.post("/connections/{conn_id}/query-services", query_services),
        web.post("/connections/{conn_id}/register-service", register_service),
        web.get("/service-registry/list-services", list_services)
    ])