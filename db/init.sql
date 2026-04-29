-- =====================================================================
-- Apparel Line Balancing System - PostgreSQL Schema (Phase 1)
-- =====================================================================
-- Covers master data + line balancing transactions. Phase 2/3 tables
-- (WIP, hourly production, time studies, IoT) are stubbed at the end.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------- ENUMS ----------------------------------------------------
DO $$ BEGIN
    CREATE TYPE machine_type AS ENUM (
        'SNLS', 'OL', 'FOA', 'BARTACK', 'BUTTON', 'BUTTONHOLE', 'IRON', 'MANUAL'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE machine_status AS ENUM ('WORKING', 'IDLE', 'BREAKDOWN', 'MAINTENANCE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE attendance_status AS ENUM ('PRESENT', 'ABSENT', 'LEAVE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('ADMIN', 'PRODUCTION_MANAGER', 'SUPERVISOR', 'IE', 'OPERATOR');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE balance_status AS ENUM ('DRAFT', 'PROPOSED', 'APPLIED', 'REJECTED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------- USERS / AUTH --------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(80) UNIQUE NOT NULL,
    email           VARCHAR(160) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(160),
    role            user_role NOT NULL DEFAULT 'IE',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- LINES / MACHINES ----------------------------------------
CREATE TABLE IF NOT EXISTS lines (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(40) UNIQUE NOT NULL,
    name            VARCHAR(120) NOT NULL,
    capacity        INTEGER NOT NULL DEFAULT 30,           -- max operators
    working_minutes INTEGER NOT NULL DEFAULT 480,          -- minutes/day
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machines (
    id              SERIAL PRIMARY KEY,
    machine_code    VARCHAR(60) UNIQUE NOT NULL,
    type            machine_type NOT NULL,
    line_id         INTEGER REFERENCES lines(id) ON DELETE SET NULL,
    status          machine_status NOT NULL DEFAULT 'IDLE',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_machines_type ON machines(type);
CREATE INDEX IF NOT EXISTS idx_machines_line ON machines(line_id);

-- ---------- OPERATORS -----------------------------------------------
CREATE TABLE IF NOT EXISTS operators (
    id                   SERIAL PRIMARY KEY,
    employee_code        VARCHAR(60) UNIQUE NOT NULL,
    name                 VARCHAR(160) NOT NULL,
    grade                INTEGER NOT NULL DEFAULT 1 CHECK (grade BETWEEN 1 AND 5),
    base_efficiency      NUMERIC(5,2) NOT NULL DEFAULT 80.00 CHECK (base_efficiency BETWEEN 0 AND 200),
    attendance_status    attendance_status NOT NULL DEFAULT 'PRESENT',
    current_line_id      INTEGER REFERENCES lines(id) ON DELETE SET NULL,
    user_id              UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- STYLES / OPERATIONS / PRECEDENCE ------------------------
CREATE TABLE IF NOT EXISTS styles (
    id              SERIAL PRIMARY KEY,
    style_code      VARCHAR(60) UNIQUE NOT NULL,
    name            VARCHAR(200) NOT NULL,
    garment_type    VARCHAR(80),
    total_sam       NUMERIC(10,3),                          -- minutes (cached, recompute from ops)
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operations (
    id              SERIAL PRIMARY KEY,
    style_id        INTEGER NOT NULL REFERENCES styles(id) ON DELETE CASCADE,
    op_code         VARCHAR(60) NOT NULL,                   -- unique within style
    sequence        INTEGER NOT NULL,
    description     VARCHAR(240) NOT NULL,
    sam             NUMERIC(8,3) NOT NULL CHECK (sam > 0),  -- standard allowed minutes
    machine_type    machine_type NOT NULL,
    skill_level     INTEGER NOT NULL DEFAULT 1 CHECK (skill_level BETWEEN 1 AND 5),
    section         VARCHAR(80),                            -- e.g. front, back, assembly
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (style_id, op_code)
);
CREATE INDEX IF NOT EXISTS idx_ops_style ON operations(style_id);

CREATE TABLE IF NOT EXISTS operation_precedence (
    id              SERIAL PRIMARY KEY,
    style_id        INTEGER NOT NULL REFERENCES styles(id) ON DELETE CASCADE,
    predecessor_id  INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    successor_id    INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    UNIQUE (predecessor_id, successor_id),
    CHECK (predecessor_id <> successor_id)
);

-- ---------- OPERATOR SKILL MATRIX -----------------------------------
-- Efficiency per operation = % vs SAM (100 = on-target)
CREATE TABLE IF NOT EXISTS operator_skills (
    id              SERIAL PRIMARY KEY,
    operator_id     INTEGER NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    operation_id    INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    efficiency      NUMERIC(5,2) NOT NULL CHECK (efficiency BETWEEN 0 AND 200),
    is_certified    BOOLEAN NOT NULL DEFAULT TRUE,
    last_used       TIMESTAMPTZ,
    UNIQUE (operator_id, operation_id)
);
CREATE INDEX IF NOT EXISTS idx_skills_op ON operator_skills(operation_id);

-- ---------- BALANCING RUNS ------------------------------------------
CREATE TABLE IF NOT EXISTS balance_runs (
    id                  SERIAL PRIMARY KEY,
    style_id            INTEGER NOT NULL REFERENCES styles(id) ON DELETE CASCADE,
    line_id             INTEGER NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
    target_output_hour  INTEGER NOT NULL,
    working_minutes     INTEGER NOT NULL DEFAULT 480,
    available_operators INTEGER NOT NULL,
    takt_time           NUMERIC(8,3),                        -- minutes/piece
    theoretical_ops     INTEGER,
    line_efficiency     NUMERIC(5,2),
    balance_loss        NUMERIC(5,2),
    bottleneck_op_id    INTEGER REFERENCES operations(id),
    status              balance_status NOT NULL DEFAULT 'DRAFT',
    solver              VARCHAR(40) NOT NULL DEFAULT 'cp-sat',
    notes               TEXT,
    explanation         TEXT,                                -- Claude-generated narrative
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_style ON balance_runs(style_id);
CREATE INDEX IF NOT EXISTS idx_runs_line ON balance_runs(line_id);

CREATE TABLE IF NOT EXISTS balance_assignments (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES balance_runs(id) ON DELETE CASCADE,
    station         INTEGER NOT NULL,                        -- 1..N
    operator_id     INTEGER REFERENCES operators(id) ON DELETE SET NULL,
    operation_id    INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    machine_id      INTEGER REFERENCES machines(id) ON DELETE SET NULL,
    cycle_time      NUMERIC(8,3) NOT NULL,                   -- minutes
    expected_output INTEGER,                                  -- per hour
    UNIQUE (run_id, operation_id)
);
CREATE INDEX IF NOT EXISTS idx_assign_run ON balance_assignments(run_id);
CREATE INDEX IF NOT EXISTS idx_assign_station ON balance_assignments(run_id, station);

-- ---------- PHASE 2/3 STUBS -----------------------------------------
CREATE TABLE IF NOT EXISTS hourly_production (
    id              SERIAL PRIMARY KEY,
    line_id         INTEGER NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
    run_id          INTEGER REFERENCES balance_runs(id) ON DELETE SET NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hour_slot       INTEGER NOT NULL,                        -- 1..N hours of shift
    target          INTEGER NOT NULL,
    actual          INTEGER NOT NULL,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS time_studies (
    id              SERIAL PRIMARY KEY,
    operation_id    INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    operator_id     INTEGER REFERENCES operators(id) ON DELETE SET NULL,
    captured_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    cycle_seconds   NUMERIC(8,3) NOT NULL,
    rating          NUMERIC(5,2) NOT NULL DEFAULT 100,       -- performance rating %
    allowance       NUMERIC(5,2) NOT NULL DEFAULT 15,        -- %
    captured_sam    NUMERIC(8,3) GENERATED ALWAYS AS
                    ((cycle_seconds/60.0) * (rating/100.0) * (1 + allowance/100.0)) STORED,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS machine_telemetry (
    id              BIGSERIAL PRIMARY KEY,
    machine_id      INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_running      BOOLEAN NOT NULL,
    rpm             INTEGER,
    payload         JSONB
);
CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time ON machine_telemetry(machine_id, captured_at DESC);

-- ---------- TRIGGERS -------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['users','machines','operators','styles']) LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_touch_%I ON %I', t, t);
        EXECUTE format('CREATE TRIGGER trg_touch_%I BEFORE UPDATE ON %I
                        FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t, t);
    END LOOP;
END $$;
