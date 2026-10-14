"""Typed source-to-projection identity checks for standalone structural validators."""
from __future__ import annotations
import json

def validate_source_projection(source_rows: list[dict], projection_rows: list[dict]) -> None:
    if not isinstance(source_rows,list) or not isinstance(projection_rows,list) or source_rows!=projection_rows:
        raise ValueError('Derived assignment projection differs from hashed decision-shard source')
    for row in projection_rows:
        for field in ('source_ids','source_urls','warnings','rule_ids'):
            raw=row.get(field)
            if not isinstance(raw,str):raise ValueError(field+': expected serialized JSON list')
            try:items=json.loads(raw)
            except (TypeError,ValueError) as e:raise ValueError(field+': invalid JSON') from e
            if not isinstance(items,list) or (field!='warnings' and not items) or any(
                not isinstance(item,str) or not item.strip() for item in items):
                raise ValueError(field+': expected typed nonempty strings (or empty warnings)')
            if field=='source_urls' and any(
                not (url.startswith('https://') or url.startswith('evidence/nan/')) for url in items):
                raise ValueError(field+': unreviewed provenance locator')
