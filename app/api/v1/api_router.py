"""
API v1 — root router.

All sub-routers are registered here and then mounted into the FastAPI
application under the `/api/v1` prefix (see main.py).

Adding a new resource:
  1. Create `app/api/v1/endpoints/your_resource.py`.
  2. Import its router below and call `api_router.include_router(...)`.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.tasks import my_tasks_router, router as tasks_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()

# --- Auth (public + protected) ---
api_router.include_router(auth_router)

# --- Users ---
api_router.include_router(users_router)

# --- Projects ---
api_router.include_router(projects_router)

# --- Tasks (project-nested) ---
api_router.include_router(tasks_router)

# --- Tasks (user-centric standalone) ---
api_router.include_router(my_tasks_router)