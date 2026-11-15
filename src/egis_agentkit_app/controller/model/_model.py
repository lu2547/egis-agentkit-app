"""Model catalog HTTP endpoints."""

from fastapi import APIRouter, Depends, Request

from ..base import current_user, services

router = APIRouter()


@router.get("/models")
async def list_models(request: Request, user=Depends(current_user)):
    return services(request).models.list()
