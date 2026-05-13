"""
Integration tests: Project lifecycle.

Tests cover the full happy path AND key error cases:
  - Registration and authentication
  - Project creation (PLANNING status)
  - Status transition (PLANNING → ACTIVE)
  - Task creation in active project
  - Task status transition
  - Authorization checks (non-member cannot create tasks)

Each test is independent — conftest.py truncates tables between tests.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

class TestAuth:
    async def test_register_success(self, client: AsyncClient) -> None:
        """New user registration returns 201 with user data and token."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "full_name": "New User",
            "password": "strongpassword1",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert "user" in body
        assert "token" in body
        assert body["user"]["email"] == "newuser@example.com"
        assert body["user"]["username"] == "newuser"
        assert "hashed_password" not in body["user"]
        assert body["token"]["token_type"] == "bearer"
        assert body["token"]["access_token"] != ""

    async def test_register_duplicate_email(
        self, client: AsyncClient, registered_user: dict
    ) -> None:
        """Registration with duplicate email returns 409."""
        payload = {
            "email": "testuser@example.com",  # already registered by fixture
            "username": "differentusername",
            "password": "anotherpassword1",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    async def test_login_success(
        self, client: AsyncClient, registered_user: dict
    ) -> None:
        """Valid credentials return a bearer token."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser@example.com", "password": "securepassword123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"] != ""

    async def test_login_wrong_password(
        self, client: AsyncClient, registered_user: dict
    ) -> None:
        """Wrong password returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["error"] == "AuthenticationError"


# ---------------------------------------------------------------------------
# Project lifecycle tests
# ---------------------------------------------------------------------------

class TestProjectLifecycle:
    async def test_create_project(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Owner can create a project — starts in PLANNING status."""
        payload = {"name": "My First Project", "description": "Test project"}
        response = await client.post(
            "/api/v1/projects/", json=payload, headers=auth_headers
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "My First Project"
        assert body["slug"] == "my-first-project"
        assert body["status"] == "planning"
        assert body["total_members"] == 1  # owner only

    async def test_create_project_duplicate_slug(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Creating two projects with same name → second returns 409."""
        payload = {"name": "Duplicate Project"}
        await client.post("/api/v1/projects/", json=payload, headers=auth_headers)
        response = await client.post(
            "/api/v1/projects/", json=payload, headers=auth_headers
        )
        assert response.status_code == 409
        assert response.json()["error"] == "ConflictError"

    async def test_activate_project(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Owner can transition project from PLANNING to ACTIVE."""
        # Create
        create_resp = await client.post(
            "/api/v1/projects/",
            json={"name": "Activation Test"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]

        # Activate
        response = await client.patch(
            f"/api/v1/projects/{project_id}/status",
            json={"status": "active"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    async def test_invalid_status_transition(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """PLANNING → COMPLETED is an invalid transition → 422."""
        create_resp = await client.post(
            "/api/v1/projects/",
            json={"name": "Invalid Transition"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/projects/{project_id}/status",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"] == "ValidationError"

    async def test_list_my_projects(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """GET /projects/ returns only the owner's projects."""
        await client.post(
            "/api/v1/projects/", json={"name": "Project A"}, headers=auth_headers
        )
        await client.post(
            "/api/v1/projects/", json={"name": "Project B"}, headers=auth_headers
        )
        response = await client.get("/api/v1/projects/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_get_project_not_found(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Non-existent project UUID → 404 with NotFoundError."""
        fake_id = "00000000-0000-0000-0000-000000000001"
        response = await client.get(
            f"/api/v1/projects/{fake_id}", headers=auth_headers
        )
        assert response.status_code == 404
        assert response.json()["error"] == "NotFoundError"


# ---------------------------------------------------------------------------
# Full end-to-end: register → project → activate → task → transition
# ---------------------------------------------------------------------------

class TestFullProjectTaskFlow:
    async def test_complete_workflow(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """
        Full happy path:
        1. Create project
        2. Activate project
        3. Create task
        4. Transition task to IN_PROGRESS
        5. Verify task status
        """
        # 1. Create project
        proj_resp = await client.post(
            "/api/v1/projects/",
            json={"name": "E2E Workflow Project"},
            headers=auth_headers,
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        # 2. Activate
        activate_resp = await client.patch(
            f"/api/v1/projects/{project_id}/status",
            json={"status": "active"},
            headers=auth_headers,
        )
        assert activate_resp.status_code == 200

        # 3. Create task
        task_resp = await client.post(
            f"/api/v1/projects/{project_id}/tasks/",
            json={"title": "First Task", "priority": "high"},
            headers=auth_headers,
        )
        assert task_resp.status_code == 201
        task_body = task_resp.json()
        task_id = task_body["id"]
        assert task_body["status"] == "backlog"
        assert task_body["priority"] == "high"

        # 4. Transition: BACKLOG → TODO
        todo_resp = await client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/status",
            json={"status": "todo"},
            headers=auth_headers,
        )
        assert todo_resp.status_code == 200
        assert todo_resp.json()["status"] == "todo"

        # 5. Transition: TODO → IN_PROGRESS
        inprog_resp = await client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth_headers,
        )
        assert inprog_resp.status_code == 200
        body = inprog_resp.json()
        assert body["status"] == "in_progress"
        assert body["started_at"] is not None

    async def test_non_member_cannot_create_task(
        self,
        client: AsyncClient,
        auth_headers: dict,
        registered_user_2: dict,
    ) -> None:
        """
        User2 is not a member of User1's project.
        Attempting to create a task returns 403.
        """
        # User1 creates and activates project
        proj_resp = await client.post(
            "/api/v1/projects/",
            json={"name": "Members Only Project"},
            headers=auth_headers,
        )
        project_id = proj_resp.json()["id"]
        await client.patch(
            f"/api/v1/projects/{project_id}/status",
            json={"status": "active"},
            headers=auth_headers,
        )

        # User2 tries to create a task
        user2_token = registered_user_2["token"]["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        response = await client.post(
            f"/api/v1/projects/{project_id}/tasks/",
            json={"title": "Unauthorized Task"},
            headers=user2_headers,
        )
        assert response.status_code == 403
        assert response.json()["error"] == "AuthorizationError"

    async def test_task_on_inactive_project_rejected(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Creating a task on a PLANNING project → 422 ValidationError."""
        proj_resp = await client.post(
            "/api/v1/projects/",
            json={"name": "Inactive Project"},
            headers=auth_headers,
        )
        project_id = proj_resp.json()["id"]
        # Project stays in PLANNING — no activation

        response = await client.post(
            f"/api/v1/projects/{project_id}/tasks/",
            json={"title": "Task on inactive project"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"] == "ValidationError"