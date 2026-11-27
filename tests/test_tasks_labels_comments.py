from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.cache import cache_service, project_tasks_cache_key
from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_tasks_filtering_pagination_cache_and_notifications(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="pm@example.com", full_name="Project Manager")
    dev = await register_and_login(client, email="dev@example.com", full_name="Developer")
    dev2 = await register_and_login(client, email="dev2@example.com", full_name="Developer 2")

    ws_id = (
        await client.post(
            "/api/v1/workspaces",
            headers=owner["headers"],
            json={"name": "Product"},
        )
    ).json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"user_id": dev["user"]["id"], "role": "EDITOR"},
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"user_id": dev2["user"]["id"], "role": "EDITOR"},
    )

    proj_id = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            headers=owner["headers"],
            json={"name": "Mobile App"},
        )
    ).json()["id"]

    with patch("app.services.task.send_task_assigned_email") as mock_notify:
        t1 = await client.post(
            f"/api/v1/projects/{proj_id}/tasks",
            headers=owner["headers"],
            json={
                "title": "Build 100% login screen",
                "priority": "HIGH",
                "status": "IN_PROGRESS",
                "assignee_id": dev["user"]["id"],
            },
        )
        assert t1.status_code == 201
        task1_id = t1.json()["id"]
        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["recipient_email"] == "dev@example.com"

        # Reassigning to dev2 triggers exactly one new email
        mock_notify.reset_mock()
        reassigned = await client.patch(
            f"/api/v1/tasks/{task1_id}",
            headers=owner["headers"],
            json={"assignee_id": dev2["user"]["id"]},
        )
        assert reassigned.status_code == 200
        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["recipient_email"] == "dev2@example.com"

    await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        json={"title": "Setup CI pipeline", "priority": "URGENT", "status": "TODO"},
    )
    await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        json={"title": "Write API docs", "priority": "LOW", "status": "DONE"},
    )

    # Search escapes '%' wildcard properly (only matches the task containing literal '100%')
    search_pct = await client.get(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        params={"search": "100%"},
    )
    assert search_pct.status_code == 200
    assert search_pct.json()["total"] == 1
    assert search_pct.json()["items"][0]["id"] == task1_id

    # Filter by priority & status
    filtered = await client.get(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        params={"priority": "HIGH", "status": "IN_PROGRESS"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    # Pagination + cache population
    page1 = await client.get(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=owner["headers"],
        params={"page": 1, "limit": 2},
    )
    assert page1.status_code == 200
    p1_data = page1.json()
    assert p1_data["total"] == 3
    assert p1_data["total_pages"] == 2
    assert len(p1_data["items"]) == 2

    key = project_tasks_cache_key(
        proj_id,
        status=None,
        priority=None,
        assignee_id=None,
        search=None,
        page=1,
        limit=2,
    )
    assert await cache_service.get_json(key) is not None

    # Updating a task invalidates the cache and subsequent GET returns fresh data
    upd = await client.patch(
        f"/api/v1/tasks/{task1_id}",
        headers=dev["headers"],
        json={"status": "DONE"},
    )
    assert upd.status_code == 200
    assert await cache_service.get_json(key) is None

    # PATCH with explicit null for NOT NULL fields returns 422 (not 500)
    for bad_body in ({"title": None}, {"status": None}, {"priority": None}):
        bad_patch = await client.patch(
            f"/api/v1/tasks/{task1_id}",
            headers=dev["headers"],
            json=bad_body,
        )
        assert bad_patch.status_code == 422

    # Whitespace-only title returns 422
    ws_title = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        json={"title": "   "},
    )
    assert ws_title.status_code == 422


@pytest.mark.asyncio
async def test_labels_comments_archived_and_non_member_404(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="lead@example.com", full_name="Lead")
    viewer = await register_and_login(client, email="qa@example.com", full_name="QA Viewer")
    outsider = await register_and_login(client, email="ext@example.com", full_name="Outsider")

    ws_id = (
        await client.post(
            "/api/v1/workspaces",
            headers=owner["headers"],
            json={"name": "QA Team"},
        )
    ).json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner["headers"],
        json={"user_id": viewer["user"]["id"], "role": "VIEWER"},
    )

    proj_id = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            headers=owner["headers"],
            json={"name": "Release 1.0"},
        )
    ).json()["id"]

    task_id = (
        await client.post(
            f"/api/v1/projects/{proj_id}/tasks",
            headers=owner["headers"],
            json={"title": "Verify checkout flow"},
        )
    ).json()["id"]

    # Non-member gets 404 (not 403) when probing task ID
    assert (
        await client.get(f"/api/v1/tasks/{task_id}", headers=outsider["headers"])
    ).status_code == 404

    # Create label & attach to task
    lbl = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        headers=owner["headers"],
        json={"name": "bug", "color": "#EF4444"},
    )
    assert lbl.status_code == 201
    label_id = lbl.json()["id"]

    # PATCH label with explicit null returns 422
    assert (
        await client.patch(
            f"/api/v1/labels/{label_id}",
            headers=owner["headers"],
            json={"name": None},
        )
    ).status_code == 422

    attached = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner["headers"],
    )
    assert attached.status_code == 200
    assert len(attached.json()["labels"]) == 1

    # Whitespace-only comment returns 422
    assert (
        await client.post(
            f"/api/v1/tasks/{task_id}/comments",
            headers=viewer["headers"],
            json={"content": "   "},
        )
    ).status_code == 422

    comment = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=viewer["headers"],
        json={"content": "Reproduced on staging!"},
    )
    assert comment.status_code == 201
    viewer_comment_id = comment.json()["id"]

    owner_comment = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=owner["headers"],
        json={"content": "Investigating now."},
    )
    assert owner_comment.status_code == 201
    owner_comment_id = owner_comment.json()["id"]

    # Viewer cannot delete owner's comment (403); outsider gets 404
    assert (
        await client.delete(f"/api/v1/comments/{owner_comment_id}", headers=viewer["headers"])
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/comments/{owner_comment_id}", headers=outsider["headers"])
    ).status_code == 404

    # Removed member cannot delete their own historical comment (404)
    await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{viewer['user']['id']}",
        headers=owner["headers"],
    )
    assert (
        await client.delete(f"/api/v1/comments/{viewer_comment_id}", headers=viewer["headers"])
    ).status_code == 404

    # Archive project -> all write operations (task/label/comment) are blocked with 400
    await client.post(f"/api/v1/projects/{proj_id}/archive", headers=owner["headers"])

    assert (
        await client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner["headers"],
            json={"title": "Should fail"},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/v1/projects/{proj_id}/labels",
            headers=owner["headers"],
            json={"name": "blocked"},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/v1/tasks/{task_id}/comments",
            headers=owner["headers"],
            json={"content": "Should fail"},
        )
    ).status_code == 400
    assert (
        await client.delete(f"/api/v1/comments/{owner_comment_id}", headers=owner["headers"])
    ).status_code == 400
