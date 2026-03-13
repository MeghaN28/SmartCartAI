from __future__ import annotations

import math
from datetime import datetime, date, timezone
from typing import Optional, Union

LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


def _to_datetime(value: Union[str, date, datetime]) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            if len(normalized) >= 19:
                try:
                    return datetime.fromisoformat(normalized[:19])
                except ValueError:
                    pass
            try:
                return datetime.strptime(normalized[:10], "%Y-%m-%d")
            except ValueError:
                return None
    return None


def days_until_expiry(
    expiry_value: Optional[Union[str, date, datetime]],
    now: Optional[datetime] = None,
    tz: Optional[timezone] = None,
) -> Optional[int]:
    """Return whole days between `now` and the expiry timestamp (floor)."""
    if expiry_value is None:
        return None
    target_dt = _to_datetime(expiry_value)
    if target_dt is None:
        return None
    local_tz = tz or LOCAL_TIMEZONE
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=local_tz)
    else:
        target_dt = target_dt.astimezone(local_tz)
    reference = now or datetime.now(local_tz)
    delta_seconds = (target_dt - reference).total_seconds()
    try:
        return math.floor(delta_seconds / 86400)
    except (TypeError, ValueError):
        return None
