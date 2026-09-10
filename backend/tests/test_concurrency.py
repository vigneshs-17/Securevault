from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import bearer_scheme, get_current_user
from app.db.database import engine
from app.db.dependencies import get_db
from app.main import app

pytestmark = pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires PostgreSQL row locks")
CREDENTIALS = {"email": "test@securevault.com", "password": "SecureVaultFinal456!"}


def post(path, **kwargs):
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post(path, **kwargs)


def login():
    result = post("/auth/login", json=CREDENTIALS)
    assert result.status_code == 200
    return result.json()


def parallel(first, second):
    start = Barrier(2, timeout=10)
    def run(action):
        start.wait()
        return action()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, action) for action in (first, second)]
        return [future.result(timeout=20) for future in futures]


@pytest.fixture
def simultaneous_authenticated_reads():
    # Both requests authenticate against the same committed token version before
    # either enters its handler. The handler must recheck after acquiring a lock.
    ready = Barrier(2, timeout=10)
    def authenticate(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                     db: Session = Depends(get_db)):
        user = get_current_user(credentials, db)
        ready.wait()
        return user
    app.dependency_overrides[get_current_user] = authenticate
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_same_refresh_token_can_only_rotate_once():
    tokens = login()
    def action():
        return post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    results = parallel(action, action)
    assert sorted(r.status_code for r in results) == [200, 401]


def test_concurrent_password_changes_have_one_winner(simultaneous_authenticated_reads):
    tokens = login()
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    def change(password):
        return post("/auth/change-password", headers=headers, json={
            "current_password": CREDENTIALS["password"], "new_password": password})
    results = parallel(lambda: change("ReplacementPassword123!"), lambda: change("OtherPassword456!"))
    assert sorted(r.status_code for r in results) == [200, 401]


def test_password_change_and_logout_all_recheck_revocation(simultaneous_authenticated_reads):
    tokens = login()
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    results = parallel(
        lambda: post("/auth/change-password", headers=headers, json={
            "current_password": CREDENTIALS["password"], "new_password": "ReplacementPassword123!"}),
        lambda: post("/auth/logout-all", headers=headers))
    assert sorted(r.status_code for r in results) == [200, 401]


@pytest.mark.parametrize("revoker", ["logout-all", "change-password"])
def test_refresh_cannot_escape_concurrent_revocation(revoker):
    tokens = login()
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    kwargs = {"headers": headers}
    if revoker == "change-password":
        kwargs["json"] = {"current_password": CREDENTIALS["password"],
                          "new_password": "ReplacementPassword123!"}
    refreshed, revoked = parallel(
        lambda: post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}),
        lambda: post("/auth/" + revoker, **kwargs))
    assert revoked.status_code == 200
    assert refreshed.status_code in {200, 401}
    if refreshed.status_code == 200:
        result = post("/auth/refresh", json={"refresh_token": refreshed.json()["refresh_token"]})
        assert result.status_code == 401
        with TestClient(app) as client:
            assert client.get("/auth/me", headers={
                "Authorization": "Bearer " + refreshed.json()["access_token"]}).status_code == 401
