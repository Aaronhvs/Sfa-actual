-- Tune pass-control scoring for the active impact model.
-- API-Football exposes pass accuracy as a percentage; completed passes are
-- derived at scoring time as passes_total * passes_accuracy / 100.

UPDATE scoring_rules_versions
SET config_json = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                config_json,
                                '{base_points,DEL,pass_accuracy_bonus}',
                                '0'::jsonb,
                                true
                            ),
                            '{base_points,EXT,pass_accuracy_bonus}',
                            '0'::jsonb,
                            true
                        ),
                        '{base_points,LAT,passes_completed}',
                        '2'::jsonb,
                        true
                    ),
                    '{base_points,DC,passes_completed}',
                    '2'::jsonb,
                    true
                ),
                '{base_points,MCO,pass_accuracy_bonus}',
                '1'::jsonb,
                true
            ),
            '{base_points,MF,pass_accuracy_bonus}',
            '1'::jsonb,
            true
        ),
        '{base_points,LAT,pass_accuracy_bonus}',
        '1'::jsonb,
        true
    ),
    '{base_points,DC,pass_accuracy_bonus}',
    '1'::jsonb,
    true
)
WHERE config_json ? 'base_points'
  AND (
      config_json->'base_points' ? 'LAT'
      OR config_json->'base_points' ? 'DC'
  );
