from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_pool
from routers import recognize, checkout, products, auth, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    pool = await get_pool()
    await pool.close()


app = FastAPI(title="Cashierless API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(recognize.router)
app.include_router(checkout.router)
app.include_router(products.router)


@app.get("/health")
async def health():
    return {"status": "ok"}