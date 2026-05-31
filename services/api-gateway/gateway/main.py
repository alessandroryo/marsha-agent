from fastapi import FastAPI
from gateway.routers import telemetry

app = FastAPI(
    title="marsha-agent API Gateway",
    version="0.1.0",
    description="REST API untuk monitoring dan kontrol marsha-agent trading system",
)

app.include_router(telemetry.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "marsha-agent-gateway"}
