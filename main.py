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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://todo:todo_pass@localhost:5432/todo"
)
BASE_PATH = os.environ.get("DKUBEX_BASE_PATH", "")
MAX_TITLE = 200


def auth_header(request: Request) -> str | None:
    # The gateway (cookie-auth middleware) sets this after SSO. Local runs (no DKubeX)
    # have no gateway in front, so we only enforce it when deployed as a platform app.
    if BASE_PATH:
        return request.headers.get("X-Auth-Request-User")
    return "local"


def require_user(request: Request) -> str:
    user = auth_header(request)
    if not user:
        # 401 with no login redirect — the platform's reverse proxy owns the login.
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


@app.get("/health")
def health():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/tasks")
def list_tasks(request: Request):
    require_user(request)
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, done FROM tasks ORDER BY created_at DESC, id DESC")
                rows = cur.fetchall()
    except Exception:
        return err("Something went wrong. Please try again.")
    return ok([dict(r) for r in rows])


@app.post("/api/tasks")
async def add_task(request: Request):
    require_user(request)
    try:
        body = await request.json()
    except Exception:
        return err("Task title cannot be empty.")
    title = (body.get("title") or "").strip()
    if not title:
        return err("Task title cannot be empty.")
    if len(title) > MAX_TITLE:
        return err(f"Task title must be {MAX_TITLE} characters or fewer.")
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, done", (title,))
                row = cur.fetchone()
    except Exception:
        return err("Something went wrong. Please try again.")
    return ok(dict(row))


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: int, request: Request):
    require_user(request)
    try:
        body = await request.json()
    except Exception:
        return err("Invalid request. Please try again.")
    existing = get_task(task_id)
    if existing is None:
        return err("Task not found.", 404)
    if "title" in body:
        title = (body["title"] or "").strip()
        if not title:
            return err("Task title cannot be empty.")
        if len(title) > MAX_TITLE:
            return err(f"Task title must be {MAX_TITLE} characters or fewer.")
        existing["title"] = title
    if "done" in body:
        existing["done"] = bool(body["done"])
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET title = %s, done = %s WHERE id = %s",
                    (existing["title"], existing["done"], task_id),
                )
    except Exception:
        return err("Something went wrong. Please try again.")
    return ok({"id": task_id, "title": existing["title"], "done": existing["done"]})


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, request: Request):
    require_user(request)
    existing = get_task(task_id)
    if existing is None:
        return err("Task not found.", 404)
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    except Exception:
        return err("Something went wrong. Please try again.")
    return ok({"deleted": task_id})
