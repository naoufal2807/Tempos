from fastapi import FastAPI
from .core.config import settings
from .db.session import init_db
from .api.v1 import health, tasks, query

app = FastAPI(title=settings.APP_NAME)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router,  prefix=settings.API_V1_PREFIX)
app.include_router(query.router,  prefix=settings.API_V1_PREFIX)

@app.on_event("startup")
def on_startup():
    init_db()
