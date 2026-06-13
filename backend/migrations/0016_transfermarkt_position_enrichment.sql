BEGIN;

ALTER TABLE players
  ADD COLUMN IF NOT EXISTS position_source VARCHAR(20) NOT NULL DEFAULT 'apifootball';

COMMENT ON COLUMN players.position_source IS
  'Origin of the position value: transfermarkt | apifootball | heuristic | manual';

CREATE TABLE IF NOT EXISTS player_tm_ids (
    id          SERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    tm_id       INTEGER NOT NULL,
    verified    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id),
    UNIQUE (tm_id)
);

CREATE INDEX IF NOT EXISTS ix_player_tm_ids_player_id ON player_tm_ids(player_id);
CREATE INDEX IF NOT EXISTS ix_player_tm_ids_tm_id ON player_tm_ids(tm_id);

COMMIT;
