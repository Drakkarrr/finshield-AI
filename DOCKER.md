# FinShield AI - Docker Deployment

## Quick Start

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2+

### Build and Run

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode (background)
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8091
- **API Docs**: http://localhost:8091/docs

### Environment Variables

Edit `docker-compose.yml` to customize:

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
   Update `JWT_SECRET_KEY` in `docker-compose.yml`

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
docker-compose build --no-cache
```

**Database issues:**
```bash
# Reset database
docker-compose down -v
docker-compose up --build
```

### Health Checks

```bash
# Check backend health
curl http://localhost:8091/api/health

# Check frontend
curl http://localhost:3000
```

### Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend

# Follow logs in real-time
docker-compose logs -f
```

### Backup & Restore

**Backup database:**
```bash
docker-compose exec backend cp /app/data/finshield.db /app/data/finshield.db.backup
docker cp finshield-backend:/app/data/finshield.db.backup ./backup/
```

**Restore database:**
```bash
docker cp ./backup/finshield.db finshield-backend:/app/data/finshield.db
docker-compose restart backend
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
         │ SQLite
         │
┌────────▼────────┐
│   Database      │
│   (Volume)      │
└─────────────────┘
```

## Security Notes

- Change `JWT_SECRET_KEY` before production deployment
- Use environment variables for sensitive data
- Enable HTTPS in production
- Configure CORS origins appropriately
- Regular security updates for dependencies

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review API docs: http://localhost:8091/docs
- See main README.md for detailed documentation
