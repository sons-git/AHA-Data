from fastapi import FastAPI
from app.api.routes import conversations, users, model_query

app = FastAPI()

app.include_router(conversations.router)
app.include_router(users.router)
app.include_router(model_query.router)