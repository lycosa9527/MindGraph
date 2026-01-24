---
name: PostgreSQL Migration Assessment
overview: Assess the difficulty and create a migration plan for switching from SQLite+Redis to PostgreSQL+Redis architecture
todos:
  - id: assess-current-state
    content: Review current SQLite usage and identify all SQLite-specific code paths
    status: pending
  - id: add-postgresql-driver
    content: Add PostgreSQL driver (psycopg2-binary or asyncpg) to requirements.txt
    status: pending
  - id: update-env-config
    content: Update env.example with PostgreSQL connection string and settings
    status: pending
  - id: verify-db-config
    content: Verify database.py PostgreSQL configuration and connection pooling
    status: pending
  - id: verify-schema-creation
    content: Verify init_db() creates all tables correctly in PostgreSQL
    status: pending
  - id: test-postgresql-schema
    content: Test schema creation and migrations with PostgreSQL
    status: pending
  - id: update-documentation
    content: Update README and deployment docs with PostgreSQL setup instructions for WSL (dev) and Ubuntu (server)
    status: pending
  - id: wsl-setup-guide
    content: Create WSL PostgreSQL installation and configuration guide
    status: pending
  - id: ubuntu-server-setup-guide
    content: Create Ubuntu server PostgreSQL deployment guide with systemd configuration
    status: pending
  - id: performance-testing
    content: Compare performance between SQLite and PostgreSQL under load
    status: pending
isProject: false
---

# PostgreSQL+Redis Migration Assessment

## Current Architecture

The application currently uses:

- **SQLite** for persistent data (users, organizations, diagrams, knowledge space, token usage, etc.)
- **Redis** for ephemeral data (caching, rate limiting, sessions, captcha, diagram cache)
- **Qdrant** for vector storage (RAG/knowledge space)

## Migration Difficulty: **EASY TO MODERATE** (2-3 days of focused work)

**Note:** Production server is running old code - can start fresh with empty database. No data migration needed!

### Why Moderate Difficulty?

**Easier aspects:**

1. SQLAlchemy models are already database-agnostic (mostly)
2. Database configuration already has PostgreSQL support (`config/database.py` lines 438-468)
3. Migration utilities already support PostgreSQL (`utils/db_migration.py` has `_get_postgresql_column_type`)
4. Redis usage remains unchanged (no migration needed)
5. Connection pooling logic already exists for PostgreSQL

**Challenging aspects:**

1. SQLite-specific code needs conditional handling or removal
2. WAL checkpointing logic is SQLite-only (already conditionally handled)
3. Some PRAGMA statements need removal/conditionals (already conditionally handled)
4. Testing with fresh PostgreSQL database

**Simplified because:**

- No data migration needed (production starts fresh)
- No rollback procedures for existing data
- Schema creation only (SQLAlchemy handles this)

## Required Changes

### 1. Database Configuration (`config/database.py`)

**Current SQLite-specific code to handle:**

- WAL mode enabling (lines 421-437)
- WAL checkpointing (lines 674-803)
- SQLite integrity checks (lines 855-896)
- SQLite recovery functions (lines 899-975)
- Database file path handling (lines 239-391)

**Changes needed:**

- Keep SQLite code but wrap in `if "sqlite" in DATABASE_URL` checks (already done for most)
- Ensure PostgreSQL connection pool settings are optimal
- Remove or conditionally disable WAL checkpoint scheduler for PostgreSQL

### 2. Migration Utilities (`utils/db_migration.py`)

**Status:** Already supports PostgreSQL

- Has `_get_postgresql_column_type()` function
- Handles multiple dialects in `run_migrations()`

**Action:** No changes needed, but verify PostgreSQL-specific migrations work correctly

### 3. SQLite-Specific Utilities (`utils/db_type_migration.py`)

**Current:** SQLite-only table recreation logic

**Action:**

- Keep for SQLite compatibility
- Add PostgreSQL support if needed (PostgreSQL supports `ALTER COLUMN` natively)

### 4. Fresh Database Setup

**Status:** No data migration needed - production starts fresh

**Approach:**

- Use existing `init_db()` function in `config/database.py`
- SQLAlchemy will create all tables automatically
- Seed initial data (organizations) via existing seed logic
- No data migration script required

### 5. Environment Configuration (`env.example`)

**Current:** `DATABASE_URL=sqlite:///./data/mindgraph.db`

**Change to:**

- WSL Dev: `DATABASE_URL=postgresql://mindgraph_user:password@localhost:5432/mindgraph`
- Ubuntu Server: `DATABASE_URL=postgresql://mindgraph_user:password@localhost:5432/mindgraph` (or remote host)

**Add PostgreSQL-specific settings:**

- Connection pool size (already supported)
- SSL mode (for production Ubuntu server)
- Connection timeout
- Connection string format: `postgresql://[user]:[password]@[host]:[port]/[database]`
- For WSL: use `localhost` or `127.0.0.1`
- For Ubuntu server: use server hostname/IP if remote

### 6. Dependencies (`requirements.txt`)

**Current:** No PostgreSQL driver

**Add:** `psycopg2-binary>=2.9.9` (recommended for WSL/Ubuntu compatibility)

**Note:**

- SQLAlchemy 2.0+ supports both sync and async PostgreSQL
- `psycopg2-binary` is easier to install (no compilation needed)
- Works well on both WSL and Ubuntu
- For async, can add `asyncpg>=0.29.0` later if needed

## Deployment Environment

**Development:** WSL (Windows Subsystem for Linux)

**Production:** Ubuntu server (running old code - fresh start, no data migration needed)

This affects PostgreSQL setup and configuration:

### WSL Development Environment

**Installation:**

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

**Service Management:**

- WSL uses traditional init scripts, not systemd
- Start: `sudo service postgresql start`
- Stop: `sudo service postgresql stop`
- Status: `sudo service postgresql status`
- Auto-start: Add to `~/.bashrc` or use WSL startup script

**Connection:**

- From WSL: `localhost` or `127.0.0.1`
- From Windows host: Use WSL IP (check with `ip addr show eth0`)
- Default port: `5432`

**Configuration:**

- Config file: `/etc/postgresql/[version]/main/postgresql.conf`
- Access control: `/etc/postgresql/[version]/main/pg_hba.conf`
- Data directory: `/var/lib/postgresql/[version]/main`

### Ubuntu Server Production Environment

**Installation:**

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
```

**Service Management:**

- Managed via systemd
- Start: `sudo systemctl start postgresql`
- Enable auto-start: `sudo systemctl enable postgresql`
- Status: `sudo systemctl status postgresql`

**Production Considerations:**

- Configure SSL/TLS certificates
- Set up firewall rules (UFW): `sudo ufw allow 5432/tcp`
- Configure `postgresql.conf` for production (shared_buffers, max_connections, etc.)
- Set up automated backups
- Configure log rotation
- Consider connection pooling (PgBouncer) for high concurrency

**Security:**

- Use strong passwords
- Restrict `pg_hba.conf` to trusted IPs
- Use SSL for remote connections
- Create dedicated application user (not postgres superuser)

## Migration Steps

### Phase 1: Preparation (1 day)

1. **WSL Development Setup:**

   - Install PostgreSQL: `sudo apt-get update && sudo apt-get install postgresql postgresql-contrib`
   - Start service: `sudo service postgresql start`
   - Create database: `sudo -u postgres createdb mindgraph`
   - Create user: `sudo -u postgres createuser -P mindgraph_user`

2. **Ubuntu Server Setup (Fresh Installation):**

   - Install PostgreSQL: `sudo apt-get install postgresql postgresql-contrib`
   - Enable service: `sudo systemctl enable postgresql`
   - Create fresh database: `sudo -u postgres createdb mindgraph`
   - Create application user: `sudo -u postgres createuser -P mindgraph_user`
   - Grant permissions: `sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mindgraph TO mindgraph_user;"`
   - Configure firewall if needed (port 5432)
   - Set up SSL certificates for production (optional, for remote connections)

3. **Application Configuration:**

   - Add PostgreSQL driver to `requirements.txt`
   - Update `env.example` with PostgreSQL connection strings for both environments
   - Test PostgreSQL connection locally (WSL)
   - Create PostgreSQL database and verify schema creation

### Phase 2: Code Updates (1-2 days)

1. Review and verify all SQLite conditionals in `config/database.py`
2. Ensure WAL checkpointing is disabled for PostgreSQL
3. Update any hardcoded SQLite assumptions
4. Test database operations with PostgreSQL

### Phase 3: Schema Creation & Testing (0.5 days)

1. Test `init_db()` function with PostgreSQL
2. Verify all tables are created correctly
3. Verify seed data (organizations) is created
4. Test basic CRUD operations
5. Verify migrations work correctly

### Phase 4: Testing & Deployment (0.5 days)

1. **WSL Development Testing:**

   - Test full application with PostgreSQL in WSL
   - Verify connection from Windows host (if needed)
   - Test service restart behavior

2. **Ubuntu Server Deployment:**

   - Deploy PostgreSQL on Ubuntu server (fresh installation)
   - Create database and user (see Phase 1)
   - Configure systemd service auto-start
   - Set up SSL/TLS for secure connections (if remote access needed)
   - Configure firewall rules
   - Deploy application code with PostgreSQL connection string
   - Run application - schema will be created automatically via `init_db()`

3. **General Testing:**

   - Verify Redis integration still works
   - Test application startup with fresh PostgreSQL database
   - Verify schema creation and seed data
   - Performance testing (compare SQLite vs PostgreSQL)
   - Document deployment procedure for both environments

## Benefits of PostgreSQL+Redis

**Advantages:**

1. **Better concurrency:** PostgreSQL handles concurrent writes better than SQLite
2. **Scalability:** Can scale horizontally with read replicas
3. **Advanced features:** Full-text search, JSON queries, better indexing
4. **Production-ready:** Better suited for production deployments
5. **Backup/restore:** Standard PostgreSQL tools (pg_dump, pg_restore)
6. **Monitoring:** Rich ecosystem of monitoring tools

**Considerations:**

1. **Infrastructure:** Requires PostgreSQL server (additional service to manage)
2. **Complexity:** More moving parts than SQLite file
3. **Deployment:** Need to provision PostgreSQL in production
4. **Cost:** May require additional infrastructure costs

## Risk Assessment

**Low Risk:**

- Redis integration (no changes)
- SQLAlchemy models (already database-agnostic)
- Application logic (minimal changes)

**Medium Risk:**

- Data migration (requires careful testing)
- Performance differences (may need tuning)
- Connection pooling (needs optimization)

**Mitigation:**

- Test migration script thoroughly
- Keep SQLite code path for rollback
- Gradual rollout with monitoring
- Database backups before migration

## Estimated Effort

- **Code changes:** 0.5-1 day (mostly verification)
- **PostgreSQL setup:** 0.5 day (WSL + Ubuntu)
- **Schema testing:** 0.5 day
- **Deployment & testing:** 0.5 day
- **Documentation:** 0.5 days
- **Total:** 2.5-3 days (reduced from 3.5-4.5 days due to no data migration)

## Recommendation

The migration is **feasible and moderate in difficulty**. The codebase is already well-prepared with database-agnostic patterns. The main work is:

1. Creating the data migration script
2. Testing thoroughly
3. Updating deployment procedures

Consider migrating if:

- You need better concurrent write performance
- You're planning to scale horizontally
- You want production-grade database features
- You have PostgreSQL expertise in the team

Consider staying with SQLite if:

- Current performance is acceptable
- You want to minimize infrastructure complexity
- Single-server deployment is sufficient
- Team is more familiar with SQLite