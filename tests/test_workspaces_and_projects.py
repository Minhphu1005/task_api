import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_workspace_crud_members_and_rbac(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="owner@example.com", full_name="Owner")
    editor = await register_and_login(client, email="editor@example.com", full_name="Editor")
    viewer = await register_and_login(client, email="viewer@example.com", full_name="Viewer")
    outsider = await register_and_login(client, email="outsider@example.com", full_name="Outsider")

    ws_resp = await client.post(
        "/api/v1/workspaces",
        headers=owner["headers"],
        json={"name": "Engineering"},
    )
    assert ws_resp.status_code == 201
    ws_id = ws_resp.json()["id"]

    # Invite with both email and user_id (or neither) returns 422
    both_ids = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"email": "editor@example.com", "user_id": editor["user"]["id"], "role": "EDITOR"},
    )
    assert both_ids.status_code == 422

    neither_id = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"role": "EDITOR"},
    )
    assert neither_id.status_code == 422

    # Invite editor and viewer
    inv_editor = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"email": "editor@example.com", "role": "EDITOR"},
    )
    assert inv_editor.status_code == 201

    inv_viewer = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"user_id": viewer["user"]["id"], "role": "VIEWER"},
    )
    assert inv_viewer.status_code == 201

    # Outsider gets 404 (prevents workspace ID enumeration)
    outsider_get = await client.get(f"/api/v1/workspaces/{ws_id}", headers=outsider["headers"])
    assert outsider_get.status_code == 404

    # Editor cannot update workspace name (OWNER only -> 403)
    editor_patch = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=editor["headers"],
        json={"name": "Hacked"},
    )
    assert editor_patch.status_code == 403

    # Explicit null for workspace name returns 422
    null_ws = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner["headers"],
        json={"name": None},
    )
    assert null_ws.status_code == 422

    # Owner updates workspace
    owner_patch = await client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner["headers"],
        json={"name": "Core Engineering"},
    )
    assert owner_patch.status_code == 200
    assert owner_patch.json()["name"] == "Core Engineering"

    # Workspace list supports pagination
    ws_list = await client.get(
        "/api/v1/workspaces",
        headers=owner["headers"],
        params={"page": 1, "limit": 10},
    )
    assert ws_list.status_code == 200
    assert len(ws_list.json()) == 1

    # Editor can create a project, viewer cannot
    viewer_proj = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=viewer["headers"],
        json={"name": "Blocked Project"},
    )
    assert viewer_proj.status_code == 403

    editor_proj = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=editor["headers"],
        json={"name": "Backend API", "description": "FastAPI rewrite"},
    )
    assert editor_proj.status_code == 201
    proj_id = editor_proj.json()["id"]

    # Explicit null for project name returns 422
    null_proj = await client.patch(
        f"/api/v1/projects/{proj_id}",
        headers=editor["headers"],
        json={"name": None},
    )
    assert null_proj.status_code == 422

    # Editor cannot archive project via PATCH (status field is not accepted on PATCH)
    editor_sneaky = await client.patch(
        f"/api/v1/projects/{proj_id}",
        headers=editor["headers"],
        json={"name": "Backend API v2", "status": "ARCHIVED"},
    )
    assert editor_sneaky.status_code == 200
    assert editor_sneaky.json()["status"] == "ACTIVE"

    # Viewer can read project
    viewer_read = await client.get(f"/api/v1/projects/{proj_id}", headers=viewer["headers"])
    assert viewer_read.status_code == 200

    # Only owner can archive project
    editor_archive = await client.post(
        f"/api/v1/projects/{proj_id}/archive",
        headers=editor["headers"],
    )
    assert editor_archive.status_code == 403

    owner_archive = await client.post(
        f"/api/v1/projects/{proj_id}/archive",
        headers=owner["headers"],
    )
    assert owner_archive.status_code == 200
    assert owner_archive.json()["status"] == "ARCHIVED"

    # Remove viewer from workspace -> viewer now gets 404
    remove_resp = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{viewer['user']['id']}",
        headers=owner["headers"],
    )
    assert remove_resp.status_code == 204

    viewer_after = await client.get(f"/api/v1/workspaces/{ws_id}", headers=viewer["headers"])
    assert viewer_after.status_code == 404
