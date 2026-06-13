-- Migration 0014: Add missing competition_stages for existing cups
-- and insert 8 new competitions with their stages.

-- 1. competition_stages para copas existentes sin stages
INSERT INTO competition_stages (competition_id, stage, stage_factor) VALUES
-- FA Cup (90) — no hay round_of_16 en sus fixtures
(90, 'regular', 0.90),
(90, 'quarter', 1.10),
(90, 'semi',    1.20),
(90, 'final',   1.40),
-- DFB-Pokal (92)
(92, 'regular',     0.90),
(92, 'round_of_16', 1.00),
(92, 'quarter',     1.10),
(92, 'semi',        1.20),
(92, 'final',       1.40),
-- Coppa Italia (94)
(94, 'regular',     0.90),
(94, 'round_of_16', 1.00),
(94, 'quarter',     1.10),
(94, 'semi',        1.20),
(94, 'final',       1.40),
-- Coupe de France (96)
(96, 'regular',     0.90),
(96, 'round_of_16', 1.00),
(96, 'quarter',     1.10),
(96, 'semi',        1.20),
(96, 'final',       1.40)
ON CONFLICT DO NOTHING;

-- 2. Las 8 nuevas competiciones
INSERT INTO competitions (name, country, competition_factor) VALUES
('Europa League',          'EUR', 1.30),
('Conference League',      'EUR', 1.10),
('UEFA Super Cup',         'EUR', 1.05),
('EFL Cup',               'ENG', 0.85),
('Community Shield',      'ENG', 0.75),
('DFL-Supercup',          'GER', 0.85),
('Supercoppa Italiana',   'ITA', 0.85),
('Trophée des Champions', 'FRA', 0.80)
ON CONFLICT (name) DO NOTHING;

-- 3. competition_stages para las 8 nuevas
INSERT INTO competition_stages (competition_id, stage, stage_factor)
SELECT c.id, v.stage, v.factor
FROM competitions c
JOIN (VALUES
  -- Europa League (formato UEFA: group + knockout)
  ('Europa League', 'group',       1.30::numeric),
  ('Europa League', 'regular',     1.30::numeric),
  ('Europa League', 'round_of_16', 1.50::numeric),
  ('Europa League', 'quarter',     1.70::numeric),
  ('Europa League', 'semi',        2.00::numeric),
  ('Europa League', 'final',       2.40::numeric),
  -- Conference League
  ('Conference League', 'group',       1.10::numeric),
  ('Conference League', 'regular',     1.10::numeric),
  ('Conference League', 'round_of_16', 1.25::numeric),
  ('Conference League', 'quarter',     1.40::numeric),
  ('Conference League', 'semi',        1.60::numeric),
  ('Conference League', 'final',       2.00::numeric),
  -- UEFA Super Cup (partido único entre campeón CL y UEL)
  ('UEFA Super Cup', 'final', 2.00::numeric),
  -- EFL Cup / Carabao Cup
  ('EFL Cup', 'regular',     0.80::numeric),
  ('EFL Cup', 'round_of_16', 0.90::numeric),
  ('EFL Cup', 'quarter',     1.00::numeric),
  ('EFL Cup', 'semi',        1.10::numeric),
  ('EFL Cup', 'final',       1.30::numeric),
  -- Community Shield (partido único)
  ('Community Shield', 'final', 1.00::numeric),
  -- DFL-Supercup (partido único)
  ('DFL-Supercup', 'final', 1.10::numeric),
  -- Supercoppa Italiana (puede tener semifinal)
  ('Supercoppa Italiana', 'semi',  1.10::numeric),
  ('Supercoppa Italiana', 'final', 1.30::numeric),
  -- Trophée des Champions (partido único)
  ('Trophée des Champions', 'final', 1.00::numeric)
) AS v(comp_name, stage, factor) ON c.name = v.comp_name
ON CONFLICT DO NOTHING;

-- Verificación
SELECT c.name, c.competition_factor, COUNT(cs.stage) AS stages
FROM competitions c
LEFT JOIN competition_stages cs ON cs.competition_id = c.id
GROUP BY c.id, c.name, c.competition_factor
ORDER BY c.country, c.name;
