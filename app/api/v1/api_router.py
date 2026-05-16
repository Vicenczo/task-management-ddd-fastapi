"""
Central API router — aggregates all v1 endpoint routers.
Imported by main.py via: from app.api.v1.api_router import api_router
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
# Tasks are nested under /projects/{project_id}/tasks —
# The router internally defines /{project_id}/tasks/, so we don't repeat the /projects prefix
api_router.include_router(tasks_router, prefix="/projects", tags=["Tasks"])

# Address: /api/v1/tasks/search-semantic
api_router.include_router(tasks_router, prefix="/tasks", tags=["AI Search"])