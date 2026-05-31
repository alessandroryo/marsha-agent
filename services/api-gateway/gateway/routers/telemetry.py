from fastapi import APIRouter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/")
async def get_telemetry():
    # TODO: baca dari Redis state:bot:telemetry
    return {
        "status": "IDLE",
        "current_pnl": 0.0,
        "open_positions": 0,
    }
