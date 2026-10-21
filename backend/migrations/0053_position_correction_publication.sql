BEGIN;
CREATE EXTENSION IF NOT EXISTS unaccent;
ALTER TABLE player_position_assignments ADD COLUMN IF NOT EXISTS applicable_fixture_ids INTEGER[];
ALTER TABLE player_position_assignments ADD COLUMN IF NOT EXISTS assertion_kind VARCHAR(40)
    NOT NULL DEFAULT 'habitual_football_role';
ALTER TABLE player_position_assignments ADD COLUMN IF NOT EXISTS source_ref TEXT;
ALTER TABLE player_position_assignments ADD COLUMN IF NOT EXISTS decision_policy TEXT;
ALTER TABLE player_position_assignments ADD COLUMN IF NOT EXISTS publication_batch_id VARCHAR(64);
ALTER TABLE player_position_assignments ADD CONSTRAINT ck_position_fixture_allowlist
    CHECK(applicable_fixture_ids IS NULL OR (cardinality(applicable_fixture_ids)>0
        AND 0<ALL(applicable_fixture_ids) AND array_position(applicable_fixture_ids,NULL) IS NULL));
DO $$ DECLARE item RECORD; BEGIN
    FOR item IN SELECT conname FROM pg_constraint WHERE conrelid='player_position_assignments'::regclass
                AND contype='x' LOOP
        EXECUTE format('ALTER TABLE player_position_assignments DROP CONSTRAINT %I',item.conname);
    END LOOP;
END $$;

CREATE TABLE position_correction_batches (
    batch_id VARCHAR(64) PRIMARY KEY,
    manifest_hash VARCHAR(64) NOT NULL,
    manifest JSONB NOT NULL,
    before_image JSONB NOT NULL,
    after_image JSONB NOT NULL,
    status VARCHAR(20) NOT NULL CHECK(status IN ('published','reverted')),
    actor TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reverted_at TIMESTAMPTZ
);
CREATE TABLE position_publication_epoch (
    singleton BOOLEAN PRIMARY KEY DEFAULT true CHECK(singleton),
    revision BIGINT NOT NULL DEFAULT 0
);
INSERT INTO position_publication_epoch(singleton) VALUES(true) ON CONFLICT DO NOTHING;

CREATE FUNCTION validate_accepted_position_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE conflicting BIGINT; fixture_count INTEGER;
BEGIN
    IF NEW.status<>'accepted' THEN RETURN NEW; END IF;
    IF current_setting('sfa.position_publication',true) IS DISTINCT FROM 'on' THEN
        RAISE EXCEPTION 'Accepted assignments require the exclusive correction publisher';
    END IF;
    IF NEW.applicable_fixture_ids IS NOT NULL THEN
        IF NEW.team_id IS NULL OR NEW.season IS NULL OR
           cardinality(NEW.applicable_fixture_ids)<>(SELECT count(DISTINCT i)
               FROM unnest(NEW.applicable_fixture_ids) i) THEN
            RAISE EXCEPTION 'Historical fixture allowlist requires unique IDs and explicit team/season';
        END IF;
        SELECT count(*) INTO fixture_count FROM fixtures f WHERE f.id=ANY(NEW.applicable_fixture_ids)
            AND NEW.team_id IN (f.home_team_id,f.away_team_id) AND f.season=NEW.season
            AND (NEW.competition_id IS NULL OR f.competition_id=NEW.competition_id)
            AND f.played_at>=NEW.effective_from
            AND (NEW.effective_until IS NULL OR f.played_at<NEW.effective_until);
        IF fixture_count<>cardinality(NEW.applicable_fixture_ids) THEN
            RAISE EXCEPTION 'Fixture allowlist conflicts with assignment context/interval';
        END IF;
    END IF;
    SELECT a.id INTO conflicting FROM player_position_assignments a
      WHERE a.player_id=NEW.player_id AND a.status='accepted' AND a.id<>NEW.id
        AND (a.team_id IS NULL OR NEW.team_id IS NULL OR a.team_id=NEW.team_id)
        AND (a.competition_id IS NULL OR NEW.competition_id IS NULL OR a.competition_id=NEW.competition_id)
        AND (a.season IS NULL OR NEW.season IS NULL OR a.season=NEW.season)
        AND tstzrange(a.effective_from,a.effective_until,'[)') &&
            tstzrange(NEW.effective_from,NEW.effective_until,'[)')
        AND (a.applicable_fixture_ids IS NULL OR NEW.applicable_fixture_ids IS NULL OR
             a.applicable_fixture_ids && NEW.applicable_fixture_ids)
        AND (a.position<>NEW.position OR coalesce(a.tactical_role,'UNKNOWN')<>
              coalesce(NEW.tactical_role,'UNKNOWN') OR coalesce(a.side,'UNKNOWN')<>
              coalesce(NEW.side,'UNKNOWN') OR a.secondaries<>NEW.secondaries)
      LIMIT 1;
    IF conflicting IS NOT NULL THEN RAISE EXCEPTION 'Conflicting accepted position assignment %',conflicting; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_accepted_position_scope BEFORE INSERT OR UPDATE ON player_position_assignments
    FOR EACH ROW EXECUTE FUNCTION validate_accepted_position_scope();

CREATE FUNCTION sfa_accepted_position(p_player INTEGER,p_team INTEGER,p_comp INTEGER,p_season TEXT,
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
        AND (a.applicable_fixture_ids IS NULL OR p_fixture=ANY(a.applicable_fixture_ids));
    IF cardinality(positions)>1 THEN RAISE EXCEPTION 'Conflicting position assignments for %',p_player; END IF;
    RETURN positions[1];
END $$;

-- Compatibility projection of the existing legacy overrides; never authorizes a new decision.
CREATE FUNCTION sfa_legacy_position(p_default TEXT,p_name TEXT,p_team TEXT,p_comp INTEGER) RETURNS TEXT
LANGUAGE SQL STABLE AS $$
 SELECT CASE
  WHEN unaccent(lower(p_name)) LIKE '%fermin lopez%' OR unaccent(lower(p_name))='fermin' THEN 'MCO'
  WHEN unaccent(lower(p_name)) LIKE '%zubimendi%' THEN 'MC'
  WHEN unaccent(lower(p_name)) LIKE '%aubameyang%' THEN 'DEL'
  WHEN unaccent(lower(p_name)) LIKE '%messi%' AND (p_comp=350 OR lower(p_team)='argentina') THEN 'EXT'
  WHEN unaccent(lower(p_name)) LIKE '%kimmich%' AND (p_comp=350 OR lower(p_team) IN ('germany','alemania')) THEN 'LAT'
  WHEN unaccent(lower(p_name)) LIKE '%olise%' AND (p_comp=350 OR lower(p_team) IN ('france','francia')) THEN 'MCO'
  WHEN unaccent(lower(p_name)) LIKE '%alex baena%' AND (p_comp=350 OR lower(p_team) IN ('spain','espana')) THEN 'EXT'
  ELSE p_default END
$$;

CREATE FUNCTION sfa_current_position(p_player INTEGER,p_comp INTEGER,p_season TEXT,p_at TIMESTAMPTZ)
RETURNS TEXT LANGUAGE SQL STABLE AS $$
 SELECT CASE WHEN EXISTS(SELECT 1 FROM player_position_assignments a
       WHERE a.player_id=p.id AND a.status='accepted' AND a.effective_from<=p_at
         AND (a.effective_until IS NULL OR p_at<a.effective_until)
         AND a.applicable_fixture_ids IS NULL)
     OR unaccent(lower(p.name)) SIMILAR TO '%(messi|kimmich|olise|alex baena)%'
   THEN (SELECT coalesce(sfa_accepted_position(p.id,context.team_id,context.competition_id,context.season,p_at,NULL),
                 sfa_legacy_position(p.position::text,p.name,context.team_name,context.competition_id))
     FROM (VALUES(1)) sentinel LEFT JOIN LATERAL (
   SELECT ps.team_id,f.competition_id,f.season,t.name team_name
   FROM player_stats ps JOIN fixtures f ON f.id=ps.fixture_id JOIN teams t ON t.id=ps.team_id
   JOIN competitions c ON c.id=f.competition_id
   WHERE ps.player_id=p.id AND ps.team_id IN(f.home_team_id,f.away_team_id) AND f.played_at<=p_at
      AND (p_season IS NULL OR f.season=p_season)
      AND ((p_comp IS NOT NULL AND f.competition_id=p_comp) OR (p_comp IS NULL AND c.participant_kind='club'))
   ORDER BY f.played_at DESC,f.id DESC,ps.id DESC LIMIT 1
 ) context ON true)
   ELSE sfa_legacy_position(p.position::text,p.name,NULL,p_comp) END
 FROM players p WHERE p.id=p_player
$$;

CREATE FUNCTION position_writer_shared_lock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock_shared(736615320261019);
    RETURN NULL;
END $$;
DO $$ DECLARE item RECORD; BEGIN
    FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='public'
        AND tablename NOT IN ('position_correction_batches','position_publication_epoch') LOOP
        EXECUTE format('CREATE TRIGGER position_writer_shared_lock BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE '
                       'ON %I FOR EACH STATEMENT EXECUTE FUNCTION position_writer_shared_lock()',item.tablename);
    END LOOP;
END $$;

-- Curated row conservation while legacy ingestion still deletes/recreates events.
CREATE FUNCTION sfa_curated_fixture(p_player INTEGER,p_fixture INTEGER) RETURNS BOOLEAN
LANGUAGE SQL STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM player_position_assignments a
   JOIN position_correction_batches b ON b.batch_id=a.publication_batch_id AND b.status='published'
   WHERE a.player_id=p_player AND a.status='accepted' AND p_fixture=ANY(a.applicable_fixture_ids))
$$;

CREATE FUNCTION record_position_dependency_update(p_player INTEGER,p_fixture INTEGER,p_table TEXT,
                                                  p_operation TEXT,p_incoming JSONB) RETURNS VOID
LANGUAGE plpgsql AS $$
DECLARE details JSONB;
BEGIN
 details:=jsonb_build_object('table',p_table,'operation',p_operation,'fixture_id',p_fixture,
                             'incoming',p_incoming,'state','dependency_update_pending_review');
 INSERT INTO player_position_evidence(player_id,fixture_id,assertion_kind,source_ref,source_hash,details)
 VALUES(p_player,p_fixture,'dependency_update_candidate','guard:'||p_table,
        encode(digest((details-'incoming'||jsonb_build_object('incoming',p_incoming-'id'))::text,'sha256'),'hex'),details)
 ON CONFLICT(player_id,assertion_kind,source_hash) DO NOTHING;
END $$;

CREATE FUNCTION conserve_curated_position_records() RETURNS trigger LANGUAGE plpgsql AS $$
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
     SELECT (b.manifest->>'rules_version_id')::INTEGER INTO published_version
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
CREATE TRIGGER conserve_curated_position_records BEFORE INSERT OR UPDATE OR DELETE ON player_events
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_position_records();
CREATE TRIGGER conserve_curated_position_records BEFORE INSERT OR UPDATE OR DELETE ON player_stats
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_position_records();
CREATE TRIGGER conserve_curated_position_records BEFORE INSERT OR UPDATE OR DELETE ON player_event_scores
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_position_records();

CREATE FUNCTION validate_curated_season_aggregate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_total NUMERIC; expected_matches INTEGER; expected_breakdown JSONB;
BEGIN
 IF TG_OP='DELETE' THEN
   IF EXISTS(SELECT 1 FROM player_position_assignments a JOIN position_correction_batches b
        ON b.batch_id=a.publication_batch_id AND b.status='published'
      WHERE a.player_id=OLD.player_id AND a.season=OLD.season AND a.status='accepted'
        AND (b.manifest->>'rules_version_id')::INTEGER=OLD.rules_version_id) THEN
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
        AND (b.manifest->>'rules_version_id')::INTEGER=OLD.rules_version_id) THEN
   PERFORM record_position_dependency_update(OLD.player_id,NULL,TG_TABLE_NAME,'MOVED_ROLLUP',to_jsonb(NEW));
   RETURN OLD;
 END IF;
 IF EXISTS(SELECT 1 FROM player_position_assignments a JOIN position_correction_batches b
       ON b.batch_id=a.publication_batch_id AND b.status='published'
     WHERE a.player_id=NEW.player_id AND a.season=NEW.season AND a.status='accepted'
       AND (b.manifest->>'rules_version_id')::INTEGER=NEW.rules_version_id
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
CREATE TRIGGER validate_curated_season_aggregate BEFORE INSERT OR UPDATE OR DELETE ON sfa_season_scores
 FOR EACH ROW EXECUTE FUNCTION validate_curated_season_aggregate();

CREATE FUNCTION conserve_curated_scoring_dependencies() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE incoming JSONB; target RECORD; matching_fixture INTEGER;
BEGIN
 IF current_setting('sfa.position_publication',true)='on' THEN
   IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 incoming:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 IF TG_OP='UPDATE' AND to_jsonb(OLD)=incoming THEN RETURN OLD; END IF;
 FOR target IN SELECT DISTINCT a.player_id,a.applicable_fixture_ids,b.manifest
   FROM player_position_assignments a JOIN position_correction_batches b
     ON b.batch_id=a.publication_batch_id AND b.status='published'
   WHERE a.status='accepted' AND a.applicable_fixture_ids IS NOT NULL LOOP
   matching_fixture:=NULL;
   IF TG_TABLE_NAME='fixture_team_strengths' AND ((incoming->>'fixture_id')::INTEGER=ANY(target.applicable_fixture_ids)
       OR (TG_OP='UPDATE' AND (to_jsonb(OLD)->>'fixture_id')::INTEGER=ANY(target.applicable_fixture_ids))) THEN
     matching_fixture:=(incoming->>'fixture_id')::INTEGER;
   ELSIF TG_TABLE_NAME='fixtures' AND ((incoming->>'id')::INTEGER=ANY(target.applicable_fixture_ids)
       OR (TG_OP='UPDATE' AND (to_jsonb(OLD)->>'id')::INTEGER=ANY(target.applicable_fixture_ids))) THEN
     IF TG_OP='UPDATE' AND (to_jsonb(OLD)-ARRAY['status','played_at','season','competition_id','home_team_id',
                  'away_team_id','stage']) IS DISTINCT FROM (incoming-ARRAY['status','played_at','season',
                  'competition_id','home_team_id','away_team_id','stage']) THEN
       -- Non-scoring fixture updates are permitted only if its scoring context stays identical.
       IF (SELECT jsonb_object_agg(k,incoming->k) FROM unnest(ARRAY['status','played_at','season','competition_id',
             'home_team_id','away_team_id','stage']) k) =
          (SELECT jsonb_object_agg(k,to_jsonb(OLD)->k) FROM unnest(ARRAY['status','played_at','season','competition_id',
             'home_team_id','away_team_id','stage']) k) THEN RETURN NEW; END IF;
     END IF;
     matching_fixture:=(incoming->>'id')::INTEGER;
   ELSIF TG_TABLE_NAME='scoring_rules_versions' AND ((incoming->>'id')::INTEGER=
       (target.manifest->>'rules_version_id')::INTEGER OR (TG_OP='UPDATE' AND (to_jsonb(OLD)->>'id')::INTEGER=
       (target.manifest->>'rules_version_id')::INTEGER)) THEN
     IF TG_OP='UPDATE' AND incoming->'config_json'=to_jsonb(OLD)->'config_json' THEN RETURN NEW; END IF;
   ELSIF TG_TABLE_NAME='players' AND ((incoming->>'id')::INTEGER=target.player_id
       OR (TG_OP='UPDATE' AND (to_jsonb(OLD)->>'id')::INTEGER=target.player_id)) THEN
     IF TG_OP='UPDATE' AND incoming->'birth_date' IS NOT DISTINCT FROM to_jsonb(OLD)->'birth_date'
         AND incoming->'id'=to_jsonb(OLD)->'id' THEN RETURN NEW; END IF;
   ELSIF TG_TABLE_NAME='competition_stages' AND EXISTS(SELECT 1 FROM fixtures f
        WHERE f.id=ANY(target.applicable_fixture_ids) AND
        ((f.competition_id=(incoming->>'competition_id')::INTEGER AND f.stage=incoming->>'stage')
          OR (TG_OP='UPDATE' AND f.competition_id=(to_jsonb(OLD)->>'competition_id')::INTEGER
                            AND f.stage=to_jsonb(OLD)->>'stage'))) THEN
     IF TG_OP='UPDATE' AND incoming->'stage_factor' IS NOT DISTINCT FROM to_jsonb(OLD)->'stage_factor'
         AND incoming->'competition_id'=to_jsonb(OLD)->'competition_id'
         AND incoming->'stage'=to_jsonb(OLD)->'stage' THEN RETURN NEW; END IF;
   ELSE CONTINUE;
   END IF;
   PERFORM record_position_dependency_update(target.player_id,matching_fixture,TG_TABLE_NAME,TG_OP,incoming);
   IF TG_OP='UPDATE' THEN RETURN OLD; ELSE RETURN NULL; END IF;
 END LOOP;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER conserve_curated_scoring_dependencies BEFORE INSERT OR UPDATE OR DELETE ON fixture_team_strengths
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_scoring_dependencies();
CREATE TRIGGER conserve_curated_scoring_dependencies BEFORE UPDATE OR DELETE ON fixtures
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_scoring_dependencies();
CREATE TRIGGER conserve_curated_scoring_dependencies BEFORE UPDATE OR DELETE ON scoring_rules_versions
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_scoring_dependencies();
CREATE TRIGGER conserve_curated_scoring_dependencies BEFORE UPDATE OR DELETE ON players
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_scoring_dependencies();
CREATE TRIGGER conserve_curated_scoring_dependencies BEFORE INSERT OR UPDATE OR DELETE ON competition_stages
 FOR EACH ROW EXECUTE FUNCTION conserve_curated_scoring_dependencies();

CREATE FUNCTION deny_curated_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM position_correction_batches WHERE status='published') THEN
   RAISE EXCEPTION 'TRUNCATE is forbidden while a curated correction is published';
 END IF;
 RETURN NULL;
END $$;
DO $$ DECLARE item RECORD; BEGIN
 FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
   EXECUTE format('DROP TRIGGER IF EXISTS deny_curated_truncate ON %I',item.tablename);
   EXECUTE format('CREATE TRIGGER deny_curated_truncate BEFORE TRUNCATE ON %I '
                  'FOR EACH STATEMENT EXECUTE FUNCTION deny_curated_truncate()',item.tablename);
 END LOOP;
END $$;
COMMIT;
