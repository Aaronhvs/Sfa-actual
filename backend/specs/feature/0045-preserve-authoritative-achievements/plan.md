# Plan: Preservacion de palmares autoritativo

## Archivos a crear

- [x] `src/sfa/domain/scoring/achievement_categories.py` - mapa canonico de categorias y fases singulares.
- [x] `specs/feature/0045-preserve-authoritative-achievements/decisions.md` - decisiones arquitectonicas.
- [x] `specs/feature/0045-preserve-authoritative-achievements/plan.md` - contrato de implementacion.

## Archivos a modificar

- [x] `src/sfa/application/use_cases/infer_competition_achievements.py` - preservar terminales autoritativos.
- [x] `src/sfa/application/use_cases/register_competition_achievement.py` - resolver puntos por categoria y reemplazar fases singulares.
- [x] `tests/use_cases/test_infer_competition_achievements.py` - cubrir preservacion y descarte de logros ajenos a la final.
- [x] `tests/use_cases/test_register_competition_achievement.py` - cubrir runner-up europeo sin puntos y reemplazo singular.

## Checklist de implementacion

- [x] Ejecutar la suite backend antes de editar y registrar el baseline de 471 pruebas.
- [x] Extraer `COMPETITION_CATEGORY_MAP` a dominio e incluir ligas domesticas conocidas.
- [x] Definir las fases singulares `winner`, `runner_up` y `champion`.
- [x] Resolver el bonus exclusivamente desde la categoria de la competicion.
- [x] Permitir fases terminales estructurales con bonus cero cuando no esten puntuadas.
- [x] Usar reemplazo de fase para resultados singulares y upsert para fases multiples.
- [x] Recuperar logros terminales existentes antes de limpiar una copa con final indeterminada.
- [x] Preservar solamente logros cuyos equipos sean finalistas.
- [x] Verificar que una final inferible siga reemplazando cualquier dato manual anterior.
- [x] Agregar pruebas con fakes, sin MagicMock.
- [x] Ejecutar las pruebas enfocadas.
- [x] Ejecutar la suite backend completa.
- [x] Verificar `flake8`, `isort --check-only` y `git diff --check`.

## Agent Routing Brief

**DDD Designer needed:** no

No se crean entidades, value objects ni invariantes nuevas de scoring. El cambio corrige la
orquestacion de entidades `CompetitionAchievement` existentes y centraliza constantes de categoria.

## Verificacion

1. Registrar PSG como `winner` y Arsenal como `runner_up` de Champions 2025.
2. Registrar PSG y Arsenal como `champion` de sus ligas 2025.
3. Ejecutar el recalculo `season-2025` con inferencia habilitada.
4. Confirmar que los cuatro logros permanecen y que Champions runner-up tiene bonus cero.
5. Confirmar que los jugadores participantes muestran los logros en su palmares.
