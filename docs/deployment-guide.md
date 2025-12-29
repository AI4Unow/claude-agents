# Deployment Guide

## Prerequisites

- Python 3.11+
- Modal CLI installed (`pip install modal`)
- Modal account (sign up at modal.com)
- API keys for external services

## Quick Start

```bash
# 1. Install Modal CLI
pip install modal

# 2. Authenticate with Modal
modal setup

# 3. Clone repository
git clone <repo-url>
cd Agents

# 4. Set up secrets (see below)

# 5. Deploy
modal deploy agents/main.py

# 6. View logs
modal app logs claude-agents
```

## Secrets Configuration

Create each secret in Modal with the required environment variables:

### Anthropic Credentials
```bash
modal secret create anthropic-credentials \
  ANTHROPIC_API_KEY=sk-ant-...
```

### Telegram Credentials
```bash
modal secret create telegram-credentials \
  TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Firebase Credentials
```bash
# Option 1: Individual values
modal secret create firebase-credentials \
  FIREBASE_PROJECT_ID=your-project-id \
  FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'

# Option 2: From file
modal secret create firebase-credentials \
  FIREBASE_PROJECT_ID=your-project-id \
  FIREBASE_CREDENTIALS_JSON="$(cat firebase-credentials.json)"
```

### Qdrant Credentials
```bash
modal secret create qdrant-credentials \
  QDRANT_URL=https://xxx.qdrant.io:6333 \
  QDRANT_API_KEY=your-api-key
```

### Exa Credentials (Web Search)
```bash
modal secret create exa-credentials \
  EXA_API_KEY=your-exa-key
```

### Tavily Credentials (Web Search Fallback)
```bash
modal secret create tavily-credentials \
  TAVILY_API_KEY=your-tavily-key
```

### GitHub Credentials
```bash
modal secret create github-credentials \
  GITHUB_TOKEN=ghp_...
```

### Admin Credentials (Self-Improvement + User Tiers)
```bash
modal secret create admin-credentials \
  ADMIN_TELEGRAM_ID=your-telegram-id \
  ADMIN_API_TOKEN=your-secure-token
```

### GCP Credentials (Gemini API via Vertex AI)
```bash
modal secret create gcp-credentials \
  GCP_PROJECT_ID=your-gcp-project \
  GCP_LOCATION=us-central1 \
  GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'

# Note: Enable Vertex AI API in GCP Console before using
```

## Deployment Commands

### Deploy to Production
```bash
# Deploy full app
modal deploy agents/main.py

# Output: Deploy URL
# https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run
```

### Local Development
```bash
# Run locally with hot reload
modal serve agents/main.py
```

### View Logs
```bash
# View all logs
modal app logs claude-agents

# View with filter
modal app logs claude-agents --filter "telegram"
```

### Stop App
```bash
modal app stop claude-agents
```

## Webhook Setup

### Telegram Bot Webhook

1. Create a bot via @BotFather on Telegram
2. Get your bot token
3. Set webhook to Modal URL:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-modal-url>/webhook/telegram"}'
```

### GitHub Webhook

1. Go to repository Settings > Webhooks
2. Add webhook:
   - Payload URL: `https://<your-modal-url>/webhook/github`
   - Content type: `application/json`
   - Events: Push, Pull requests, Issues

## Testing Services

Run test functions to verify connectivity:

```bash
# Test LLM connection
modal run agents/main.py::test_llm

# Test Firebase
modal run agents/main.py::test_firebase

# Test Qdrant
modal run agents/main.py::test_qdrant

# Test Embeddings
modal run agents/main.py::test_embeddings

# Test GitHub
modal run agents/main.py::test_github

# Test Gemini API
modal run agents/main.py::test_gemini

# Test Gemini grounding
modal run agents/main.py::test_grounding

# Test deep research (takes ~30s)
modal run agents/main.py::test_deep_research
```

## Initialize Skills

First-time setup to sync skills to Modal Volume:

```bash
# Sync from local
modal run agents/main.py::sync_skills_from_local

# Or sync from GitHub
modal run agents/main.py::sync_skills_from_github
```

## API Endpoints

After deployment, these endpoints are available:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with circuit status |
| `/webhook/telegram` | POST | Telegram webhook |
| `/webhook/github` | POST | GitHub webhook |
| `/api/skill` | POST | Execute skill |
| `/api/skills` | GET | List skills |
| `/api/task/{id}` | GET | Get local task status |
| `/api/reports` | GET | List user reports |
| `/api/reports/{id}` | GET | Get report download URL |
| `/api/reports/{id}/content` | GET | Get report content |
| `/api/content` | POST | Content generation |
| `/api/traces` | GET | Execution traces (developer+) |
| `/api/traces/{id}` | GET | Single trace details |
| `/api/circuits` | GET | Circuit breaker status |
| `/api/circuits/reset` | POST | Reset all circuits |

### API Examples

```bash
# Execute skill (simple mode)
curl -X POST https://<modal-url>/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "planning",
    "task": "Create authentication implementation plan",
    "mode": "simple"
  }'

# List user reports
curl "https://<modal-url>/api/reports?user_id=123456"

# Get report download URL
curl "https://<modal-url>/api/reports/research-abc123?user_id=123456"

# List available skills
curl https://<modal-url>/api/skills

# Check circuit breaker status
curl https://<modal-url>/api/circuits

# View execution traces
curl https://<modal-url>/api/traces?limit=10
```

## Local Skill Execution

For skills that require local execution (browser automation, consumer IP):

```bash
# One-time execution
python3 agents/scripts/local-executor.py

# Continuous polling (30s interval)
python3 agents/scripts/local-executor.py --poll

# Custom interval
python3 agents/scripts/local-executor.py --poll --interval 60

# Execute specific task
python3 agents/scripts/local-executor.py --task <task_id>
```

## Self-Improvement

Pull and apply approved improvements:

```bash
# List pending improvements
python3 agents/scripts/pull-improvements.py --list

# Preview changes
python3 agents/scripts/pull-improvements.py --dry-run

# Apply all approved improvements
python3 agents/scripts/pull-improvements.py

# After applying, deploy changes
git add agents/skills/
git commit -m "chore: apply skill improvements"
git push
modal deploy agents/main.py
```

## Monitoring

### Modal Dashboard
- Visit modal.com dashboard for:
  - Function execution metrics
  - Container logs
  - Cost tracking

### Health Check
```bash
# Check system health and circuit status
curl https://<modal-url>/health

# Response includes:
# - status: healthy/degraded
# - circuits: state of all 7 circuit breakers
# - timestamp
```

### Firebase Console
- View Firestore collections
- Check task queue status
- Monitor agent state
- View reports in Storage

### Qdrant Dashboard
- View collections
- Check vector counts
- Query testing

## Troubleshooting

### Common Issues

**1. Secrets not found**
```
Error: Secret 'anthropic-credentials' not found
```
Solution: Create the secret with `modal secret create`

**2. Timeout errors**
```
Error: Function timed out after 60s
```
Solution: Increase timeout in function decorator or optimize code

**3. Container cold start**
For Telegram chat agent, `min_containers=1` keeps it warm. For other functions, expect 1-2s cold start.

**4. Webhook not responding**
- Check Modal logs for errors
- Verify webhook URL is correct
- Test with `/health` endpoint first

**5. Gemini API errors**
```
Error: Vertex AI API not enabled
```
Solution: Enable Vertex AI API in GCP Console and ensure billing is enabled

**6. Firebase Storage 404**
```
Error: 404 bucket not found
```
Solution: Enable Firebase Storage in Firebase Console

### Debug Mode

Run with verbose logging:
```bash
# In code
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

## Cost Optimization

1. **Telegram Agent**: Uses `min_containers=1` (~$15-20/mo)
   - Consider removing if not needed 24/7

2. **GitHub/Data Agents**: Cron-based, pay-per-use
   - Adjust cron frequency as needed

3. **LLM Costs**: ~$10-20/mo depending on usage
   - Use shorter prompts when possible
   - Cache common responses

4. **Gemini API**: Vertex AI pricing
   - Use API key mode for free tier (limited)
   - Use Vertex AI for production

## Updating Deployment

```bash
# Update code
git pull

# Redeploy
modal deploy agents/main.py

# Sync skills (if skills changed)
modal run agents/main.py::sync_skills_from_local
```

## Related Documents

- [README.md](../README.md)
- [Project Overview](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Code Standards](./code-standards.md)
