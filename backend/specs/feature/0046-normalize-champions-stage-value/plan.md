# Plan: Normalizacion del valor de las fases de Champions

## Archivos a crear

- [x] `specs/feature/0046-normalize-champions-stage-value/decisions.md` - decisiones y valores canonicos.
- [x] `specs/feature/0046-normalize-champions-stage-value/plan.md` - contrato de implementacion.
- [x] `migrations/0047_normalize_champions_stage_value.sql` - actualizacion idempotente de M2 y rules version 4.

## Archivos a modificar

- [x] `src/sfa/domain/scoring/value_objects.py` - defaults de palmares Champions.
- [x] `../scripts/seed_competition_stages.py` - factores M2 canonicos para nuevos entornos.
- [x] `../frontend/src/pages/MetodologiaPage.tsx` - explicacion publica alineada al motor.
- [x] `tests/use_cases/test_scoring_balance_v2.py` - contrato exacto de bonos.
- [x] `tests/use_cases/test_infer_competition_achievements.py` - recalculo de terminales preservados.
- [x] `tests/use_cases/test_register_competition_achievement.py` - subcampeonato puntuado.

## Checklist de implementacion

- [x] Leer `CLAUDE.md`, Architecture Engineer y la skill SFA Spec.
- [x] Ejecutar baseline backend: 476 pruebas aprobadas.
- [x] Actualizar bonos Champions incluyendo `runner_up` con 11000 puntos base.
- [x] Normalizar factores M2 de grupos a final.
- [x] Agregar migracion transaccional e idempotente para produccion.
- [x] Sincronizar la pagina de metodologia.
- [x] Actualizar pruebas de configuracion, inferencia y registro manual.
- [x] Ejecutar pruebas enfocadas: 45 aprobadas.
- [x] Ejecutar `flake8`, `isort --check-only` y `git diff --check`.
- [x] Ejecutar la suite backend completa: 476 aprobadas.
- [x] Ejecutar `npm run build` para la metodologia del frontend.
- [x] Documentar comandos de despliegue, recalculo y verificacion en VPS.

## Agent Routing Brief

**DDD Designer needed:** no

No se crean conceptos de dominio. El cambio calibra configuracion versionada y datos de
referencia existentes, dentro de los limites ya definidos por el motor.

## Verificacion en produccion

1. Confirmar los cinco factores de `competition_stages` para Champions League.
2. Confirmar los seis bonos en `scoring_rules_versions.config_json` para id 4.
3. Ejecutar el recalculo integral de `season-2025`.
4. Confirmar que PSG conserva `winner` y Arsenal `runner_up` con puntos.
5. Auditar de nuevo a Dominik Szoboszlai y el top general para comprobar el efecto combinado.
