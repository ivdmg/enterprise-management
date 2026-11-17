"""Additional credential lifecycle checks for the disposable composed API scenario."""

import asyncio

from httpx import AsyncClient
from sqlalchemy import text


async def check_access_edges(call, transport, client_origin, director, operator, company, engine, deliver_one, latest_token):
    address = "edge-viewer@example.com"
    secret = "synthetic-edge-password"
    path = f"/platform/companies/{company}/invitations"
    req = await call(director, "POST", "/company/access-requests", 201,
                     json={"email": address, "full_name": "Test Viewer", "role": "viewer"})
    invitation = await call(operator, "POST", path, 201, json={"access_request_id": req["id"]},
                            headers={"Idempotency-Key": "qa02-credential-edge"})
    assert await deliver_one()
    old_token = latest_token(address)
    async with engine.begin() as db:
        from app.services.platform_auth import token_hash
        assert await db.scalar(text("""
            UPDATE auth_grants SET expires_at = now() - interval '1 minute'
            WHERE token_hash = :token AND purpose = 'client_invite' RETURNING 1
        """), {"token": token_hash(old_token)}) == 1

    async with (
        AsyncClient(transport=transport, base_url=client_origin) as first,
        AsyncClient(transport=transport, base_url=client_origin) as second,
    ):
        accept_path = "/auth/invitation/accept"
        payload = {"token": old_token, "password": secret, "full_name": "Test Viewer"}
        await call(first, "POST", accept_path, 410, json=payload)
        reissued = await call(operator, "POST", path + f"/{invitation['id']}/reissue", 200,
                              json={"version": invitation["version"], "reason": "QA expired invite"})
        assert reissued["version"] == invitation["version"] + 1 and await deliver_one()
        await call(first, "POST", accept_path, 410, json=payload)
        payload["token"] = latest_token(address)
        assert payload["token"] != old_token

        async def try_accept(client):
            csrf = await client.get("/api/v1/auth/csrf")
            response = await client.post("/api/v1" + accept_path, json=payload,
                                         headers={"Origin": client_origin, "X-CSRF-Token": csrf.json()["data"]["csrf_token"]})
            return response.status_code

        assert sorted(await asyncio.gather(try_accept(first), try_accept(second))) == [200, 410]
        login = {"company_code": "smoke-a", "email": address, "password": secret}
        profile = (await call(first, "POST", "/auth/login", 200, json=login))["profile"]
        assert profile["role"] == "viewer"
        await call(first, "POST", "/company/access-requests", 403,
                   json={"email": "forbidden@example.com", "full_name": "Denied", "role": "viewer"})

        director_profile = await call(director, "GET", "/auth/me", 200)
        directors = await call(director, "GET", "/company/users", 200)
        director_version = next(user["version"] for user in directors if user["id"] == director_profile["id"])
        await call(director, "PATCH", f"/company/users/{director_profile['id']}", 409,
                   json={"version": director_version, "is_active": False})

        reset_request = {"company_code": "smoke-a", "email": address}
        reset_result = await call(second, "POST", "/auth/password/forgot", 202, json=reset_request)
        unknown_result = await call(second, "POST", "/auth/password/forgot", 202,
                                    json=reset_request | {"email": "unknown-qa@example.com"})
        assert reset_result == unknown_result == {"state": "accepted"}
        reset_token = latest_token(address)
        new_secret = "synthetic-reset-password"
        reset_payload = {"token": reset_token, "password": new_secret}
        await call(second, "POST", "/auth/password/reset", 200, json=reset_payload)
        await call(second, "POST", "/auth/password/reset", 410, json=reset_payload)
        await call(first, "GET", "/auth/me", 401)
        await call(second, "POST", "/auth/login", 401, json=login)
        await call(second, "POST", "/auth/login", 200, json=login | {"password": new_secret})
    print("Credential edge smoke passed: expiry, reissue, concurrent acceptance, last director and reset.")
