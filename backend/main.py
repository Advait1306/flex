from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import facts_router, freewrite_router, todos_router, transcription_router
import store

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(freewrite_router)
app.include_router(todos_router)
app.include_router(facts_router)
app.include_router(transcription_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
