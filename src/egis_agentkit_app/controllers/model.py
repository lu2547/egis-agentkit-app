"""Model catalog HTTP endpoints."""

from fastapi import APIRouter, Depends, Request

from ..security import current_user
from .dependencies import services

router = APIRouter()


@router.get("/models")
async def list_models(request: Request, user=Depends(current_user)):
    return services(request).models.list()
