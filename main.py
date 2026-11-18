"""A simple todo list app: FastAPI + PostgreSQL, one page.

Built for the DKubeX platform app standard:
- Served under a base path ($DKUBEX_BASE_PATH, e.g. /todo-app).
- Identity comes from the gateway's X-Auth-Request-* headers; there is no app login.
- The database connection is injected by the platform (postgres.db_url -> DATABASE_URL).
"""

import os
from contextlib import asynccontextmanager

import psycopg
import psycopg.rows as rows
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://todo:todo_pass@localhost:5432/todo"
)
BASE_PATH = os.environ.get("DKUBEX_BASE_PATH", "")
MAX_TITLE = 200


def auth_header(request: Request) -> str | None:
    """Return the authenticated username from the gateway, or 'local' for dev runs."""
    if BASE_PATH:
        return request.headers.get("X-Auth-Request-User")
    return "local"


def require_user(request: Request) -> str:
    user = auth_header(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    yield


app = FastAPI(title="Todo List", lifespan=lifespan)

# Create a router for all routes; we'll mount it at BASE_PATH (or "/" for local dev)
router = APIRouter()


def db():
    return psycopg.connect(DB_URL, row_factory=rows.dict_row)


def ok(data):
    return JSONResponse({"ok": True, "data": data})


def err(message, status=400):
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def get_task(task_id: int) -> dict | None:
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s", (task_id,))
            return cur.fetchone()


@router.get("/health")
def health():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok"}


@router.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@router.get("/api/tasks")
def list_tasks(request: Request):
    require_user(request)
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, done FROM tasks ORDER BY created_at DESC, id DESC")
                tasks = cur.fetchall()
        return ok(tasks)
    except Exception as e:
        return err(f"Database error: {e}", 500)


@router.post("/api/tasks", status_code=201)
def create_task(request: Request, body: dict):
    require_user(request)
    title = (body.get("title") or "").strip()
    if not title:
        return err("Title is required")
    if len(title) > MAX_TITLE:
        return err(f"Title must be at most {MAX_TITLE} characters")
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, done",
                    (title,),
                )
                task = cur.fetchone()
        return ok(task)
    except Exception as e:
        return err(f"Database error: {e}", 500)


@router.put("/api/tasks/{task_id}")
def update_task(request: Request, task_id: int, body: dict):
    require_user(request)
    task = get_task(task_id)
    if not task:
        return err("Task not found", 404)

    title = body.get("title")
    done = body.get("done")

    if title is not None:
        title = title.strip()
        if not title:
            return err("Title cannot be empty")
        if len(title) > MAX_TITLE:
            return err(f"Title must be at most {MAX_TITLE} characters")

    try:
        with db() as conn:
            with conn.cursor() as cur:
                if title is not None and done is not None:
                    cur.execute(
                        "UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING id, title, done",
                        (title, done, task_id),
                    )
                elif title is not None:
                    cur.execute(
                        "UPDATE tasks SET title = %s WHERE id = %s RETURNING id, title, done",
                        (title, task_id),
                    )
                elif done is not None:
                    cur.execute(
                        "UPDATE tasks SET done = %s WHERE id = %s RETURNING id, title, done",
                        (done, task_id),
                    )
                else:
                    return ok(task)
                updated = cur.fetchone()
        return ok(updated)
    except Exception as e:
        return err(f"Database error: {e}", 500)


@router.delete("/api/tasks/{task_id}")
def delete_task(request: Request, task_id: int):
    require_user(request)
    task = get_task(task_id)
    if not task:
        return err("Task not found", 404)
    try:
        with db() as conn:
            conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        return ok({"deleted": task_id})
    except Exception as e:
        return err(f"Database error: {e}", 500)


# Mount router at BASE_PATH (gateway forwards full path, so app must match it)
# For local dev (no BASE_PATH), mount at root
mount_path = BASE_PATH if BASE_PATH else ""
app.include_router(router, prefix=mount_path)
