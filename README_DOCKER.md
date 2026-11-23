# Docker setup for SMART_PARKING_ML

This bundle adds a development Docker Compose setup for the repository's four main services:

- React/Vite frontend: `http://localhost:5173`
- ASP.NET Core API: `http://localhost:5049/swagger`
- Python Flask/OCR API: `http://localhost:5000`
- SQL Server: `localhost,14330` by default (container port 1433)

## Files to copy into the repository root

Copy these paths while preserving their folders:

- `docker-compose.yml` -> repository root
- `.dockerignore` -> repository root
- `.env.docker.example` -> repository root
- `Backend/Dockerfile` -> `Backend/Dockerfile`
- `app/Dockerfile` -> `app/Dockerfile`
- `frontend/Dockerfile` -> `frontend/Dockerfile`
- `frontend/vite.config.ts` -> replace the existing file

The Vite config keeps `localhost` as the default for non-Docker development. Compose sets environment variables so Vite proxies to the other containers by service name.

## Run

1. Install and start Docker Desktop with the WSL 2 backend.
2. In PowerShell, go to the repository root.
3. Copy the environment template and edit the password:

   ```powershell
   Copy-Item .env.docker.example .env
   notepad .env
   ```

4. Build and start all services:

   ```powershell
   docker compose up --build -d
   ```

5. Check containers and logs:

   ```powershell
   docker compose ps
   docker compose logs --tail=100
   ```

6. Initialize SQL Server. The Compose file starts an empty SQL Server database engine; it does not automatically execute the project's SQL script. In SSMS connect to `localhost,14330` using SQL Server Authentication (`sa`) and the password from `.env`, enable Trust Server Certificate if prompted, open `database/schema.sql`, and execute it.

7. Open:

   - Frontend: http://localhost:5173
   - Swagger: http://localhost:5049/swagger

## Stop / reset

- Stop containers but keep database data: `docker compose down`
- Delete containers AND all named volume data (including SQL Server database): `docker compose down -v`

Do not use `down -v` unless you intentionally want to erase the database volume.

## Important checks

- If port 14330 is in use, change `SQLSERVER_PORT` in `.env` to another free port. The backend still connects to `sqlserver,1433` inside the Docker network.
- The repository's Python app loads trained Joblib files from `models/classification/best_classification_model.pkl`, `models/regression/best_regression_model.pkl`, and `models/demand/best_demand_model.pkl` when prediction features are used. The repository `.gitignore` excludes `*.pkl`; confirm these files exist locally before building if you need those prediction features. This Dockerfile copies local model files if they exist in the build context, but does not generate them.
- `database/schema.sql` was verified in the repository. The README mentions `database/seed.sql`, but that path was not available when this bundle was prepared; only run it if the file exists in your checkout.
- This is a local development configuration, not a production deployment. Change demo passwords, use HTTPS/reverse proxy, and review debug/development settings before production.
