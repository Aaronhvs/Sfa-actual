import { useEffect } from 'react'
import type { CSSProperties } from 'react'

const CONCEPTOS = [
  {
    num: '01',
    titulo: 'El contexto importa',
    descripcion: 'Un gol contra el líder en el minuto 89 vale más que un gol en un partido sin trascendencia. El SFA lo captura.',
  },
  {
    num: '02',
    titulo: 'Cada posición tiene su metro',
    descripcion: 'Un lateral que genera juego puntúa diferente a un delantero. Los roles no son intercambiables.',
  },
  {
    num: '03',
    titulo: 'Los logros colectivos cuentan',
    descripcion: 'Ganar la Champions o tu liga suma puntos extra proporcionales a tu participación en el éxito del equipo.',
  },
]

const MULTIPLICADORES = [
  {
    id: 'M1',
    color: 'var(--met-blue)',
    nombre: 'Fuerza del Rival',
    rango: '0.6× - 1.8×',
    descripcion: 'Cuanto más fuerte el equipo contrario, más valen tus acciones. Un gol contra el líder de la Premier League puntúa casi el triple que contra el colista.',
    detalle: 'Se calcula a partir del ELO del equipo rival, ajustado por la fortaleza de su liga. El límite [0.6, 1.8] evita que equipos irrelevantes o dominantes distorsionen el ranking.',
    ejemplo: { bajo: 'vs equipo débil → ×0.6', alto: 'vs líder Champions → ×1.8' },
  },
  {
    id: 'M2',
    color: 'var(--met-green)',
    nombre: 'Fase de Competición',
    rango: '1.0× - 1.5×',
    descripcion: 'Una semifinal de Champions vale más que la fase de grupos. A mayor trascendencia del partido, mayor multiplicador.',
    detalle: 'La fase del torneo determina M2: fase de grupos = 1.0, octavos = 1.1, cuartos = 1.2, semifinal = 1.35, final = 1.5. En liga, los partidos directos por el título aplican un bonus.',
    ejemplo: { bajo: 'Fase de grupos → ×1.0', alto: 'Final Champions → ×1.5' },
  },
  {
    id: 'M3',
    color: 'var(--met-orange)',
    nombre: 'Momento del Partido',
    rango: 'variable',
    descripcion: 'Un gol en el minuto 89 que da la vuelta al marcador vale mucho más que un gol en el 10 cuando ya ganabas 3-0. El SFA captura la tensión del momento.',
    detalle: 'M3 combina el minuto del partido con la diferencia de goles en ese instante. Acciones en empate o desventaja, en los últimos 20 minutos, reciben el mayor bonus.',
    ejemplo: { bajo: 'Gol min 10, ganando 3-0 → bajo', alto: 'Gol min 89, perdiendo → máximo' },
  },
  {
    id: 'M4',
    color: 'var(--met-violet)',
    nombre: 'Dificultad del Disparo',
    rango: '0.8× - 1.2×',
    descripcion: 'No es lo mismo rematar solo frente al portero que marcar desde 35 metros en ángulo imposible. El xG mide la probabilidad real del disparo.',
    detalle: 'Basado en el Expected Goals (xG) de la acción. Un disparo con xG bajo que acaba en gol recibe bonus M4 alto. Solo aplica a goles, no a asistencias ni otras acciones.',
    ejemplo: { bajo: 'Penalti (xG≈0.76) → ×0.8', alto: 'Tiro difícil (xG<0.1) → ×1.2' },
  },
  {
    id: 'Mv',
    color: 'var(--met-yellow)',
    nombre: 'Bonus Visitante',
    rango: '×1.15 fuera de casa',
    descripcion: 'Jugar fuera de casa es más difícil. Las acciones clave se multiplican por 1.15 cuando el jugador compite de visitante.',
    detalle: 'Solo aplica a las acciones más decisivas: gol, asistencia, córner asistido, penalti y tanda de penaltis. Pases o tackles no reciben este bonus.',
    ejemplo: { bajo: 'En casa → ×1.0', alto: 'De visitante → ×1.15' },
  },
]

const POSICIONES = [
  { pos: 'DEL', nombre: 'Delantero', color: 'var(--met-red)', top: ['Gol (650 pts)', 'Penal (390 pts)', 'Asistencia (500 pts)'] },
  { pos: 'EXT', nombre: 'Extremo', color: 'var(--met-orange)', top: ['Regate ganado (110 pts)', 'Gol (550 pts)', 'Falta recibida (60 pts)'] },
  { pos: 'MCO', nombre: 'MC Ofensivo', color: 'var(--met-violet)', top: ['Gol (600 pts)', 'Asistencia (520 pts)', 'xG sin gol (70 pts)'] },
  { pos: 'MC', nombre: 'Mediocampista', color: 'var(--met-green)', top: ['Pases completados (7 pts/c)', 'Gol (720 pts)', 'Recuperación (95 pts)'] },
  { pos: 'LAT', nombre: 'Lateral', color: 'var(--met-blue)', top: ['Gol (850 pts)', 'Asistencia (620 pts)', 'Córner asistido (300 pts)'] },
  { pos: 'DC', nombre: 'Def. Central', color: 'var(--text-dim)', top: ['Gol (1000 pts)', 'Bloqueo (180 pts)', 'Intercepción (160 pts)'] },
]

const LOGROS = [
  { comp: 'Champions League', fase: 'Campeón', pts: 18000, weight: 1, color: 'var(--met-yellow)', grupo: 'internacional' },
  { comp: 'Champions League', fase: 'Semifinal', pts: 9000, weight: 1, color: 'var(--met-yellow)', grupo: 'internacional' },
  { comp: 'Champions League', fase: 'Cuartos', pts: 5500, weight: 1, color: 'var(--met-yellow)', grupo: 'internacional' },
  { comp: 'Europa League', fase: 'Campeón', pts: 7000, weight: 0.75, color: 'var(--met-orange)', grupo: 'internacional' },
  { comp: 'Liga doméstica', fase: 'Campeón', pts: 14000, weight: 0.95, color: 'var(--met-blue)', grupo: 'domestico' },
  { comp: 'Liga doméstica', fase: 'Subcampeón', pts: 5000, weight: 0.95, color: 'var(--met-blue)', grupo: 'domestico' },
  { comp: 'Liga doméstica', fase: 'Top 4', pts: 2000, weight: 0.95, color: 'var(--met-blue)', grupo: 'domestico' },
  { comp: 'Copa Nacional', fase: 'Campeón', pts: 6000, weight: 0.65, color: 'var(--met-green)', grupo: 'domestico' },
]

const EJEMPLO_FILAS = [
  { concepto: 'Base (EXT · Gol)', valor: '550 pts' },
  { concepto: 'M1 rival fuerte (Bayern, 82 pts)', valor: '× 1.80' },
  { concepto: 'M2 semifinal Champions', valor: '× 1.35' },
  { concepto: 'M3 minuto 78, empate a 1', valor: '× 1.42', nota: 'estimado' },
  { concepto: 'M4 xG bajo (remate difícil 0.08)', valor: '× 1.15' },
  { concepto: 'Mv (partido de visitante)', valor: '× 1.15' },
]

const B1_FILAS = [
  { contribuciones: '1 gol o asistencia', bono: '+200 pts' },
  { contribuciones: '2 goles/asistencias', bono: '+400 pts' },
  { contribuciones: '3+ goles/asistencias', bono: '+600 pts' },
]

function LogroColumn({ titulo, grupo }: { titulo: string; grupo: string }) {
  return (
    <div className="met-logro__column">
      <h3 className="met-logro__column-title">{titulo}</h3>
      <div className="met-logro__list">
        {LOGROS.filter((logro) => logro.grupo === grupo).map((logro) => (
          <div
            key={`${logro.comp}-${logro.fase}`}
            className="met-logro__row"
            style={{ '--logro-color': logro.color } as CSSProperties}
          >
            <div className="met-logro__meta">
              <div>
                <strong>{logro.comp}</strong>
                <span>{logro.fase}</span>
              </div>
              <b>{logro.pts.toLocaleString('es-ES')} pts</b>
            </div>
            <div className="met-logro__track" aria-hidden="true">
              <span style={{ width: `${(logro.pts / 18000) * 100 * logro.weight}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function MetodologiaPage() {
  useEffect(() => {
    const items = document.querySelectorAll('.met-concepto__card, .met-mult__item, .met-logro__row, .met-b1__row')
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('--visible')
          observer.unobserve(entry.target)
        }
      }),
      { threshold: 0.15 },
    )

    items.forEach((item) => observer.observe(item))
    return () => observer.disconnect()
  }, [])

  return (
    <div className="met-page">
      <section className="met-hero">
        <div className="met-hero__inner">
          <span className="met-hero__eyebrow">Sistema de Puntuación</span>
          <h1 className="met-hero__title">
            <span className="met-hero__title-line">No todos</span>
            <span className="met-hero__title-line met-hero__title-line--gold">los goles</span>
            <span className="met-hero__title-line">valen igual.</span>
          </h1>
          <p className="met-hero__sub">
            <span className="met-hero__sub-line">El SFA mide el impacto real de cada acción:</span>{' '}
            <span className="met-hero__sub-line">contra quién, en qué momento,</span>{' '}
            <span className="met-hero__sub-line">en qué competición y qué tan difícil fue.</span>
          </p>
          <div className="met-hero__scroll-hint">
            <span>Descubrir cómo</span>
            <div className="met-hero__scroll-arrow" />
          </div>
        </div>
        <img src="/blanco.png" alt="" className="met-hero__logo" aria-hidden="true" />
      </section>

      <section className="met-concepto met-section">
        <div className="met-section-header">
          <span className="met-eyebrow">La idea en 30 segundos</span>
          <h2 className="met-section-title">Medir impacto, no volumen</h2>
        </div>
        <div className="met-concepto__cards">
          {CONCEPTOS.map((concepto) => (
            <article key={concepto.num} className="met-concepto__card">
              <div className="met-concepto__num">{concepto.num}</div>
              <h3>{concepto.titulo}</h3>
              <p>{concepto.descripcion}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="met-formula">
        <div className="met-section">
          <div className="met-section-header">
            <span className="met-eyebrow">La matemática detrás</span>
            <h2 className="met-section-title">La Fórmula</h2>
          </div>
          <div className="met-formula__display" aria-label="Puntos SFA igual a la suma de puntos base por cinco multiplicadores">
            <span className="met-formula__pts">SFA pts</span>
            <span className="met-formula__eq">=</span>
            <span className="met-formula__sigma">Σ</span>
            <div className="met-formula__factors">
              <span className="met-formula__factor met-formula__factor--base">base</span>
              <span className="met-formula__op">×</span>
              <span className="met-formula__factor met-formula__factor--m1">M1</span>
              <span className="met-formula__op">×</span>
              <span className="met-formula__factor met-formula__factor--m2">M2</span>
              <span className="met-formula__op">×</span>
              <span className="met-formula__factor met-formula__factor--m3">M3</span>
              <span className="met-formula__op">×</span>
              <span className="met-formula__factor met-formula__factor--m4">M4</span>
              <span className="met-formula__op">×</span>
              <span className="met-formula__factor met-formula__factor--mv">Mv</span>
            </div>
          </div>
          <div className="met-formula__legend">
            <div className="met-formula__pill met-formula__pill--base"><strong>base</strong>Puntos base según posición y acción</div>
            <div className="met-formula__pill met-formula__pill--m1"><strong>M1</strong>Fuerza del rival (0.6 - 1.8×)</div>
            <div className="met-formula__pill met-formula__pill--m2"><strong>M2</strong>Fase de la competición (1.0 - 1.5×)</div>
            <div className="met-formula__pill met-formula__pill--m3"><strong>M3</strong>Momento del partido (minuto + marcador)</div>
            <div className="met-formula__pill met-formula__pill--m4"><strong>M4</strong>Dificultad del disparo (xG)</div>
            <div className="met-formula__pill met-formula__pill--mv"><strong>Mv</strong>Bonus visitante (1.15× fuera de casa)</div>
          </div>
        </div>
      </section>

      <section className="met-b1 met-section">
        <div className="met-section-header">
          <span className="met-eyebrow">Beta Mundial 2026</span>
          <h2 className="met-section-title">B1 - Edad excepcional</h2>
        </div>
        <div className="met-b1__grid">
          <div className="met-b1__panel">
            <span className="met-b1__tag">Solo Mundial</span>
            <p>
              B1 reconoce partidos de alto impacto cuando el jugador esta en un
              rango de edad especialmente exigente: promesas de 17 a 20 años o
              veteranos de 35 años en adelante.
            </p>
            <p>
              El bono aplica solo sobre contribuciones directas de gol:
              goles y asistencias. No modifica pases, duelos, tiros ni acciones
              defensivas.
            </p>
          </div>
          <div className="met-b1__rows" aria-label="Tabla de bono B1">
            {B1_FILAS.map((fila) => (
              <div key={fila.contribuciones} className="met-b1__row">
                <span>{fila.contribuciones}</span>
                <strong>{fila.bono}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="met-multiplicadores met-section">
        <div className="met-section-header">
          <span className="met-eyebrow">Cinco capas de contexto</span>
          <h2 className="met-section-title">Los multiplicadores</h2>
        </div>
        <div className="met-mult__list">
          {MULTIPLICADORES.map((mult) => (
            <article
              key={mult.id}
              className="met-mult__item"
              style={{ '--mult-color': mult.color } as CSSProperties}
            >
              <div className="met-mult__id">{mult.id}</div>
              <div className="met-mult__body">
                <div className="met-mult__header">
                  <h3 className="met-mult__nombre">{mult.nombre}</h3>
                  <span className="met-mult__rango">{mult.rango}</span>
                </div>
                <p className="met-mult__desc">{mult.descripcion}</p>
                <p className="met-mult__detalle">{mult.detalle}</p>
                <div className="met-mult__ejemplos">
                  <span className="met-mult__ej met-mult__ej--bajo">{mult.ejemplo.bajo}</span>
                  <span className="met-mult__ej met-mult__ej--alto">{mult.ejemplo.alto}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="met-posiciones">
        <div className="met-section">
          <div className="met-section-header">
            <span className="met-eyebrow">El valor depende del rol</span>
            <h2 className="met-section-title">Cada posición, su propia vara</h2>
          </div>
          <div className="met-posiciones__grid">
            {POSICIONES.map((posicion) => (
              <article
                key={posicion.pos}
                className="met-posicion"
                style={{ '--pos-color': posicion.color } as CSSProperties}
              >
                <div className="met-posicion__header">
                  <strong>{posicion.pos}</strong>
                  <span>{posicion.nombre}</span>
                </div>
                <ol className="met-posicion__actions">
                  {posicion.top.map((accion, index) => (
                    <li key={accion}>
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      {accion}
                    </li>
                  ))}
                </ol>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="met-logros met-section">
        <div className="met-section-header">
          <span className="met-eyebrow">El éxito colectivo también cuenta</span>
          <h2 className="met-section-title">Logros de temporada</h2>
        </div>
        <div className="met-logros__columns">
          <LogroColumn titulo="Competición internacional" grupo="internacional" />
          <LogroColumn titulo="Liga doméstica y copa" grupo="domestico" />
        </div>
        <p className="met-logros__note">
          Los puntos de logro se distribuyen según tu participación real en la temporada. Un jugador que jugó el 80% de los minutos recibe más bonus que uno que jugó el 20%. Los mejores del equipo en rendimiento reciben un multiplicador adicional.
        </p>
      </section>

      <section className="met-ejemplo">
        <div className="met-section">
          <div className="met-section-header">
            <span className="met-eyebrow">Del dato al puntaje</span>
            <h2 className="met-section-title">Un gol, paso a paso</h2>
          </div>
          <div className="met-ejemplo__box">
            <div className="met-ejemplo__heading">
              <span>Ejemplo</span>
              <h3>Gol de Lamine Yamal en semifinal de Champions</h3>
            </div>
            <div className="met-ejemplo__rows">
              {EJEMPLO_FILAS.map((fila, index) => (
                <div key={fila.concepto} className="met-ejemplo__row">
                  <span className="met-ejemplo__step">{String(index + 1).padStart(2, '0')}</span>
                  <span className="met-ejemplo__concept">{fila.concepto}</span>
                  <strong>{fila.valor}</strong>
                  {fila.nota && <small>{fila.nota}</small>}
                </div>
              ))}
            </div>
            <div className="met-ejemplo__total">
              <span>Total</span>
              <strong>≈ 3.200 pts</strong>
            </div>
            <p className="met-ejemplo__note">
              Los valores de M3 y M4 son aproximaciones con fines ilustrativos. El cálculo real usa los datos exactos del partido.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
