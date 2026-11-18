# Todo App

A simple todo list application backed by PostgreSQL, built for the DKubeX platform.

## Features

- Create, update, and delete tasks
- Mark tasks as complete
- PostgreSQL storage
- DKubeX platform integration (SSO, base-path routing)

## Quick Start (Local Development)

```bash
# Start PostgreSQL
docker run -d --name todo-pg -e POSTGRES_USER=todo -e POSTGRES_PASSWORD=todo_pass \
  -e POSTGRES_DB=todo -p 5432:5432 postgres:16

# Install dependencies
pip install -r requirements.txt

# Run the app
export DATABASE_URL=postgresql://todo:todo_pass@localhost:5432/todo
uvicorn main:app --reload
```

## Docker Image

```bash
docker pull ghcr.io/sharmistha2023/todo-app:0.1.0
```

## Helm Chart (DKubeX)

Add the Helm repository:

```bash
helm repo add todo-app https://sharmistha2023.github.io/todo-app
helm repo update
```

Install:

```bash
helm install my-todo todo-app/todo-app \
  --set postgres.db_url="postgresql://user:pass@host:5432/db"
```

## DKubeX Platform

When installed via the DKubeX catalog, the platform automatically:
- Provisions a PostgreSQL database
- Injects the connection string via `postgres.db_url`
- Routes the app under its base path with SSO authentication

## License

MIT
