from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import zoning, layout

app = FastAPI(title="AI Land Layout Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zoning.router,  prefix="/api", tags=["Zoning"])
app.include_router(layout.router,  prefix="/api", tags=["Layout"])

@app.get("/")
def root():
    return {"status": "AI Land Optimizer Backend Running ✅"}

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}