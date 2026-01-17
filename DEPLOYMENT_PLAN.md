# Railway Deployment Plan: Hard Hats Detection System

## Overview

Transform the current single-tenant, SQLite-based hard hats detection system into a production-ready, multi-tenant SaaS deployed on Railway with authentication, RTSP stream support, and horizontal scalability.

---

## Architecture Decision Summary

| Component | Current | Target |
|-----------|---------|--------|
| Database | SQLite (thread-local) | PostgreSQL (Railway managed) |
| Cache/Sessions | In-memory | Redis (Railway managed) |
| Auth | None | JWT + bcrypt + role-based |
| Tenancy | Single | Multi-tenant with org isolation |
| Video Sources | Local files only | RTSP streams + files |
| Deployment | Docker local | Railway containers |

### Service Topology

```
Railway Edge (HTTPS)
        │
   ┌────┴────┐
   │ Web API │ ← FastAPI (auth, API, SSE, MJPEG proxy)
   └────┬────┘
        │
   ┌────┴────┬─────────────┐
   │         │             │
┌──▼──┐ ┌────▼────┐ ┌──────▼──────┐
│Redis│ │PostgreSQL│ │Video Workers│
└─────┘ └─────────┘ │(YOLO+RTSP) │
                    └─────────────┘
```

**Architecture:** Separate web and worker containers from day 1 (10+ cameras/customer requires this)
- **Web Service:** API, auth, SSE, MJPEG proxy
- **Worker Service:** YOLO inference, RTSP connections, frame processing
- **Redis:** Frame pub/sub between services, session storage

---

## Database Schema

### Core Tables

```sql
organizations (id, name, slug, plan, max_cameras, max_users, settings, created_at)
users (id, organization_id, email, password_hash, full_name, role, is_active, last_login)
cameras (id, organization_id, name, zone, source_type, rtsp_url, credentials_encrypted,
         placeholder_video, use_placeholder, inference_width, inference_height, target_fps,
         position_x, position_y, detection_mode, zone_polygon, confidence_threshold,
         is_active, status, last_seen, error_message)
events (id, organization_id, camera_id, event_type, violation_type, severity,
        confidence, bbox_*, thumbnail_path, acknowledged, acknowledged_by)
daily_stats (id, organization_id, camera_id, date, total_violations,
             no_hardhat_count, no_vest_count, zone_breach_count, frames_processed)
audit_logs (id, organization_id, user_id, action, resource_type, resource_id, details, ip_address)
password_reset_tokens (id, user_id, token_hash, expires_at, used_at)
```

### Multi-Tenant Isolation
- All tables have `organization_id` foreign key
- All queries filter by `organization_id` from JWT context
- Row-level security at repository layer

---

## Authentication System

### Why HTTP-Only Cookies (Not localStorage + Headers)

**Critical Constraint:** The dashboard uses `<img src="/api/stream/{id}">` for MJPEG and `new EventSource('/api/sse/events')` for SSE. Neither can send Authorization headers - browsers don't support it.

**Solution:** HTTP-only cookie-based authentication. Browser automatically includes cookies with every request.

### Cookie Configuration
```python
response.set_cookie(
    key="session",
    value=jwt_token,
    httponly=True,      # JavaScript cannot read (XSS protection)
    secure=True,        # HTTPS only (Railway provides this)
    samesite="strict",  # CSRF protection
    max_age=3600,       # 1 hour expiry
    path="/",           # Available for all routes
)
```

### JWT Token Structure (Stored in Cookie)
```json
{
  "sub": "user_uuid",
  "org": "organization_uuid",
  "role": "admin|manager|operator",
  "exp": 1234567890
}
```

### Auth Dependency (Extracts from Cookie)
```python
async def get_current_user(request: Request) -> User:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return await get_user_by_id(payload["sub"])
```

### Role Permissions (Simplified - Admin-Only Camera Setup)

| Resource | Admin | Manager | Operator |
|----------|-------|---------|----------|
| Users | CRUD | - | - |
| Organization | CRUD | Read | - |
| Cameras | CRUD | Read | Read |
| Events | CRUD | CRUD | Read+Acknowledge |
| Streams | Full | Full | Full |
| Stats | Full | Full | Full |

**Note:** Only admins can configure RTSP cameras. Managers and operators can only view streams and manage events.

### Auth Endpoints (No Email Verification)
```
POST /api/v1/auth/register        # Create org + admin → Sets session cookie
POST /api/v1/auth/login           # Verify credentials → Sets session cookie
POST /api/v1/auth/logout          # Clears session cookie
POST /api/v1/auth/refresh         # Refresh before expiry → Sets new cookie
POST /api/v1/auth/change-password # Change own password (authenticated)
GET  /api/v1/auth/me              # Get current user from cookie
```

### Frontend Integration (Embedded Dashboard)
```javascript
// Login - cookie is set automatically by response
await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',  // REQUIRED for cookies
    body: JSON.stringify({ email, password })
});

// All subsequent requests include cookie automatically
// MJPEG streams work:
<img src="/api/stream/${camera.id}">  // Cookie sent automatically

// SSE works:
const sse = new EventSource('/api/sse/events', { withCredentials: true });

// API calls work:
await fetch('/api/v1/cameras', { credentials: 'include' });
```

**Deferred:** Email verification and password reset via email will be added later when email service is configured.

---

## RTSP Stream Support

### Camera Source Types
- `rtsp` - RTSP URL with credentials (production)
- `file` - Placeholder video file (demo/fallback when RTSP unavailable)

### Placeholder Video Fallback
When RTSP stream is unavailable or not yet configured:
- Admin can upload or select a demo video as placeholder
- System shows "DEMO MODE" watermark on stream
- Allows demonstrating detection capabilities before real camera setup
- Automatic fallback: if RTSP fails after N retries, switch to placeholder

### Camera Configuration Options

```python
# Per-camera settings (admin configurable)
class CameraConfig:
    # Source
    source_type: str          # "rtsp" or "file"
    rtsp_url: str             # RTSP stream URL
    rtsp_credentials: str     # Encrypted username:password
    placeholder_video: str    # Fallback video path/URL
    use_placeholder: bool     # Force placeholder mode (demo)

    # Processing Resolution (downscale for YOLO)
    inference_width: int      # 640, 720, 1080, 1280 (default: 640)
    inference_height: int     # 640, 720, 1080, 1280 (default: 640)
    # Note: Camera sends native resolution, we downscale before inference

    # Frame Rate Control
    target_fps: float         # 0.25 to 2.0 FPS (default: 0.5)
    # Lower = less CPU, fewer detections
    # Higher = more CPU, more responsive
```

### Resolution Presets
| Preset | Resolution | Use Case |
|--------|------------|----------|
| Low | 640x640 | Fast processing, low CPU (~174ms/frame) |
| Medium | 720x720 | Balanced accuracy/speed |
| High | 1080x1080 | Better accuracy, higher CPU (~400ms/frame) |
| Custom | User-defined | Advanced users |

### FPS Guidelines
| FPS | Frames/min | CPU Load | Use Case |
|-----|------------|----------|----------|
| 0.25 | 15 | Very Low | Large camera count, basic monitoring |
| 0.5 | 30 | Low | Default, good balance |
| 1.0 | 60 | Medium | Active areas, faster response |
| 2.0 | 120 | High | Critical zones, near real-time |

### RTSP Connection Management
```python
class RTSPHandler:
    max_retries = 5
    base_delay = 1.0  # exponential backoff
    max_delay = 60.0
    health_check_interval = 30.0
    fallback_to_placeholder = True  # Auto-switch on failure
```

### Credential Security
- Fernet symmetric encryption for RTSP passwords
- Encryption key from `ENCRYPTION_KEY` env var
- Never log credentials
- Validate URLs before connecting

### Camera API
```
POST /api/v1/cameras              # Create camera with config
POST /api/v1/cameras/{id}/test    # Test RTSP connection
PUT  /api/v1/cameras/{id}         # Update config/credentials
POST /api/v1/cameras/{id}/placeholder  # Upload placeholder video
GET  /api/v1/cameras/presets      # Get resolution/FPS presets
```

---

## New File Structure (Two-Container Architecture)

```
app/
├── web/                          # WEB SERVICE (container 1)
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Railway env vars
│   ├── auth/
│   │   ├── dependencies.py       # get_current_user, require_role
│   │   ├── jwt.py                # Token creation/validation
│   │   ├── password.py           # bcrypt hashing
│   │   └── schemas.py            # Auth models
│   ├── api/v1/
│   │   ├── auth.py               # Auth endpoints
│   │   ├── users.py              # User management (admin only)
│   │   ├── organizations.py      # Org settings (admin only)
│   │   ├── cameras.py            # Camera CRUD (admin only for write)
│   │   ├── events.py             # Event queries
│   │   ├── stream.py             # MJPEG proxy (reads from Redis)
│   │   ├── stats.py              # Statistics
│   │   └── sse.py                # SSE broadcast (subscribes to Redis)
│   └── services/
│       ├── auth_service.py
│       ├── camera_service.py
│       └── stream_proxy.py       # Redis frame subscriber
│
├── worker/                       # WORKER SERVICE (container 2)
│   ├── main.py                   # Worker entry point
│   ├── config.py                 # Worker config
│   ├── camera_manager.py         # Multi-camera orchestration
│   ├── rtsp_handler.py           # RTSP connection management
│   ├── frame_publisher.py        # Publishes frames to Redis
│   ├── event_processor.py        # Detects violations, stores events
│   └── vision.py                 # YOLO inference (unchanged)
│
├── shared/                       # SHARED CODE (both containers)
│   ├── db/
│   │   ├── database.py           # Async SQLAlchemy + PostgreSQL
│   │   ├── models.py             # ORM models
│   │   └── repositories/
│   │       ├── base.py           # Tenant-filtered base
│   │       ├── users.py
│   │       ├── cameras.py
│   │       ├── events.py
│   │       └── organizations.py
│   ├── redis/
│   │   ├── client.py             # Redis connection factory
│   │   └── pubsub.py             # Frame/event pub/sub helpers
│   ├── encryption.py             # Fernet for RTSP credentials
│   └── models/                   # Pydantic schemas
│       ├── camera.py
│       ├── event.py
│       └── user.py
│
├── alembic/                      # Database migrations
│   ├── env.py
│   └── versions/
│
├── docker/
│   ├── Dockerfile.web            # Web service image
│   └── Dockerfile.worker         # Worker service image
│
├── railway.json                  # Railway multi-service config
├── requirements-web.txt          # Web service dependencies
└── requirements-worker.txt       # Worker service dependencies
```

### railway.json (Multi-Service Config)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE" },
  "deploy": { "restartPolicyType": "ON_FAILURE" },
  "services": {
    "web": {
      "dockerfile": "docker/Dockerfile.web",
      "healthcheck": { "path": "/health", "timeout": 30 }
    },
    "worker": {
      "dockerfile": "docker/Dockerfile.worker"
    }
  }
}
```

---

## Railway Configuration (Two Services)

### Railway Project Structure
```
Railway Project: hard-hats-prod
├── Service: web (Dockerfile.web)
│   └── Domain: hard-hats.up.railway.app
├── Service: worker (Dockerfile.worker)
│   └── No public domain (internal only)
├── Plugin: PostgreSQL
│   └── DATABASE_URL auto-injected
└── Plugin: Redis
    └── REDIS_URL auto-injected
```

### Environment Variables (Shared)
```bash
# Auto-provided by Railway
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...

# Application secrets (set manually)
SECRET_KEY=<32-byte-hex>
ENCRYPTION_KEY=<fernet-key>

# Configuration
JWT_EXPIRE_MINUTES=60
LOG_LEVEL=INFO
MAX_CAMERAS_PER_ORG=50
```

### Dockerfile.web
```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY app/shared/ app/shared/
COPY app/web/ app/web/
COPY alembic/ alembic/
COPY alembic.ini .

ENV PYTHONUNBUFFERED=1

# Run migrations then start web server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.web.main:app --host 0.0.0.0 --port ${PORT:-8123}"]
```

### Dockerfile.worker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

COPY app/shared/ app/shared/
COPY app/worker/ app/worker/

# Pre-download YOLO weights at build time
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

ENV PYTHONUNBUFFERED=1

# Worker process (no port needed)
CMD ["python", "-m", "app.worker.main"]
```

### Dashboard HTML Update
- Keep embedded in `app/web/main.py` (no separate frontend)
- Add login form before dashboard access
- JWT stored in HTTP-only cookie (set by server, not accessible to JS)
- All fetch calls use `credentials: 'include'` to send cookie
- MJPEG `<img>` tags work automatically (browser sends cookie)
- SSE `EventSource` uses `{ withCredentials: true }`

---

## Implementation Phases

### Phase 1: Project Restructure + Database (Week 1)
1. Reorganize into `app/web/`, `app/worker/`, `app/shared/` structure
2. Create SQLAlchemy ORM models with organization_id FKs
3. Set up Alembic migrations
4. Create both Dockerfiles
5. Push to GitHub → Railway auto-deploys
6. Use Railway MCP to add PostgreSQL + Redis plugins

**Critical files:**
- `app/shared/db/database.py` - PostgreSQL async engine
- `app/shared/db/models.py` - SQLAlchemy ORM models
- `docker/Dockerfile.web`, `docker/Dockerfile.worker`
- `alembic/versions/*.py` - Migration scripts

**Deployment:** GitHub push → Railway auto-deploy (no local Docker/pip)

### Phase 2: Authentication + Dashboard Login (Week 2)
1. Implement JWT token handling (`python-jose`)
2. Implement password hashing (`passlib[bcrypt]`)
3. Create auth endpoints (register, login, refresh, change-password)
4. Add login page to embedded dashboard HTML
5. Add auth dependencies to all API routes

**Critical files:**
- `app/web/auth/jwt.py` - Token creation/validation
- `app/web/auth/dependencies.py` - get_current_user, require_role
- `app/web/api/v1/auth.py` - Auth endpoints
- `app/web/main.py` - Login page HTML

### Phase 3: Multi-Tenancy + Redis Pub/Sub (Week 2-3)
1. Add organization context to all API routes
2. Implement Redis frame pub/sub between worker and web
3. Update camera manager to load from database (filtered by org)
4. Update event processor with organization_id
5. Update SSE to subscribe to Redis events

**Critical files:**
- `app/shared/redis/pubsub.py` - Frame/event pub/sub
- `app/worker/camera_manager.py` - DB-backed, tenant-filtered
- `app/worker/frame_publisher.py` - Publishes to Redis
- `app/web/services/stream_proxy.py` - Subscribes from Redis

### Phase 4: RTSP Support (Week 3)
1. Implement RTSPHandler with retry logic and health checks
2. Add Fernet encryption for credentials
3. Update camera API for RTSP URLs (admin-only create/update)
4. Add connection testing endpoint

**Critical files:**
- `app/worker/rtsp_handler.py` - Connection management
- `app/shared/encryption.py` - Credential encryption
- `app/web/api/v1/cameras.py` - RTSP support (admin-only write)

### Phase 5: Railway Deploy + Testing (Week 4)
1. Push code to GitHub
2. Use Railway MCP tools to create project and link to GitHub repo
3. Use Railway MCP to add PostgreSQL + Redis databases
4. Use Railway MCP to set environment variables
5. Railway auto-deploys from GitHub on each push
6. Verify via Railway dashboard and health endpoints

**Railway deployment via MCP tools (no local CLI):**
```
# Using Claude Code's Railway MCP skills:
1. mcp__railway__create-project-and-link → Create project
2. mcp__railway__deploy-template (postgres) → Add PostgreSQL
3. mcp__railway__deploy-template (redis) → Add Redis
4. mcp__railway__set-variables → Set SECRET_KEY, ENCRYPTION_KEY
5. mcp__railway__deploy → Deploy from GitHub
6. mcp__railway__generate-domain → Get public URL
7. mcp__railway__get-logs → Verify deployment
```

**GitHub → Railway flow:**
- Connect Railway project to GitHub repo
- Railway auto-deploys on push to main branch
- Separate services for web and worker via railway.json config

---

## Scaling Strategy (10+ Cameras/Customer)

### Resource Requirements per Camera
| Resource | Per Camera |
|----------|------------|
| CPU | ~0.5 vCPU (YOLO inference) |
| Memory | ~200MB (buffers + model share) |
| Bandwidth | 1-5 Mbps (RTSP stream) |

### Two-Container Architecture (From Day 1)

**Web Service (1 instance):**
- FastAPI API server
- Authentication/authorization
- SSE event broadcasting
- MJPEG stream proxy (fetches from Redis)
- Resource: 1 vCPU, 1GB RAM

**Worker Service (scalable):**
- YOLO model inference
- RTSP connection management
- Frame processing and publishing
- Event generation
- Resource: 4+ vCPU, 4GB RAM per worker

**Inter-Service Communication via Redis:**
```
Worker → Redis (PUBLISH frames/{camera_id}) → Web → MJPEG to client
Worker → Redis (PUBLISH events/{org_id}) → Web → SSE to client
Worker → PostgreSQL (event storage)
```

### Railway Tier Recommendations
| Customers | Cameras | Workers | Est. Cost |
|-----------|---------|---------|-----------|
| 1-2 | 10-20 | 1 worker | ~$40/mo |
| 3-5 | 30-50 | 2 workers | ~$70/mo |
| 5-10 | 50-100 | 3-4 workers | ~$120/mo |

### Worker Scaling Rules
- Each worker handles ~15-20 concurrent RTSP streams
- Scale workers based on total active cameras across all orgs
- Workers are stateless - can be added/removed dynamically

---

## Security Checklist

- [ ] HTTP-only cookies for JWT (XSS protection)
- [ ] Secure cookie flag (HTTPS only - Railway default)
- [ ] SameSite=Strict cookie (CSRF protection)
- [ ] JWT tokens with short expiry (60 min)
- [ ] bcrypt with work factor 12
- [ ] Rate limiting on auth endpoints
- [ ] Fernet encryption for RTSP credentials
- [ ] All queries filtered by organization_id
- [ ] Audit logging for sensitive operations
- [ ] Environment variables for all secrets
- [ ] HTTPS enforced (Railway default)

---

## Verification Plan

1. **Auth Flow Testing:**
   - Register new organization + admin
   - Login and verify JWT claims
   - Test role-based access (admin/manager/operator)
   - Password reset flow

2. **Multi-Tenant Isolation:**
   - Create two organizations
   - Verify cameras/events don't leak across orgs
   - Test admin can only see own org data

3. **RTSP Streams:**
   - Add camera with RTSP URL
   - Verify credentials encrypted in DB
   - Test connection retry on failure
   - Verify stream displays in dashboard

4. **Railway Deployment:**
   - Verify DATABASE_URL connection
   - Verify migrations run on deploy
   - Health check endpoint responds
   - SSE events work across instances
