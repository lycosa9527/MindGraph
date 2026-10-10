# MindGraph documentation

App version **5.180.154**. This index lists the living docs. Historical behavior stays in [CHANGELOG.md](../CHANGELOG.md).

## Start here

| Doc | What it covers |
|-----|----------------|
| [README](../README.md) | Product overview, install, routes |
| [API reference](API_REFERENCE.md) | External HTTP API (`X-API-Key`) |
| [Diagram type fields](DIAGRAM_TYPE_TABLE.md) | Spec fields per diagram type |
| [`.mg` file format](MG_FILE_FORMAT.md) | AES-GCM interchange (`frontend/src/utils/mgInterchange.ts`) |
| [AGENTS.md](../AGENTS.md) | Agent and CI conventions |

## Setup

| Doc | What it covers |
|-----|----------------|
| [Node / nvm](NODE_NVM_SETUP.md) | Frontend Node |
| [Vue](VUE_SETUP.md) | Frontend dev server and proxy timeouts |
| [PostgreSQL](POSTGRES_SETUP.md) | Database |
| [Redis](REDIS_SETUP.md) | Cache, sessions, collab |
| [Qdrant](QDRANT_SETUP.md) | Knowledge Space |
| [Celery](CELERY_SETUP.md) | Background workers |
| [Fail2ban + AbuseIPDB](FAIL2BAN_SETUP.md) | Host ban reporting |
| [ip2region patch](IP2REGION_PATCH_GUIDE.md) | Geo lookup patch |
| [Alembic](../alembic/README.md) | Schema migrations and RLS roles |

Database notes: [RLS rollout](db-rls-rollout.md), [RLS admin scope](db-rls-admin-scope.md), [RLS pre-coding checklist](db-rls-pre-coding-checklist.md), [tuning](db-tuning.md).

## Architecture

Canvas workshop fan-out (Redis pub/sub, live spec, writer tasks): [ARCHITECTURE.md](ARCHITECTURE.md). Day-to-day steps: [online collab runbook](operations/online-collab-runbook.md).

| Doc | What it covers |
|-----|----------------|
| [Production security deploy](architecture/production_security_deploy.md) | Env, proxy, paired rollout |
| [OAuth QR login](architecture/oauth_qr_login.md) | WeChat and DingTalk |
| [DingTalk account binding](architecture/dingtalk_account_binding.md) | MindBot pair codes |
| [MindBot tool ingress](architecture/mindbot_tool_ingress.md) | Pre-Dify tools |
| [Identity unification](architecture/identity_unification.md) | MindGraph, Dify, DingTalk |
| [MindMate collab](architecture/mindmate_collab.md) | Shared AI chatroom |
| [MindMate Dify persona inputs](architecture/mindmate_dify_persona_inputs.md) | Persona fields sent to Dify |
| [Thinking coins](architecture/thinking_coins.md) | Trial wallet |
| [Learning space](architecture/learning_space.md) | Classroom homework |
| [Training follow](architecture/training_follow.md) | `FEATURE_TRAINING` |
| [Tencent VOD](architecture/tencent_vod.md) | Admin video library |
| [Slide remote](architecture/slide_remote.md) | Watch clicker |
| [Word add-in embed auth](architecture/word_addin_embed_auth.md) | Login-free embed |
| [Diagram edit tool](architecture/diagram_edit_tool.md) | Verified canvas edits |
| [Mind map node identity](architecture/mindmap_node_identity.md) | UUID node ids |
| [Thinking map node identity](architecture/thinking_map_node_identity.md) | Same contract for Thinking Maps |
| [Mind map v2 separation](architecture/mindmap_v2_separation.md) | Classic vs new canvas modules |
| [Diagram chrome legacy spec](architecture/diagram_chrome_legacy_spec.md) | Previous Material look |
| [Kitty agent gaps](architecture/kitty_agent_gaps.md) | Typed loop (shipped) |

## Operations

| Doc | What it covers |
|-----|----------------|
| [MCP HTTP](operations/mcp_http.md) | `/api/mcp` |
| [Online collab runbook](operations/online-collab-runbook.md) | Day-to-day collab ops |
| [Uvicorn resource_tracker](operations/UVICORN_RESOURCE_TRACKER.md) | SIGHUP / worker reload warning |

## Package READMEs

| Package | Doc |
|---------|-----|
| Kitty | [services/kitty/README.md](../services/kitty/README.md) |
| Agent hub | [services/agent_hub/README.md](../services/agent_hub/README.md) |
| Showcase | [services/showcase/README.md](../services/showcase/README.md) |
| MindBot Dify audit | [services/mindbot/docs/DIFY_API_AUDIT.md](../services/mindbot/docs/DIFY_API_AUDIT.md) |
| File reader | [clients/file-reader/README.md](../clients/file-reader/README.md) |
| Chrome extension | [chrome-extension/README.md](../chrome-extension/README.md) |
| Word add-in | [word-addin/README.md](../word-addin/README.md) |
| ESP32 | [esp32/README.md](../esp32/README.md) |
| OpenClaw skill | [openclaw/skills/mindgraph/README.md](../openclaw/skills/mindgraph/README.md) |
| Tests | [tests/README.md](../tests/README.md) |
