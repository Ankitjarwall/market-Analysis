---
name: shannon
description: Security testing skill for the market platform. Use /shannon to run penetration tests against API endpoints.
---

## Shannon Security Skill

### Usage

```bash
# Full pentest of the backend API
/shannon http://localhost:8000 backend-api

# Target specific vulnerability categories
/shannon --scope=xss,injection http://localhost:8000 backend-api

# Named workspace (resumable)
/shannon --workspace=audit-q1 http://localhost:8000 backend-api

# Check status
/shannon status

# View report
/shannon results
```

### Market Platform Security Profile

**Authentication Endpoints** (test priority: HIGH)
- `POST /auth/login` — test: brute force protection (5 attempts → lockout), timing attacks, SQL injection in email/password
- `POST /auth/refresh` — test: token rotation, replay attacks
- `GET /auth/me` — test: missing token, expired token, tampered token

**WebSocket** (test priority: HIGH)
- `WS /ws/market?token=TOKEN` — test: missing token (should reject), invalid token, token from different user

**Admin Endpoints** (test priority: CRITICAL)
- `GET /api/admin/users` — test: viewer role should get 403
- `POST /api/admin/users` — test: privilege escalation, creating super_admin accounts
- `PUT /api/admin/users/{id}` — test: IDOR (modifying other users)

**Market Endpoints** (test priority: MEDIUM)
- `GET /api/market/*` — test: unauthenticated access
- `POST /api/signals/{id}/manual-entry` — test: manipulating signal data

### Known Security Controls
- Rate limiting: 5 failed logins → 30-minute lockout (per user)
- JWT: HS256 with `jti` (UUID) to prevent collision
- Session table: token stored in DB, logout invalidates immediately
- Role hierarchy: super_admin > admin > analyst > viewer

### Scope Exclusions
- Do NOT test against production (this is development only)
- Do NOT DoS the local DB (single-node, not hardened)
- WebSocket flood tests: limit to 10 concurrent connections for local testing
