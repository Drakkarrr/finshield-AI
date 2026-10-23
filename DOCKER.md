# FinShield AI - Docker Deployment

> **Status.** The root `docker-compose.yml` runs three services: `postgres` (pgvector — RAG store), `backend` (FastAPI, SQLite primary DB until slice S1.1) and `frontend` (Next.js). Images are single-stage and run as root (hardening is slice S6.3). This is a development setup, not a production deployment — see [docs/architecture/evolution/](./docs/architecture/evolution/README.md).

## Quick Start

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2+

### Build and Run

```bash
# Build and start all services
docker compose up --build

# Run in detached mode (background)
docker compose up --build -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8091
- **API Docs**: http://localhost:8091/api/docs

### Environment Variables

Copy `.env.example` to `.env` at the repo root and edit it; compose interpolates these values and refuses to start while required secrets (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`) are unset. Never put real secrets in `docker-compose.yml`.

**Backend:**
- `DATABASE_URL`: Database connection string (default: SQLite)
- `JWT_SECRET_KEY`: Secret key for JWT tokens (CHANGE IN PRODUCTION)
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration (default: 30)
- `DEBUG`: Enable debug mode (default: false)

**Frontend:**
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: http://backend:8091)

### Production Deployment

1. **Change JWT Secret Key**:
   ```bash
   openssl rand -hex 32
   ```
   Set `JWT_SECRET_KEY` in `.env` (or your platform's secret store)

2. **Use PostgreSQL** (recommended for production):
   ```yaml
   environment:
     - DATABASE_URL=postgresql://user:password@postgres:5432/finshield
   ```

3. **Add SSL/TLS**:
   - Use a reverse proxy (nginx, traefik)
   - Configure SSL certificates
   - Update CORS origins

### Troubleshooting

**Port conflicts:**
```bash
# Check if ports are in use
netstat -ano | findstr :3000
netstat -ano | findstr :8091

# Change ports in docker-compose.yml
ports:
  - "3001:3000"  # Frontend
  - "8092:8091"  # Backend
```

**Build issues:**
```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker compose build --no-cache
```

**Database issues:**
```bash
# Reset database
docker compose down -v
docker compose up --build
```

### Health Checks

```bash
# Check backend health (per-dependency status)
curl http://localhost:8091/api/health
# Liveness / readiness probes (slice S0.4)
curl http://localhost:8091/api/health/live
curl http://localhost:8091/api/health/ready   # 503 when a dependency is down

# Check frontend
curl http://localhost:3000
```

### Logs

```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs backend
docker compose logs frontend

# Follow logs in real-time
docker compose logs -f
```

### Backup & Restore

The stack runs on Postgres. The `backup` service writes a daily `pg_dump` archive to `./backups`. For an archive on demand:

```bash
docker compose exec backup sh /scripts/backup.sh
```

To restore, follow the tested runbook in [DEPLOYMENT.md, Phase 9](./DEPLOYMENT.md#phase-9-backup-and-restore--implemented-s45) (`scripts/restore.sh`, then the audit-chain check).

> **Superseded (SQLite only, R7).** These commands apply only to a pre-Postgres SQLite setup. To move such a file into Postgres, use `python -m scripts.sqlite_to_postgres <file>`.

**Backup database:**
```bash
docker compose exec backend cp /app/data/finshield.db /app/data/finshield.db.backup
docker cp finshield-backend:/app/data/finshield.db.backup ./backup/
```

**Restore database:**
```bash
docker cp ./backup/finshield.db finshield-backend:/app/data/finshield.db
docker compose restart backend
```

## Architecture

```
┌─────────────────┐
│   Frontend      │
│   (Next.js)     │
│   Port 3000     │
└────────┬────────┘
         │
         │ HTTP
         │
────────▼────────┐
│   Backend       │
│   (FastAPI)     │
│   Port 8091     │
└────────┬────────┘
         │
         │ SQLite (primary)        pgvector (RAG)
         │                              │
┌────────▼────────┐          ┌────────▼────────┐
│   SQLite file   │          │   PostgreSQL 16 │
│ (backend-data)  │          │ (postgres-data) │
└─────────────────┘          └─────────────────┘
```

## Security Notes

- Change `JWT_SECRET_KEY` before production deployment
- Use environment variables for sensitive data
- Enable HTTPS in production
- Configure CORS origins appropriately
- Regular security updates for dependencies

## Support

For issues or questions:
- Check logs: `docker compose logs -f`
- Review API docs: http://localhost:8091/api/docs
- See main README.md for detailed documentation
