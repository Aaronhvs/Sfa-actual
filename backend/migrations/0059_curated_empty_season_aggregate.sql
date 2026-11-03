BEGIN;

-- A published goalkeeper can legitimately have no scored actions. Updating
-- its trophy bonus must retain an empty aggregate, rather than writing NULL.
DO $migration$
DECLARE
    definition TEXT;
    marker TEXT := '   IF NEW.total_pts IS DISTINCT FROM expected_total';
    normalization TEXT := E'   -- Normalize an empty protected scoring aggregate.\n'
        || E'   expected_total := coalesce(expected_total, 0);\n'
        || E'   expected_matches := coalesce(expected_matches, 0);\n'
        || E'   expected_breakdown := coalesce(expected_breakdown, ''{}''::jsonb);\n';
BEGIN
    IF to_regprocedure('public.validate_curated_season_aggregate()') IS NULL THEN
        RETURN;
    END IF;
    SELECT pg_get_functiondef('public.validate_curated_season_aggregate()'::regprocedure)
        INTO definition;
    IF position(normalization IN definition) > 0 THEN
        RETURN;
    END IF;
    IF (length(definition) - length(replace(definition, marker, ''))) / length(marker) <> 1 THEN
        RAISE EXCEPTION 'Unexpected curated aggregate function; review before migration';
    END IF;
    EXECUTE replace(definition, marker, normalization || marker);
END
$migration$;

COMMIT;
