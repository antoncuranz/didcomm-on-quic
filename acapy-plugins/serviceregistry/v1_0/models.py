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
            credentials: list[str] = None,
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


class RegisteredServiceRecordSchema(BaseRecordSchema):
    class Meta:
        model_class = RegisteredServiceRecord

    schema = fields.Str(required=True)
    did = fields.Str(required=True)
    credentials = fields.List(
        fields.Str(
            metadata={
                "description": "Role: requester or responder",
                "example": "requester",
            }
        ),
        required=False,
        allow_none=True,
        metadata={"description": "List of roles"},
    )
