from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import analyze, editing, execute, validate, vnc

app = FastAPI(
    title="FormBot Scraper Service",
    description="Internal scraping microservice for FormBot",
    version="1.0.0"
)

# CORS (internal service, allow all from Docker network)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analyze.router, tags=["analyze"])
app.include_router(execute.router, tags=["execute"])
app.include_router(validate.router, tags=["validate"])
app.include_router(vnc.router, tags=["vnc"])
app.include_router(editing.router, tags=["editing"])


@app.get("/health")
async def health_check():
    from app.services.ollama_client import OllamaClient
    ollama = OllamaClient()
    ollama_ok = await ollama.is_available()

    return {
        "status": "ok",
        "ollama": "connected" if ollama_ok else "unavailable"
    }
