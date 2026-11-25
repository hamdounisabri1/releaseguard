"""Column types shared by the models: UUID primary keys and UTC timestamps."""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import mapped_column

UuidPk = Annotated[
    uuid.UUID,
    mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")),
]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
Timestamp = Annotated[datetime, mapped_column(DateTime(timezone=True))]
