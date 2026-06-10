# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pydantic v2 camelCase base model (PLAT-09).

``CamelModel`` is the single mechanism for mapping snake_case Python/DB field
names to camelCase JSON. Every model inherits it; do not hand-map fields.

- ``alias_generator=to_camel`` emits camelCase aliases (``lxc_ip`` -> ``lxcIp``).
- ``populate_by_name=True`` accepts snake_case field names on input.
- ``from_attributes=True`` allows construction from ORM-ish / Row objects.

Serialize at the boundary with ``model_dump(by_alias=True)`` to emit camelCase.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: snake_case in, camelCase out via the alias generator."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
