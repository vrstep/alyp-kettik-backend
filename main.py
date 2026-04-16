from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_pool
from routers import recognize, checkout, products, auth, sessions, entry


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
app.include_router(entry.router)
app.include_router(recognize.router)
app.include_router(checkout.router)
app.include_router(products.router)


# Serve turnstile web app at /turnstile/
_turnstile_dir = Path(__file__).parent / "turnstile"
if _turnstile_dir.exists():
    app.mount("/turnstile", StaticFiles(directory=str(_turnstile_dir), html=True), name="turnstile")


@app.get("/health")
async def health():
    return {"status": "ok"}