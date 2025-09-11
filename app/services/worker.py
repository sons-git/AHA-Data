import base64
from uuid import uuid4
import multiprocessing
import httpx
from app.database.redis_client import get_redis_config
from app.services.manage_responses.response_streamer import stream_response
from app.services.manage_responses.web_search import search
from app.utils.common import classify_message
from app.utils.file_processing import handle_file_processing

from fastapi import APIRouter
import asyncio

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

base_url = get_redis_config("api_keys")["BACKEND_URL"]

# In-Memory Async Queue + Results Store
job_queue: asyncio.Queue = asyncio.Queue()
job_results = {}
job_counter = 0

# Async Worker (runs forever)
async def worker():
    """Background worker that processes jobs from the queue."""

    while True:
        job_id, job = await job_queue.get()
        try:
            job_type = job["type"]
            if job_type == "stream":
                processed_file = await handle_file_processing(
                    job["message"].content, job["message"].files
                )
                classified_message = await classify_message(
                    processed_file, job["user_id"]
                )
                result = await stream_response(
                    job["conversation_id"], job["message"], classified_message
                )

            elif job_type == "websearch":
                search_results = await search(job["message"].content)
                result = await stream_response(job["conversation_id"], job["message"], search_results)

            elif job_type == "speech_to_text":
                async with httpx.AsyncClient(base_url=base_url) as client:
                    response = await client.post(
                        "/api/conversations/speech_to_text",
                        json=job["data"],
                        timeout=30.0
                    )
                    response.raise_for_status()
                    result = response.json()

            elif job_type == "text_to_speech":
                async with httpx.AsyncClient(base_url=base_url, timeout=300) as client:
                    backend_response = await client.post(
                        "/api/conversations/text_to_speech",
                        json=job["data"]
                    )
                    backend_response.raise_for_status()
                    # Return raw bytes
                    result = {
                        "audio": base64.b64encode(backend_response.content).decode("utf-8")
                    }

            job_results[job_id]["status"] = "done"
            job_results[job_id]["result"] = result
        except Exception as e:
            job_results[job_id]["status"] = "error"
            job_results[job_id]["result"] = str(e)
        finally:
            job_queue.task_done()

async def enqueue_job(job: dict) -> str:
    """Enqueue a job for processing and return its job ID.
    Args:
        job (dict): The job data to process.
    Returns:
        str: The job ID.
    """
    job_id = str(uuid4())
    job_results[job_id] = {"status": "pending", "result": None}
    await job_queue.put((job_id, job))
    return job_id

# Kick off worker when app starts 
def start_worker(app):
    """Start the background worker when the FastAPI app starts."""
    loop = asyncio.get_event_loop()
    
    # Detect number of CPU cores
    cpu_count = multiprocessing.cpu_count()
    
    # Set number of workers dynamically
    num_workers = cpu_count * 5  
    
    for _ in range(num_workers):
        loop.create_task(worker())
    
    print(f"Started {num_workers} background workers on {cpu_count} CPU cores.")


# Routes
@router.get("/{job_id}")
async def get_job_result(job_id: str):
    """Fetch result of a previously submitted job.
    Args:
        job_id (str): The ID of the job to fetch.
    Returns:
        dict: A dictionary containing the job status and result (if done).
    """
    job = job_results.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "pending"}

    response = {
        "job_id": job_id,
        "status": job["status"],
        "result": job["result"],
    }

    # If job is finished, delete it after serving once
    if job["status"] in ("done", "error") and job["result"] is not None:
        job_results.pop(job_id, None)

    return response



