import hashlib
import hmac


def generate_audit_hash(
    secret_key: str,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int | None,
    previous_hash: str | None,
) -> str:
    payload = "|".join(
        [
            str(user_id),
            action,
            resource_type,
            str(resource_id) if resource_id is not None else "",
            previous_hash or "",
        ]
    )

    return hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_audit_hash(
    secret_key: str,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int | None,
    previous_hash: str | None,
    stored_hash: str,
) -> bool:
    expected_hash = generate_audit_hash(
        secret_key=secret_key,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_hash=previous_hash,
    )

    return hmac.compare_digest(expected_hash.encode("ascii"), stored_hash.encode("utf-8"))