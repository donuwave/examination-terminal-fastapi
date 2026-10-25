import asyncio
import re
from datetime import datetime, timedelta

from sqlalchemy import update

from core.models import PasswordReset
from tests.conftest import PASSWORD, Api
from tests.test_db import TestSessionLocal

AUTH = "/api/v1/auth"
NEW = "new-pass-1"


async def anon(world):
    import httpx

    return httpx.AsyncClient(transport=world["transport"], base_url="http://test")


def code_of(outbox) -> str:
    return re.search(r"\b(\d{6})\b", outbox[-1].text).group(1)


async def login(client, email, password):
    return await client.post(f"{AUTH}/login", data={"email": email, "password": password})


async def test_full_reset_flow(world, outbox):
    client = await anon(world)
    assert (await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})).status_code == 204
    assert len(outbox) == 1 and outbox[0].to == "alice@test.dev"
    code = code_of(outbox)

    assert (await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": code})).status_code == 204
    done = await client.post(
        f"{AUTH}/reset/confirm", json={"email": "alice@test.dev", "code": code, "password": NEW}
    )
    assert done.status_code == 204

    assert (await login(client, "alice@test.dev", PASSWORD)).status_code != 200
    assert (await login(client, "alice@test.dev", NEW)).status_code == 200
    # О смене пароля приходит второе письмо.
    assert len(outbox) == 2 and "изменён" in outbox[1].subject


async def test_unknown_email_looks_the_same_and_sends_nothing(world, outbox):
    client = await anon(world)
    response = await client.post(f"{AUTH}/reset/request", json={"email": "nobody@test.dev"})
    assert response.status_code == 204 and outbox == []


async def test_wrong_code_and_unknown_email_give_same_error(world, outbox):
    client = await anon(world)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    wrong = await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": "000000"})
    unknown = await client.post(f"{AUTH}/reset/verify", json={"email": "nobody@test.dev", "code": "000000"})
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_code_burns_after_five_wrong_attempts(world, outbox):
    client = await anon(world)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    code = code_of(outbox)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": wrong})
    # Даже верный код после этого не принимается.
    response = await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": code})
    assert response.status_code == 400 and "новый код" in response.json()["detail"]


async def test_expired_code_is_rejected(world, outbox):
    client = await anon(world)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    code = code_of(outbox)
    async with TestSessionLocal() as session:
        await session.execute(update(PasswordReset).values(expires_at=datetime.utcnow() - timedelta(minutes=1)))
        await session.commit()
    response = await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": code})
    assert response.status_code == 400


async def test_code_cannot_be_used_twice_and_new_request_cancels_old(world, outbox):
    client = await anon(world)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    first = code_of(outbox)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    second = code_of(outbox)
    # Старый код после нового запроса не работает (если коды случайно не совпали).
    if first != second:
        assert (await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": first})).status_code == 400
    body = {"email": "alice@test.dev", "code": second, "password": NEW}
    assert (await client.post(f"{AUTH}/reset/confirm", json=body)).status_code == 204
    assert (await client.post(f"{AUTH}/reset/confirm", json={**body, "password": "another-1"})).status_code == 400


async def test_other_users_code_does_not_work(world, outbox):
    client = await anon(world)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    code = code_of(outbox)
    response = await client.post(f"{AUTH}/reset/verify", json={"email": "bob@test.dev", "code": code})
    assert response.status_code == 400


async def test_requests_are_rate_limited_per_email(world, outbox):
    client = await anon(world)
    for _ in range(3):
        assert (await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})).status_code == 204
    blocked = await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    assert blocked.status_code == 429
    # Для несуществующей почты лимит тот же, иначе по нему можно отличить адреса.
    for _ in range(3):
        await client.post(f"{AUTH}/reset/request", json={"email": "ghost@test.dev"})
    assert (await client.post(f"{AUTH}/reset/request", json={"email": "ghost@test.dev"})).status_code == 429


async def test_old_refresh_token_stops_working_after_reset(world, outbox):
    alice: Api = world["alice"]
    old = await login(alice.client, "alice@test.dev", PASSWORD)
    refresh = old.json()["refresh_token"]
    client = await anon(world)
    # iat токена и время смены пароля считаются в целых секундах.
    await asyncio.sleep(1.1)
    await client.post(f"{AUTH}/reset/request", json={"email": "alice@test.dev"})
    code = code_of(outbox)
    await client.post(f"{AUTH}/reset/confirm", json={"email": "alice@test.dev", "code": code, "password": NEW})
    refreshed = await client.post(f"{AUTH}/refresh", headers={"Authorization": f"Bearer {refresh}"})
    assert refreshed.status_code == 401


async def test_bad_input_is_rejected(world):
    client = await anon(world)
    assert (await client.post(f"{AUTH}/reset/verify", json={"email": "alice@test.dev", "code": "12"})).status_code == 422
    body = {"email": "alice@test.dev", "code": "123456", "password": "123"}
    assert (await client.post(f"{AUTH}/reset/confirm", json=body)).status_code == 422
