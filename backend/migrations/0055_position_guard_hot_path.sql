BEGIN;
-- Reconstructible, bounded projections of the immutable publication journal.
CREATE FUNCTION position_guard_ids(image JSONB, collection TEXT) RETURNS BIGINT[]
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE ids BIGINT[]; item JSONB; value BIGINT;
BEGIN
 IF image ? collection AND jsonb_typeof(image->collection) IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION 'Malformed position journal collection: %',collection;
 END IF;
 ids:=ARRAY[]::BIGINT[];
 FOR item IN SELECT * FROM jsonb_array_elements(coalesce(image->collection,'[]'::jsonb)) LOOP
  IF jsonb_typeof(item) IS DISTINCT FROM 'object' OR item->>'id' IS NULL THEN
   RAISE EXCEPTION 'Malformed position journal identity in %',collection;
  END IF;
  value:=(item->>'id')::BIGINT;
  IF value<=0 OR value=ANY(ids) THEN RAISE EXCEPTION 'Invalid/duplicate journal identity'; END IF;
  ids:=array_append(ids,value);
 END LOOP;
 RETURN ids;
END $$;
ALTER TABLE position_correction_batches
 ADD COLUMN guard_rules_version_id INTEGER GENERATED ALWAYS AS ((manifest->>'rules_version_id')::INTEGER) STORED,
 ADD COLUMN guard_bonus_ids BIGINT[] GENERATED ALWAYS AS (position_guard_ids(after_image,'bonuses')) STORED,
 ADD COLUMN guard_rollup_ids BIGINT[] GENERATED ALWAYS AS (position_guard_ids(after_image,'rollups')) STORED;
ALTER TABLE position_correction_batches ALTER COLUMN guard_rules_version_id SET NOT NULL;
ALTER TABLE position_correction_batches ADD CONSTRAINT ck_guard_rules_version CHECK(guard_rules_version_id>0);
CREATE INDEX ix_curated_assignment_fixture_allowlist ON player_position_assignments
 USING GIN(applicable_fixture_ids) WHERE status='accepted' AND applicable_fixture_ids IS NOT NULL;


CREATE OR REPLACE FUNCTION conserve_curated_position_records() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE incoming JSONB; record_player INTEGER; record_fixture INTEGER; published_version INTEGER;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN
   IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 incoming:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 record_player:=(incoming->>'player_id')::INTEGER;
 record_fixture:=(incoming->>'fixture_id')::INTEGER;
 -- An UPDATE may not move a protected OLD identity outside its published scope.
 IF TG_OP='UPDATE' AND sfa_curated_fixture(OLD.player_id,OLD.fixture_id) THEN
   record_player:=OLD.player_id; record_fixture:=OLD.fixture_id;
 END IF;
 IF sfa_curated_fixture(record_player,record_fixture) THEN
   IF TG_TABLE_NAME='player_event_scores' THEN
     SELECT b.guard_rules_version_id INTO published_version
     FROM player_position_assignments a JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id
     WHERE a.player_id=record_player AND record_fixture=ANY(a.applicable_fixture_ids)
       AND a.status='accepted' AND b.status='published' LIMIT 1;
     IF (incoming->>'rules_version_id')::INTEGER<>published_version
         AND NOT (TG_OP='UPDATE' AND (to_jsonb(OLD)->>'rules_version_id')::INTEGER=published_version) THEN
       IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
     END IF;
   END IF;
   IF TG_OP='UPDATE' AND to_jsonb(OLD)=incoming THEN RETURN OLD; END IF;
   PERFORM record_position_dependency_update(record_player,record_fixture,TG_TABLE_NAME,TG_OP,incoming);
   IF TG_OP='UPDATE' THEN RETURN OLD; ELSE RETURN NULL; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;

CREATE OR REPLACE FUNCTION validate_curated_season_aggregate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_total NUMERIC; expected_matches INTEGER; expected_breakdown JSONB;
BEGIN
 IF TG_OP='DELETE' THEN
   IF EXISTS(SELECT 1 FROM player_position_assignments a JOIN position_correction_batches b
        ON b.batch_id=a.publication_batch_id AND b.status='published'
      WHERE a.player_id=OLD.player_id AND a.season=OLD.season AND a.status='accepted'
        AND b.guard_rules_version_id=OLD.rules_version_id) THEN
     PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'DELETE',to_jsonb(OLD));
     RETURN NULL;
   END IF;
   RETURN OLD;
 END IF;
 IF current_setting('sfa.position_publication',true)='on' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND (OLD.player_id,OLD.competition_id,OLD.season,OLD.rules_version_id)
    IS DISTINCT FROM (NEW.player_id,NEW.competition_id,NEW.season,NEW.rules_version_id)
    AND EXISTS(SELECT 1 FROM player_position_assignments a JOIN position_correction_batches b
      ON b.batch_id=a.publication_batch_id AND b.status='published'
      WHERE a.player_id=OLD.player_id AND a.season=OLD.season AND a.status='accepted'
        AND b.guard_rules_version_id=OLD.rules_version_id) THEN
   PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'MOVED_ROLLUP',to_jsonb(NEW));
   RETURN OLD;
 END IF;
 IF EXISTS(SELECT 1 FROM player_position_assignments a JOIN position_correction_batches b
       ON b.batch_id=a.publication_batch_id AND b.status='published'
     WHERE a.player_id=NEW.player_id AND a.season=NEW.season AND a.status='accepted'
       AND b.guard_rules_version_id=NEW.rules_version_id
       AND EXISTS(SELECT 1 FROM fixtures f WHERE f.id=ANY(a.applicable_fixture_ids)
                   AND f.competition_id=NEW.competition_id)) THEN
   SELECT sum(final_points),count(DISTINCT fixture_id) INTO expected_total,expected_matches
    FROM player_event_scores WHERE player_id=NEW.player_id AND competition_id=NEW.competition_id
      AND season=NEW.season AND rules_version_id=NEW.rules_version_id;
   SELECT jsonb_object_agg(action_type,jsonb_build_object('count',n,'pts',pts,
       'pct',CASE WHEN expected_total=0 THEN 0 ELSE round(pts/expected_total*100,1) END))
     INTO expected_breakdown FROM (
       SELECT action_type,count(*) n,sum(final_points) pts FROM player_event_scores
       WHERE player_id=NEW.player_id AND competition_id=NEW.competition_id
         AND season=NEW.season AND rules_version_id=NEW.rules_version_id GROUP BY action_type
     ) actions;
   IF NEW.total_pts IS DISTINCT FROM expected_total OR NEW.matches_played IS DISTINCT FROM expected_matches
       OR NEW.breakdown IS DISTINCT FROM expected_breakdown THEN
     PERFORM record_position_dependency_update(NEW.player_id,NULL,TG_TABLE_NAME,'UNRECONCILED_ROLLUP',to_jsonb(NEW));
     NEW.total_pts:=expected_total; NEW.matches_played:=expected_matches; NEW.breakdown:=expected_breakdown;
   END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION conserve_reviewed_bonus() RETURNS trigger LANGUAGE plpgsql AS $$
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
 SELECT EXISTS(SELECT 1 FROM position_correction_batches b
  WHERE b.status='published' AND (coalesce(existing.id,(incoming->>'id')::BIGINT)=ANY(b.guard_bonus_ids)
     OR old_id=ANY(b.guard_bonus_ids))) INTO protected;
 IF protected AND (TG_OP<>'UPDATE' OR incoming IS DISTINCT FROM to_jsonb(OLD)) THEN
  PERFORM record_position_dependency_update(protected_player,NULL,TG_TABLE_NAME,TG_OP,incoming);
  IF TG_OP='UPDATE' THEN RETURN OLD; ELSE RETURN NULL; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;

CREATE OR REPLACE FUNCTION preserve_reviewed_bonus_rollup() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected NUMERIC;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND (OLD.id,OLD.player_id,OLD.competition_id,OLD.season,OLD.rules_version_id)
    IS DISTINCT FROM (NEW.id,NEW.player_id,NEW.competition_id,NEW.season,NEW.rules_version_id)
    AND EXISTS(SELECT 1 FROM position_correction_batches b
      WHERE b.status='published' AND OLD.id=ANY(b.guard_rollup_ids)) THEN
  PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'MOVED_ROLLUP',to_jsonb(NEW));
  RETURN OLD;
 END IF;
 IF EXISTS(SELECT 1 FROM position_correction_batches b
    WHERE b.status='published' AND NEW.id=ANY(b.guard_rollup_ids)) THEN
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

CREATE OR REPLACE FUNCTION conserve_reviewed_peer_rollup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN RETURN OLD; END IF;
 IF EXISTS(SELECT 1 FROM position_correction_batches b
   WHERE b.status='published' AND OLD.id=ANY(b.guard_rollup_ids)) THEN
  PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'DELETE',to_jsonb(OLD));
  RETURN NULL;
 END IF;
 RETURN OLD;
END $$;

CREATE OR REPLACE FUNCTION conserve_curated_scoring_dependencies() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE incoming JSONB; target RECORD; matching_fixture INTEGER; prior JSONB;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN
  IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 incoming:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 IF TG_OP='UPDATE' AND to_jsonb(OLD)=incoming THEN RETURN OLD; END IF;
 IF TG_TABLE_NAME='fixture_team_strengths' THEN
  -- INSERT triggers run even before ON CONFLICT's no-op WHERE predicate.
  IF TG_OP='INSERT' THEN
   SELECT to_jsonb(s)-'created_at' INTO prior FROM fixture_team_strengths s
    WHERE s.fixture_id=(incoming->>'fixture_id')::INTEGER AND s.team_id=(incoming->>'team_id')::INTEGER;
   IF prior=incoming-'created_at' THEN RETURN NEW; END IF;
  ELSIF TG_OP='UPDATE' AND to_jsonb(OLD)-'created_at'=incoming-'created_at' THEN RETURN OLD;
  END IF;
 ELSIF TG_TABLE_NAME='fixtures' AND TG_OP='UPDATE' THEN
  IF (SELECT jsonb_object_agg(k,incoming->k) FROM unnest(ARRAY['status','played_at','season','competition_id',
       'home_team_id','away_team_id','stage']) k)=
     (SELECT jsonb_object_agg(k,to_jsonb(OLD)->k) FROM unnest(ARRAY['status','played_at','season','competition_id',
       'home_team_id','away_team_id','stage']) k) THEN RETURN NEW; END IF;
 ELSIF TG_TABLE_NAME='players' AND TG_OP='UPDATE' THEN
  IF incoming->'birth_date' IS NOT DISTINCT FROM to_jsonb(OLD)->'birth_date'
    AND incoming->'id'=to_jsonb(OLD)->'id' THEN RETURN NEW; END IF;
 ELSIF TG_TABLE_NAME='scoring_rules_versions' AND TG_OP='UPDATE' THEN
  IF incoming->'config_json'=to_jsonb(OLD)->'config_json' THEN RETURN NEW; END IF;
 ELSIF TG_TABLE_NAME='competition_stages' AND TG_OP='UPDATE' THEN
  IF incoming->'stage_factor' IS NOT DISTINCT FROM to_jsonb(OLD)->'stage_factor'
     AND incoming->'competition_id'=to_jsonb(OLD)->'competition_id'
     AND incoming->'stage'=to_jsonb(OLD)->'stage' THEN RETURN NEW; END IF;
 END IF;
 SELECT a.player_id INTO target FROM player_position_assignments a
 JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id AND b.status='published'
 WHERE a.status='accepted' AND a.applicable_fixture_ids IS NOT NULL AND (
  (TG_TABLE_NAME='fixture_team_strengths' AND
   (a.applicable_fixture_ids @> ARRAY[(incoming->>'fixture_id')::INTEGER] OR
    (TG_OP='UPDATE' AND a.applicable_fixture_ids @> ARRAY[(to_jsonb(OLD)->>'fixture_id')::INTEGER]))) OR
  (TG_TABLE_NAME='fixtures' AND
   (a.applicable_fixture_ids @> ARRAY[(incoming->>'id')::INTEGER] OR
    (TG_OP='UPDATE' AND a.applicable_fixture_ids @> ARRAY[(to_jsonb(OLD)->>'id')::INTEGER]))) OR
  (TG_TABLE_NAME='players' AND (a.player_id=(incoming->>'id')::INTEGER OR
    (TG_OP='UPDATE' AND a.player_id=(to_jsonb(OLD)->>'id')::INTEGER))) OR
  (TG_TABLE_NAME='scoring_rules_versions' AND (b.guard_rules_version_id=(incoming->>'id')::INTEGER OR
    (TG_OP='UPDATE' AND b.guard_rules_version_id=(to_jsonb(OLD)->>'id')::INTEGER))) OR
  (TG_TABLE_NAME='competition_stages' AND EXISTS(SELECT 1 FROM fixtures f
    WHERE f.id=ANY(a.applicable_fixture_ids) AND
    ((f.competition_id=(incoming->>'competition_id')::INTEGER AND f.stage=incoming->>'stage') OR
     (TG_OP='UPDATE' AND f.competition_id=(to_jsonb(OLD)->>'competition_id')::INTEGER
      AND f.stage=to_jsonb(OLD)->>'stage')))))
 ORDER BY a.player_id LIMIT 1;
 IF FOUND THEN
  matching_fixture:=CASE WHEN TG_TABLE_NAME='fixture_team_strengths' THEN (incoming->>'fixture_id')::INTEGER
                         WHEN TG_TABLE_NAME='fixtures' THEN (incoming->>'id')::INTEGER ELSE NULL END;
  PERFORM record_position_dependency_update(target.player_id,matching_fixture,TG_TABLE_NAME,TG_OP,incoming);
  IF TG_OP='UPDATE' THEN RETURN OLD; ELSE RETURN NULL; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;


COMMIT;
