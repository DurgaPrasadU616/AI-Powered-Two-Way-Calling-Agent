"""Phase 2 contact CRUD tests — E.164 validation included."""

from __future__ import annotations

from httpx import AsyncClient


async def test_create_contact_returns_201(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.post(
        "/contacts",
        json={
            "name": "Rahul Kumar",
            "phone_e164": "+919876543210",
            "company": "Hotel Blue Diamond",
            "purpose": "Commercial RO enquiry",
            "product": "Commercial RO System",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] > 0
    assert body["phone_e164"] == "+919876543210"
    assert body["name"] == "Rahul Kumar"


async def test_create_contact_with_invalid_phone_returns_422(
    client: AsyncClient, auth_headers: dict
) -> None:
    response = await client.post(
        "/contacts",
        json={"name": "Bad Number", "phone_e164": "12345"},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["status_code"] == 422


async def test_create_contact_with_local_format_returns_422(
    client: AsyncClient, auth_headers: dict
) -> None:
    """09876543210 without country code is not E.164."""
    response = await client.post(
        "/contacts",
        json={"name": "No CC", "phone_e164": "09876543210"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_list_contacts_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/contacts")
    assert response.status_code == 401


async def test_list_and_search_contacts(
    client: AsyncClient, auth_headers: dict, make_contact
) -> None:
    await make_contact(name="Rahul Kumar", phone="+919876543210")
    await make_contact(name="Priya Sharma", phone="+919845123456")

    all_rows = await client.get("/contacts", headers=auth_headers)
    assert all_rows.status_code == 200
    assert len(all_rows.json()) == 2

    filtered = await client.get("/contacts", params={"q": "rahul"}, headers=auth_headers)
    assert filtered.status_code == 200
    rows = filtered.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Rahul Kumar"


async def test_get_contact_by_id_and_404(
    client: AsyncClient, auth_headers: dict, make_contact
) -> None:
    created = await make_contact(name="Rahul Kumar")
    found = await client.get(f"/contacts/{created['id']}", headers=auth_headers)
    assert found.status_code == 200
    assert found.json()["name"] == "Rahul Kumar"

    missing = await client.get("/contacts/999999", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["status_code"] == 404


async def test_update_contact(client: AsyncClient, auth_headers: dict, make_contact) -> None:
    created = await make_contact(name="Old Name")
    response = await client.patch(
        f"/contacts/{created['id']}",
        json={"name": "New Name", "phone_e164": "+911122334455"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "New Name"
    assert body["phone_e164"] == "+911122334455"
    # untouched field preserved
    assert body["company"] == created["company"]

    bad = await client.patch(
        f"/contacts/{created['id']}", json={"phone_e164": "12345"}, headers=auth_headers
    )
    assert bad.status_code == 422

    missing = await client.patch("/contacts/999999", json={"name": "x"}, headers=auth_headers)
    assert missing.status_code == 404


async def test_delete_contact(client: AsyncClient, auth_headers: dict, make_contact) -> None:
    created = await make_contact()
    deleted = await client.delete(f"/contacts/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    gone = await client.get(f"/contacts/{created['id']}", headers=auth_headers)
    assert gone.status_code == 404

    again = await client.delete(f"/contacts/{created['id']}", headers=auth_headers)
    assert again.status_code == 404
