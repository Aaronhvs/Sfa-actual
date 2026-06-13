# scripts/

Scripts de mantenimiento para el proyecto SFA.

---

## scripts/seed_competition_stages.py

**Propósito:** Poblar la tabla `competition_stages` con los stage factors de todas las competiciones.

**Cuándo usarlo:**
- Después de ingestar una nueva competición por primera vez.
- Si se quieren ajustar los stage factors (CL, copas nacionales, etc.).

**Cómo usarlo:**
```bash
python scripts/seed_competition_stages.py
```

Usa `ON CONFLICT DO UPDATE` — es seguro re-ejecutar.

---

## scripts/legacy/

Scripts de reparación de emergencia que se ejecutaron una sola vez en mayo 2026.
**NO volver a ejecutar** — los datos ya están corregidos en producción.

Para operaciones equivalentes en el futuro, usar los endpoints admin:

| Script legacy | Equivalente correcto |
|---|---|
| `recalculate_all_scores.py` | `POST /api/v1/admin/recalculate/{competition_id}` |
| `repair_missing_goal_events.py` | Re-ingestar con `POST /api/v1/admin/ingest/{league_id}` (el bug de _name_matches ya está corregido) |
| `backfill_wikipedia_photos.py` | Pendiente: convertir en Celery task `backfill_photos_task` |

Estos scripts violaron la arquitectura hexagonal (acceso directo con psycopg2 sin pasar por Use Cases).
Se conservan solo como referencia histórica de la lógica aplicada.
