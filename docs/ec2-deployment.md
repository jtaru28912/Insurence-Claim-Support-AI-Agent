# EC2 Deployment Guide

This project ships with a manual GitHub Actions deployment workflow for an Ubuntu-based EC2 host. The workflow only deploys after Ruff and pytest pass, verifies `/health`, and rolls back to the previous release if the health check fails.

## Expected EC2 layout

```text
/opt/insurance-claims-ai/
|-- current -> /opt/insurance-claims-ai/releases/<git-sha>
|-- releases/
|-- shared/
|   |-- .env
|   `-- storage/
|       |-- db/
|       `-- vector_store/
`-- last_successful_release.txt
```

## One-time EC2 setup

1. Install Docker Engine and Docker Compose plugin.
2. Create the application directories under `/opt/insurance-claims-ai`.
3. Put the production `.env` file at `/opt/insurance-claims-ai/shared/.env`.
4. Open inbound ports `8000` and `8501`, or place the services behind Nginx and only expose `80`/`443`.
5. Add the following GitHub repository secrets:
   - `EC2_HOST`
   - `EC2_USERNAME`
   - `EC2_SSH_PRIVATE_KEY`
   - `EC2_APP_DIR`

## Local container verification

Run this before relying on the deployment workflow:

```bash
docker compose up --build
curl http://localhost:8000/health
```

Streamlit should then be available at `http://localhost:8501`.

## Deployment flow

1. Trigger `.github/workflows/deploy.yml` manually from GitHub Actions.
2. The workflow reruns `ruff check .` and `pytest tests -q`.
3. The workflow clones the selected ref onto EC2 as a new release.
4. Shared storage and `.env` are attached to that release.
5. `docker compose up -d` starts the API and Streamlit services.
6. The workflow calls `http://localhost:8000/health` on the EC2 host.

## Rollback procedure

Automatic rollback is already built into the workflow if the deployment or health check step fails after a prior release has been recorded.

Manual rollback on EC2:

```bash
cd /opt/insurance-claims-ai
ln -sfn "$(cat last_successful_release.txt)" current
cd current
docker compose up -d
curl --fail http://localhost:8000/health
```

## Notes

- Keep API keys only in the EC2 `shared/.env` file and GitHub secrets.
- `storage/` is shared across releases so SQLite and Chroma data survive deploys.
- If you front the app with Nginx, proxy `/` to Streamlit on `8501` and API routes to `8000`.
