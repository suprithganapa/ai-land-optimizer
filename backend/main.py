from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import zoning, layout, export

app = FastAPI(
    title="LandAI Optimizer API",
    description="AI-Powered Residential Land Layout Generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zoning.router,  prefix="/api", tags=["Zoning"])
app.include_router(layout.router,  prefix="/api", tags=["Layout"])
app.include_router(export.router,  prefix="/api", tags=["Export"])

@app.get("/")
def root():
    return {"status": "LandAI Optimizer API running ✅", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}