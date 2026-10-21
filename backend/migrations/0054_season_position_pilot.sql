BEGIN;
ALTER TABLE position_correction_batches ADD COLUMN reverted_by TEXT;

CREATE TABLE position_scope_classifications (
 id BIGSERIAL PRIMARY KEY,
 player_id INTEGER NOT NULL REFERENCES players(id),
 team_id INTEGER NOT NULL REFERENCES teams(id),
 scope_key TEXT NOT NULL,
 position TEXT NOT NULL CHECK(position IN ('DC','LAT','MC','MCO','EXT','DEL')),
 competition_ids INTEGER[] NOT NULL,
 scope_competition_ids INTEGER[] NOT NULL,
 decision_id VARCHAR(64) NOT NULL,
 definition JSONB NOT NULL,
 batch_id VARCHAR(64) NOT NULL REFERENCES position_correction_batches(batch_id),
 UNIQUE(player_id,scope_key,batch_id)
);
CREATE INDEX ix_position_scope_player ON position_scope_classifications(player_id,scope_key);

CREATE TABLE position_lineup_arbitrations (
 id BIGSERIAL PRIMARY KEY,
 fixture_id INTEGER NOT NULL REFERENCES fixtures(id),
 team_id INTEGER NOT NULL REFERENCES teams(id),
 active_snapshot_id BIGINT NOT NULL REFERENCES fixture_lineup_snapshots(id),
 compatible_snapshot_ids BIGINT[] NOT NULL,
 revision_id VARCHAR(64) NOT NULL UNIQUE,
 source_ref TEXT NOT NULL,
 fetched_at TIMESTAMPTZ NOT NULL,
 supersedes JSONB NOT NULL,
 reason TEXT NOT NULL,
 actor TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_position_lineup_arbitration ON position_lineup_arbitrations(fixture_id,team_id,id DESC);

CREATE VIEW position_active_lineup_snapshots AS
 SELECT s.* FROM fixture_lineup_snapshots s LEFT JOIN LATERAL
  (SELECT a.compatible_snapshot_ids FROM position_lineup_arbitrations a
   WHERE a.fixture_id=s.fixture_id AND a.team_id=s.team_id
   ORDER BY a.fetched_at DESC,a.id DESC LIMIT 1) a ON true
 WHERE a.compatible_snapshot_ids IS NULL OR s.id=ANY(a.compatible_snapshot_ids);

CREATE FUNCTION guard_position_arbitration() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' OR current_setting('sfa.position_publication',true) IS DISTINCT FROM 'on' THEN
  RAISE EXCEPTION 'Provider arbitrations are immutable journal evidence';
 END IF;
 IF NOT NEW.active_snapshot_id=ANY(NEW.compatible_snapshot_ids) OR EXISTS
  (SELECT 1 FROM unnest(NEW.compatible_snapshot_ids) i LEFT JOIN fixture_lineup_snapshots s ON s.id=i
   WHERE s.id IS NULL OR s.fixture_id<>NEW.fixture_id OR s.team_id<>NEW.team_id) THEN
  RAISE EXCEPTION 'Arbitration snapshot identities do not match';
 END IF;
 IF EXISTS(SELECT 1 FROM position_lineup_arbitrations a WHERE a.fixture_id=NEW.fixture_id AND a.team_id=NEW.team_id
  AND a.fetched_at=NEW.fetched_at AND NOT a.active_snapshot_id=ANY(NEW.compatible_snapshot_ids)) THEN
  RAISE EXCEPTION 'Equal-time incompatible provider revisions require quarantine';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_position_arbitration BEFORE INSERT OR UPDATE OR DELETE ON position_lineup_arbitrations
 FOR EACH ROW EXECUTE FUNCTION guard_position_arbitration();

CREATE FUNCTION guard_scope_classification() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Scope classification history is immutable'; END IF;
 IF current_setting('sfa.position_publication',true) IS DISTINCT FROM 'on' THEN
  RAISE EXCEPTION 'Scope classifications require the exclusive journal publisher';
 END IF;
 IF EXISTS(SELECT 1 FROM position_scope_classifications c JOIN position_correction_batches b
   ON b.batch_id=c.batch_id WHERE c.player_id=NEW.player_id AND c.scope_key=NEW.scope_key
     AND b.status='published' AND c.batch_id<>NEW.batch_id) THEN
  RAISE EXCEPTION 'Another published classification already occupies this scope';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_scope_classification BEFORE INSERT OR UPDATE OR DELETE ON position_scope_classifications
 FOR EACH ROW EXECUTE FUNCTION guard_scope_classification();

CREATE FUNCTION sfa_scope_position(p_player INTEGER,p_scope TEXT,p_comp INTEGER,p_scope_comps INTEGER[],p_default TEXT)
RETURNS TEXT LANGUAGE SQL STABLE AS $$
 SELECT coalesce((SELECT c.position FROM position_scope_classifications c
  JOIN position_correction_batches b ON b.batch_id=c.batch_id AND b.status='published'
  WHERE c.player_id=p_player AND c.scope_key=p_scope AND c.scope_competition_ids=p_scope_comps
   AND (p_comp IS NULL OR p_comp=ANY(c.competition_ids)) LIMIT 1),p_default)
$$;

-- History may consume an explicitly reviewed scoring decision for that fixture;
-- a current habitual-role lookup never consumes it or a scope display label.
CREATE OR REPLACE FUNCTION sfa_accepted_position(p_player INTEGER,p_team INTEGER,p_comp INTEGER,p_season TEXT,
                                     p_at TIMESTAMPTZ,p_fixture INTEGER) RETURNS TEXT
LANGUAGE plpgsql STABLE AS $$
DECLARE positions TEXT[];
BEGIN
 SELECT array_agg(DISTINCT a.position) INTO positions FROM player_position_assignments a
 WHERE a.player_id=p_player AND a.status='accepted'
  AND a.effective_from<=p_at AND (a.effective_until IS NULL OR p_at<a.effective_until)
  AND (a.team_id IS NULL OR a.team_id=p_team)
  AND (a.competition_id IS NULL OR a.competition_id=p_comp)
  AND (a.season IS NULL OR a.season=p_season)
  AND ((a.assertion_kind='habitual_football_role' AND
        (a.applicable_fixture_ids IS NULL OR p_fixture=ANY(a.applicable_fixture_ids))) OR
       (a.assertion_kind='curated_fixture_scoring_role' AND p_fixture=ANY(a.applicable_fixture_ids)))
  AND (a.publication_batch_id IS NULL OR EXISTS(SELECT 1 FROM position_correction_batches b
    WHERE b.batch_id=a.publication_batch_id AND b.status='published'));
 IF cardinality(positions)>1 THEN RAISE EXCEPTION 'Conflicting position assignments for %',p_player; END IF;
 RETURN positions[1];
END $$;

CREATE FUNCTION sfa_fixture_scoring_position(p_player INTEGER,p_fixture INTEGER,p_fallback TEXT)
RETURNS TEXT LANGUAGE SQL STABLE AS $$
 SELECT coalesce(sfa_accepted_position(p_player,ps.team_id,f.competition_id,f.season,f.played_at,f.id),p_fallback)
 FROM fixtures f LEFT JOIN player_stats ps ON ps.fixture_id=f.id AND ps.player_id=p_player
 WHERE f.id=p_fixture
$$;

-- A full-season aggregate can be updated by legitimate new fixtures. Its
-- reviewed achievement component must survive a legacy bonus rebuild.
CREATE FUNCTION conserve_reviewed_bonus() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE incoming JSONB; existing player_achievement_bonuses; protected BOOLEAN; old_id BIGINT; protected_player INTEGER;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN
  IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 incoming:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 old_id:=CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN OLD.id ELSE NULL END;
 protected_player:=CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN OLD.player_id ELSE NEW.player_id END;
 SELECT * INTO existing FROM player_achievement_bonuses p
  WHERE p.player_id=(incoming->>'player_id')::INTEGER AND p.achievement_id=(incoming->>'achievement_id')::INTEGER
    AND p.rules_version_id=(incoming->>'rules_version_id')::INTEGER LIMIT 1;
 SELECT EXISTS(SELECT 1 FROM position_correction_batches b,
  jsonb_array_elements(coalesce(b.after_image->'bonuses','[]')) r
  WHERE b.status='published' AND ((r->>'id')::BIGINT=coalesce(existing.id,(incoming->>'id')::BIGINT)
     OR (r->>'id')::BIGINT=old_id)) INTO protected;
 IF protected AND (TG_OP<>'UPDATE' OR incoming IS DISTINCT FROM to_jsonb(OLD)) THEN
  PERFORM record_position_dependency_update(protected_player,NULL,TG_TABLE_NAME,TG_OP,incoming);
  IF TG_OP='UPDATE' THEN RETURN OLD; ELSE RETURN NULL; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER conserve_reviewed_bonus BEFORE INSERT OR UPDATE OR DELETE ON player_achievement_bonuses
 FOR EACH ROW EXECUTE FUNCTION conserve_reviewed_bonus();

CREATE FUNCTION preserve_reviewed_bonus_rollup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected NUMERIC;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND (OLD.id,OLD.player_id,OLD.competition_id,OLD.season,OLD.rules_version_id)
    IS DISTINCT FROM (NEW.id,NEW.player_id,NEW.competition_id,NEW.season,NEW.rules_version_id)
    AND EXISTS(SELECT 1 FROM position_correction_batches b,jsonb_array_elements(coalesce(b.after_image->'rollups','[]')) r
      WHERE b.status='published' AND (r->>'id')::BIGINT=OLD.id) THEN
  PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'MOVED_ROLLUP',to_jsonb(NEW));
  RETURN OLD;
 END IF;
 IF EXISTS(SELECT 1 FROM position_correction_batches b,jsonb_array_elements(coalesce(b.after_image->'rollups','[]')) r
    WHERE b.status='published' AND (r->>'id')::INTEGER=NEW.id) THEN
  SELECT coalesce(sum(final_bonus),0) INTO expected FROM player_achievement_bonuses
   WHERE player_id=NEW.player_id AND competition_id=NEW.competition_id AND season=NEW.season
     AND rules_version_id IS NOT DISTINCT FROM NEW.rules_version_id;
  IF NEW.achievement_bonus_pts IS DISTINCT FROM expected THEN
   PERFORM record_position_dependency_update(NEW.player_id,NULL,TG_TABLE_NAME,'BONUS_ROLLUP',to_jsonb(NEW));
   NEW.achievement_bonus_pts:=expected;
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER preserve_reviewed_bonus_rollup BEFORE INSERT OR UPDATE ON sfa_season_scores
 FOR EACH ROW EXECUTE FUNCTION preserve_reviewed_bonus_rollup();

CREATE FUNCTION conserve_reviewed_peer_rollup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN RETURN OLD; END IF;
 IF EXISTS(SELECT 1 FROM position_correction_batches b,jsonb_array_elements(coalesce(b.after_image->'rollups','[]')) r
   WHERE b.status='published' AND (r->>'id')::INTEGER=OLD.id) THEN
  PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'DELETE',to_jsonb(OLD));
  RETURN NULL;
 END IF;
 RETURN OLD;
END $$;
CREATE TRIGGER conserve_reviewed_peer_rollup BEFORE DELETE ON sfa_season_scores
 FOR EACH ROW EXECUTE FUNCTION conserve_reviewed_peer_rollup();

CREATE TRIGGER position_writer_shared_lock BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE
 ON position_scope_classifications FOR EACH STATEMENT EXECUTE FUNCTION position_writer_shared_lock();
CREATE TRIGGER position_writer_shared_lock BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE
 ON position_lineup_arbitrations FOR EACH STATEMENT EXECUTE FUNCTION position_writer_shared_lock();
CREATE TRIGGER deny_curated_truncate BEFORE TRUNCATE ON position_scope_classifications
 FOR EACH STATEMENT EXECUTE FUNCTION deny_curated_truncate();
CREATE TRIGGER deny_curated_truncate BEFORE TRUNCATE ON position_lineup_arbitrations
 FOR EACH STATEMENT EXECUTE FUNCTION deny_curated_truncate();
COMMIT;
