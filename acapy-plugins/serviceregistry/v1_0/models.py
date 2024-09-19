from aries_cloudagent.messaging.models.base_record import BaseRecord, BaseRecordSchema
from marshmallow import fields


class RegisteredServiceRecord(BaseRecord):
    RECORD_ID_NAME = "record_id"
    RECORD_TYPE = "registeredservice"

    class Meta:
        schema_class = "RegisteredServiceRecordSchema"

    def __init__(
            self,
            *,
            record_id: str = None,
            schema: str = None,
            did: str = None,
            credentials: dict = {},
            **kwargs,
    ):
        """Initialize a new SchemaRecord."""
        super().__init__(record_id, **kwargs)
        self.schema = schema
        self.did = did
        self.credentials = credentials

    @property
    def record_id(self) -> str:
        """Accessor for this schema's id."""
        return self._id

    @property
    def record_value(self) -> dict:
        """Get record value."""
        return {
            prop: getattr(self, prop)
            for prop in ("schema", "did", "credentials")
        }

    def serialize_with_state(self, state):
        serialized = super().serialize()
        serialized["state"] = state
        return serialized


class RegisteredServiceRecordSchema(BaseRecordSchema):
    class Meta:
        model_class = RegisteredServiceRecord

    schema = fields.Str(required=True)
    did = fields.Str(required=True)
    credentials = fields.Dict(
        keys=fields.Str(),
        values=fields.Str(),
        required=False,
        allow_none=True,
    )
