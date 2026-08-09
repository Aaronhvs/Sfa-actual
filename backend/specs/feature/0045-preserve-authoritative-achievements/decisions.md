# Preservacion de palmares autoritativo

## Contexto de negocio

Los resultados terminales de la Champions League 2025 no pueden inferirse desde los eventos
disponibles porque la final no contiene goles ni penales utilizables. El motor registra las fases
previas, pero actualmente borra tambien los logros manuales `winner` y `runner_up` aunque el log
indique que seran preservados. Como consecuencia, los jugadores de PSG y Arsenal pierden su
palmares europeo en cada recalculo.

El registro manual tambien busca una fase en todas las categorias. Para `runner_up` de Champions
puede tomar por error los puntos del Mundial, aunque la configuracion vigente establece que el
subcampeonato europeo debe mostrarse con cero puntos adicionales.

## Restricciones

- Se mantiene Router -> Use Case -> Port -> Repository.
- No se agregan endpoints, tablas ni migraciones.
- La rules version sigue siendo la unica fuente de puntos y pesos.
- Un resultado manual solo se preserva si pertenece a uno de los dos equipos de la final.
- `winner`, `runner_up` y `champion` son fases singulares por competicion y temporada.
- Las fases alcanzadas con multiples equipos, como `semi_final` y `top_4`, conservan el upsert
  normal por equipo.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Mover el mapa competicion-categoria a un modulo de dominio compartido | Importar constantes entre use cases | Evita dependencia lateral entre casos de uso y elimina resoluciones inconsistentes. |
| Resolver el bonus manual solo dentro de la categoria de la competicion | Buscar la fase en todas las categorias | Impide asignar puntos del Mundial a un subcampeon de Champions. |
| Permitir `runner_up` estructural con bonus cero en Champions | Agregar puntos nuevos a la rules version | El producto necesita mostrar el palmares, no cambiar el balance vigente. |
| Rehidratar `winner` y `runner_up` existentes cuando la final es indeterminada | Omitirlos y borrar toda la competicion | Cumple la promesa de preservar resultados autoritativos y permite recalculos idempotentes. |
| Reemplazar la fase para resultados singulares | Upsert por equipo | Evita dos campeones o dos subcampeones para la misma competicion y temporada. |

## Domain Model

No se agregan entidades. Se incorporan constantes y una funcion pura de resolucion de categoria
en `domain/scoring/achievement_categories.py`.

## Flujo

1. El administrador registra los resultados autoritativos con el endpoint existente.
2. El caso de uso resuelve categoria, puntos y peso desde la rules version.
3. Para una fase singular, el repositorio reemplaza cualquier equipo anterior de esa fase.
4. Durante el recalculo, si la final sigue indeterminada, la inferencia recupera los logros
   terminales existentes que coinciden con los finalistas.
5. La inferencia reconstruye las fases y el calculo de bonos reconstruye los detalles y totales.
6. El endpoint de jugador devuelve tanto logros con puntos como el subcampeonato con bonus cero.

## Integraciones externas

Ninguna nueva. El resultado autoritativo se ingresa por el endpoint de scoring existente.
