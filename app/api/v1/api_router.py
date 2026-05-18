"""
Central API router — aggregates all v1 endpoint routers.
Imported by main.py via: from app.api.v1.api_router import api_router

Route map:
  /auth/*                          — auth_router
  /users/*                         — users_router
  /projects/*                      — projects_router
  /projects/{project_id}/tasks/*   — tasks_router   (CRUD, nested)
  /tasks/search-semantic           — ai_tasks_router (AI, flat)
  /tasks/{task_id}/suggest-subtasks — ai_tasks_router (AI, flat)

Route ordering within ai_tasks_router:
  /search-semantic MUST be registered before /{task_id}/suggest-subtasks
  to prevent FastAPI from trying to parse "search-semantic" as a UUID.
  This is already handled by the order of @router.get decorators in ai_tasks.py.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.ai_tasks import router as ai_tasks_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])

# CRUD task endpoints — nested under /projects/{project_id}/tasks/
api_router.include_router(tasks_router, prefix="/projects", tags=["Tasks"])

# AI task endpoints — flat under /tasks/ (cross-project, no project_id needed)
# /tasks/search-semantic and /tasks/{task_id}/suggest-subtasks
api_router.include_router(ai_tasks_router, prefix="/tasks", tags=["AI"])