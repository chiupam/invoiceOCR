"""Unauthenticated liveness/readiness probe (exempt from rate limiting —
kubelet probes hit this every few seconds from one source IP)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", name="main.health")
async def health():
    return {"status": "ok"}
