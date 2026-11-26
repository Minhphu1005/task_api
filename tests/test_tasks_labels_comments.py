import pytest
from httpx import AsyncClient

from app.core.cache import cache_service, project_tasks_cache_key
from app.services.notification import sent_notifications
from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_tasks_filtering_pagination_cache_and_notifications(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="pm@example.com", full_name="Project Manager")
    dev = await register_and_login(client, email="dev@example.com", full_name="Developer")

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

    proj_id = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            headers=owner["headers"],
            json={"name": "Mobile App"},
        )
    ).json()["id"]

    # Create 3 tasks, assigning one to dev -> triggers background notification
    t1 = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=owner["headers"],
        json={
            "title": "Build login screen",
            "priority": "HIGH",
            "status": "IN_PROGRESS",
            "assignee_id": dev["user"]["id"],
        },
    )
    assert t1.status_code == 201
    task1_id = t1.json()["id"]

    assert len(sent_notifications) == 1
    assert sent_notifications[0].recipient_email == "dev@example.com"
    assert "Build login screen" in sent_notifications[0].subject

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

    # Filter by priority & status
    filtered = await client.get(
        f"/api/v1/projects/{proj_id}/tasks",
        headers=dev["headers"],
        params={"priority": "HIGH", "status": "IN_PROGRESS"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == task1_id

    # Pagination
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

    # Verify cache key was populated
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

    # Updating a task invalidates the project tasks cache
    upd = await client.patch(
        f"/api/v1/tasks/{task1_id}",
        headers=dev["headers"],
        json={"status": "DONE"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "DONE"
    assert await cache_service.get_json(key) is None


@pytest.mark.asyncio
async def test_labels_and_comments_lifecycle(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="lead@example.com", full_name="Lead")
    viewer = await register_and_login(client, email="qa@example.com", full_name="QA Viewer")

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

    # Create label & attach to task
    lbl = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        headers=owner["headers"],
        json={"name": "bug", "color": "#EF4444"},
    )
    assert lbl.status_code == 201
    label_id = lbl.json()["id"]

    attached = await client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner["headers"],
    )
    assert attached.status_code == 200
    assert len(attached.json()["labels"]) == 1
    assert attached.json()["labels"][0]["name"] == "bug"

    # Viewer can post comment and delete own comment
    comment = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=viewer["headers"],
        json={"content": "Reproduced on staging!"},
    )
    assert comment.status_code == 201
    comment_id = comment.json()["id"]

    owner_comment = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=owner["headers"],
        json={"content": "Investigating now."},
    )
    assert owner_comment.status_code == 201
    owner_comment_id = owner_comment.json()["id"]

    # Viewer cannot delete owner's comment
    forbidden_del = await client.delete(
        f"/api/v1/comments/{owner_comment_id}",
        headers=viewer["headers"],
    )
    assert forbidden_del.status_code == 403

    # Viewer can delete own comment
    own_del = await client.delete(
        f"/api/v1/comments/{comment_id}",
        headers=viewer["headers"],
    )
    assert own_del.status_code == 204

    # Detach label
    detached = await client.delete(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=owner["headers"],
    )
    assert detached.status_code == 200
    assert detached.json()["labels"] == []
