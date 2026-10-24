BEGIN;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS fixture_lineup_snapshots (
    id BIGSERIAL PRIMARY KEY,
    fixture_id INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE RESTRICT,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    provider VARCHAR(40) NOT NULL,
    payload JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    source_ref TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    validation_status VARCHAR(30) NOT NULL,
    validation_reason TEXT,
    schema_version VARCHAR(60) NOT NULL DEFAULT 'api-football-grid-v3',
    UNIQUE(fixture_id, team_id, provider, payload_hash)
);
CREATE INDEX IF NOT EXISTS ix_lineup_snapshot_fixture ON fixture_lineup_snapshots(fixture_id, team_id);

CREATE TABLE IF NOT EXISTS position_source_coverage (
    id BIGSERIAL PRIMARY KEY,
    scope_key VARCHAR(160) NOT NULL,
    proof_hash VARCHAR(64) NOT NULL,
    proof JSONB NOT NULL,
    status VARCHAR(30) NOT NULL CHECK(status IN ('partial','complete','unavailable','invalid')),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(scope_key, proof_hash)
);

CREATE TABLE IF NOT EXISTS player_position_evidence (
    id BIGSERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    lineup_snapshot_id BIGINT REFERENCES fixture_lineup_snapshots(id) ON DELETE RESTRICT,
    fixture_id INTEGER REFERENCES fixtures(id) ON DELETE RESTRICT,
    team_id INTEGER REFERENCES teams(id) ON DELETE RESTRICT,
    competition_id INTEGER REFERENCES competitions(id) ON DELETE RESTRICT,
    season VARCHAR(10),
    assertion_kind VARCHAR(40) NOT NULL,
    position VARCHAR(10),
    tactical_role VARCHAR(15),
    side VARCHAR(10),
    source_ref TEXT NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    details JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(player_id, assertion_kind, source_hash)
);
CREATE INDEX IF NOT EXISTS ix_position_evidence_context ON player_position_evidence(player_id, team_id, season);

CREATE TABLE IF NOT EXISTS player_position_assignments (
    id BIGSERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    team_id INTEGER REFERENCES teams(id) ON DELETE RESTRICT,
    competition_id INTEGER REFERENCES competitions(id) ON DELETE RESTRICT,
    season VARCHAR(10),
    position VARCHAR(10) NOT NULL CHECK(position IN ('GK','DC','LAT','MC','MCO','EXT','DEL')),
    tactical_role VARCHAR(15),
    side VARCHAR(10),
    secondaries JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL CHECK(status IN ('legacy','draft','accepted','superseded')),
    effective_from TIMESTAMPTZ NOT NULL,
    effective_until TIMESTAMPTZ,
    revision_id VARCHAR(64) NOT NULL UNIQUE,
    evidence_ids JSONB NOT NULL DEFAULT '[]',
    source_kind VARCHAR(40) NOT NULL,
    reason TEXT NOT NULL,
    actor VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK(effective_until IS NULL OR effective_until > effective_from),
    EXCLUDE USING gist (
        player_id WITH =,
        (COALESCE(team_id,0)) WITH =,
        (COALESCE(competition_id,0)) WITH =,
        (COALESCE(season,'')) WITH =,
        tstzrange(effective_from,effective_until,'[)') WITH &&
    ) WHERE (status = 'accepted')
);
CREATE INDEX IF NOT EXISTS ix_position_assignment_lookup ON player_position_assignments(player_id,status,effective_from);

CREATE OR REPLACE FUNCTION protect_accepted_player_position() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE incoming JSONB;
BEGIN
    IF current_setting('sfa.position_publication',true) IS DISTINCT FROM 'on'
       AND (NEW.position IS DISTINCT FROM OLD.position OR NEW.position_source IS DISTINCT FROM OLD.position_source)
       AND EXISTS(SELECT 1 FROM player_position_assignments a WHERE a.player_id=OLD.id
                  AND a.status='accepted' AND a.effective_from<=now()
                  AND (a.effective_until IS NULL OR a.effective_until>now())) THEN
        incoming := jsonb_build_object('mapped_input_position',NEW.position::text,
                      'input_source',NEW.position_source,'reason','accepted_assignment_preserved');
        INSERT INTO player_position_evidence(player_id,assertion_kind,position,source_ref,source_hash,details)
        VALUES(OLD.id,'incoming_mapped_candidate',NEW.position::text,'guard:players_update',
               encode(digest(incoming::text,'sha256'),'hex'),incoming)
        ON CONFLICT(player_id,assertion_kind,source_hash) DO NOTHING;
        NEW.position := OLD.position;
        NEW.position_source := OLD.position_source;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_accepted_player_position ON players;
CREATE TRIGGER protect_accepted_player_position BEFORE UPDATE OF position,position_source ON players
FOR EACH ROW EXECUTE FUNCTION protect_accepted_player_position();
COMMIT;
