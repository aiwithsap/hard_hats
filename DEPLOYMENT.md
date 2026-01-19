# Deployment Guide - Hard Hats Detection

## Architecture

Railway services:
- **web**: FastAPI API/dashboard (clones from GitHub at build time)
- **worker**: YOLO inference service (clones from GitHub at build time)
- **Postgres**: Database
- **Redis**: Frame/event pub-sub

## Standard Deployment Workflow

After GitHub integration is configured, deploy by pushing to GitHub:

```bash
# 1. Make code changes locally
# 2. Commit and push
git add <files>
git commit -m "Your message"
git push origin main

# 3. Railway auto-detects push and rebuilds both services
```

## Force Rebuild (Cache Busting)

If Railway caches builds and doesn't pick up changes:

1. Update CACHEBUST timestamp in both Dockerfiles:
   - `docker/Dockerfile.web` line 40
   - `docker/Dockerfile.worker` line 35
2. Format: `YYYYMMDD_HHMM` (e.g., `20260118_1430`)
3. Commit and push

## Monitoring Deployments

### Check Deployment Status
```bash
# Using Railway MCP tools (in Claude Code):
mcp__railway__list-deployments --service web
mcp__railway__list-deployments --service worker

# Using Railway CLI:
railway logs --service web
railway logs --service worker
```

### View Build/Deploy Logs
```bash
# Build logs (for debugging build failures):
mcp__railway__get-logs --logType build --service web

# Runtime logs (for debugging app issues):
mcp__railway__get-logs --logType deploy --service web
```

## One-Time Setup (Dashboard Required)

GitHub integration must be configured via Railway dashboard:

### Step 1: Connect GitHub Repository
1. Go to https://railway.app and login
2. Open your project
3. Go to **Settings** → **Source**
4. Click **Connect Repository**
5. Authorize Railway GitHub App (if needed)
6. Select repository: `aiwithsap/hard_hats`
7. Select branch: `main`
8. Click **Connect**

### Step 2: Verify Service Build Config
Each service should be configured:
- **web** → Dockerfile Path: `docker/Dockerfile.web`
- **worker** → Dockerfile Path: `docker/Dockerfile.worker`

Check via: Service Settings → Build → Dockerfile Path

### Step 3: Confirm Auto-Deploy
- Service Settings → Deployments → "Auto-deploy" should be ON

## What to AVOID

- ❌ `railway up` - Uploads corrupted local files (WSL issue)
- ❌ Any local file upload mechanism
- ✅ Always push to git for deployments

## Troubleshooting

### Deployment Not Triggering
- Check GitHub webhook in repo Settings → Webhooks
- Verify Railway GitHub App has access to repo
- Try manual redeploy from Railway dashboard

### Build Using Stale Code
- Update CACHEBUST in Dockerfiles
- Verify push was to `main` branch
- Check Railway is connected to correct branch

### Service Fails to Start
```bash
# Check runtime logs:
mcp__railway__get-logs --logType deploy --service <service-name>
```

### Database Migration Issues
Web service runs: `alembic upgrade head || alembic stamp head`
- First tries upgrade, falls back to stamp if revision mismatch
