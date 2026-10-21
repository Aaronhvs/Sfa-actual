BEGIN;
CREATE TABLE player_name_aliases (
 id SERIAL PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
 external_player_id INTEGER NOT NULL CHECK(external_player_id>0),
 provider VARCHAR(80) NOT NULL,
 alias VARCHAR(250) NOT NULL CHECK(length(trim(alias))>0),
 normalized_alias VARCHAR(250) NOT NULL CHECK(length(trim(normalized_alias))>0),
 source_ref TEXT NOT NULL,
 captured_at TIMESTAMPTZ NOT NULL,
 CONSTRAINT uq_player_name_alias UNIQUE(player_id,provider,normalized_alias)
);
CREATE INDEX ix_player_name_aliases_player_id ON player_name_aliases(player_id);
CREATE TRIGGER position_writer_shared_lock BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE
 ON player_name_aliases FOR EACH STATEMENT EXECUTE FUNCTION position_writer_shared_lock();
CREATE TRIGGER deny_curated_truncate BEFORE TRUNCATE ON player_name_aliases
 FOR EACH STATEMENT EXECUTE FUNCTION deny_curated_truncate();
COMMIT;
