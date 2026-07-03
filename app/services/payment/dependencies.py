from datetime import datetime, timezone


def ttl_from_expiry(expires_at: str | None) -> int | None:
    if not expires_at:
        return None
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    seconds_left = (expiry - datetime.now(timezone.utc)).total_seconds()
    return max(int(seconds_left), 0) or None

def bank_code_exists(code: str, banks: list[dict]) -> bool:
    return any(bank["code"] == code for bank in banks)