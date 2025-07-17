from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.utils.text_processing.text_embedding import (
    get_dense_embedder,
    get_sparse_embedder_and_tokenizer
)
from app.api.routes import auth, conversations, model_query, user
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app):
    try:
        embedder = get_dense_embedder()
        tokenizer, embedder = get_sparse_embedder_and_tokenizer()
        print("Application startup completed successfully!")
        yield

    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    finally:
        print("Application shutdown completed successfully!")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(model_query.router)