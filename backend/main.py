import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from routers import auth_router, daemon_router, facts_router, freewrite_router, todos_router, transcription_router
import store

DB_URL = os.getenv("DATABASE_URL", "postgres://flex:flex@localhost:5433/flex")
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgres://", 1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["db_models"]},
    )
    await Tortoise.generate_schemas()
    store.init()
    yield
    await Tortoise.close_connections()


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(daemon_router)
app.include_router(freewrite_router)
app.include_router(todos_router)
app.include_router(facts_router)
app.include_router(transcription_router)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
