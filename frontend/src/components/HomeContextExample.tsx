import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { fetchPlayerEvents, fetchPlayerFixtures } from '../api/client'
import type { PlayerEvent } from '../types'
import { ArrowIcon } from './tournaments/MatchUI'
import { tournamentCompetitionLogoByName } from '../utils/tournaments'
import './HomeContextExample.css'

// Curated league-vs-Champions pairs from different matches; values come from the API.
// Dembélé is deliberately the reverse case: context, not the competition alone, sets the value.
const EXAMPLES = [
  { playerId: 888, name: 'Mbappé', team: 'Real Madrid', events: [1717549, 1936417] },
  { playerId: 8297, name: 'Haaland', team: 'Manchester City', events: [1799852, 1821651] },
  { playerId: 7571, name: 'Dembélé', team: 'Paris Saint Germain', events: [1825508, 1949453] },
] as const
type Example = typeof EXAMPLES[number]
type Logos = { home: string | null; away: string | null }
type Goal = PlayerEvent & { logos: Logos; playerIsHome: boolean }
type Case = { example: Example; goals: [Goal, Goal] }

const SCOPE = 'season-2026'
const ROTATE_MS = 7000

const points = (value: number) => Math.round(value).toLocaleString('es-ES')
const factor = (value: number) => value.toLocaleString('es-ES', { maximumFractionDigits: 2 })

async function loadCase(example: Example): Promise<Case> {
  const [available, fixtures] = await Promise.all([
    fetchPlayerEvents(example.playerId, undefined, SCOPE),
    // Crests are a nicety: the comparison still works with initials if this fails.
    fetchPlayerFixtures(example.playerId, undefined, SCOPE).catch(() => []),
  ])
  const byFixture = new Map(fixtures.map((fixture) => [fixture.fixture_id, fixture]))
  const goals = example.events.map((id) => available.find((event) => event.id === id && event.event_type === 'goal'))
  if (goals.some((event) => !event || !Number.isFinite(event.pts) || event.pts <= 0)) throw new Error('Ejemplo no disponible')
  const [a, b] = (goals as PlayerEvent[]).map((event) => {
    const fixture = byFixture.get(event.fixture_id)
    const team = fixture?.player_team ?? example.team
    return {
      ...event,
      logos: { home: fixture?.home_team_logo ?? null, away: fixture?.away_team_logo ?? null },
      playerIsHome: event.home_team === team,
    }
  })
  return { example, goals: a.pts <= b.pts ? [a, b] : [b, a] }
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return reduced
}

/** Factors that actually differ between the two goals, shown as "×a → ×b". */
function changedFactors([low, high]: [Goal, Goal]) {
  const rows: Array<[string, number, number]> = [
    ['Rival', low.m1, high.m1],
    ['Fase', low.m2, high.m2],
    ['Momento', low.m3, high.m3],
    ['Remate', low.m4, high.m4],
    ['Visita', low.mvisit, high.mvisit],
  ]
  return rows.filter(([, a, b]) => Math.abs(a - b) >= 0.01)
}

function TeamBadge({ name, logo }: { name: string; logo: string | null }) {
  return logo
    ? <img className="hce__crest" src={logo} alt={name} title={name} loading="lazy" decoding="async" />
    : <span className="hce__crest hce__crest--fallback" role="img" aria-label={name} title={name}>{name.slice(0, 3).toUpperCase()}</span>
}

/** Reads the goal from the scorer's side: how the game stood and what the goal changed. */
function goalSituation(goal: Goal) {
  const [home = 0, away = 0] = (goal.score_before ?? '0:0').split(':').map(Number)
  const own = goal.playerIsHome ? home : away
  const rival = goal.playerIsHome ? away : home
  const diff = own - rival
  const before = diff < 0 ? `Perdían ${rival}–${own}` : diff === 0 ? `Empate ${own}–${rival}` : `Ganaban ${own}–${rival}`
  const effect = diff === -1 ? 'gol del empate' : diff < -1 ? 'recorta' : diff === 0 ? 'se adelantan' : 'amplía la ventaja'
  const after = goal.playerIsHome ? [home + 1, away] : [home, away + 1]
  return { before, effect, home, away, after, tone: diff < 0 ? 'is-behind' : diff === 0 ? 'is-level' : 'is-ahead' }
}

/** The moment of the goal: competition, crests, the score it produced, minute and situation. */
function GoalContext({ goal, high }: { goal: Goal; high: boolean }) {
  const situation = goalSituation(goal)
  const logo = tournamentCompetitionLogoByName(goal.competition)
  const [homeAfter, awayAfter] = situation.after
  return (
    <div className={`hce__context${high ? ' is-high' : ''}`}>
      <span className="hce__competition">
        {logo && <span className="tp-tile"><img src={logo} alt="" loading="lazy" /></span>}
        {goal.competition}
      </span>
      <span className="hce__scoreboard" aria-label={`${goal.home_team} ${homeAfter} – ${awayAfter} ${goal.away_team} tras el gol, minuto ${goal.minute}`}>
        <TeamBadge name={goal.home_team} logo={goal.logos.home} />
        <strong>
          <span className={goal.playerIsHome ? 'is-goal' : undefined}>{homeAfter}</span>
          <i aria-hidden="true">–</i>
          <span className={goal.playerIsHome ? undefined : 'is-goal'}>{awayAfter}</span>
        </strong>
        <TeamBadge name={goal.away_team} logo={goal.logos.away} />
      </span>
      <span className="hce__minute">Gol en el <b>{goal.minute}'</b></span>
      <span className={`hce__situation ${situation.tone}`}>{situation.before} · {situation.effect}</span>
    </div>
  )
}

export default function HomeContextExample() {
  const [cases, setCases] = useState<Case[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [selected, setSelected] = useState(0)
  const [paused, setPaused] = useState(false)
  const [cycle, setCycle] = useState(0)
  const [retry, setRetry] = useState(0)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    void Promise.allSettled(EXAMPLES.map(loadCase)).then((results) => {
      if (cancelled) return
      const ready = results.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : []))
      setCases(ready)
      setSelected(0)
      setStatus(ready.length ? 'ready' : 'error')
    })
    return () => { cancelled = true }
  }, [retry])

  const rotating = status === 'ready' && cases.length > 1 && !paused && !reducedMotion

  useEffect(() => {
    if (!rotating) return undefined
    const timer = window.setTimeout(() => setSelected((current) => (current + 1) % cases.length), ROTATE_MS)
    return () => window.clearTimeout(timer)
  }, [rotating, selected, cycle, cases.length])

  const choose = (index: number) => {
    setSelected(index)
    setCycle((value) => value + 1)
  }

  const current = cases[selected]
  const [low, high] = current?.goals ?? []
  const max = current ? Math.max(low.pts, high.pts) : 1
  const increase = current ? Math.round((high.pts / low.pts - 1) * 100) : 0

  return (
    <figure
      className="hce"
      aria-labelledby="hce-title"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false) }}
    >
      <figcaption className="hce__head">
        <span className="tp-eyebrow">Casos reales</span>
        <strong id="hce-title">Mismo jugador, otro contexto</strong>
      </figcaption>

      {status === 'ready' && cases.length > 1 && (
        <div className="hce__tabs" role="group" aria-label="Elegir jugador del ejemplo">
          {cases.map(({ example }, index) => (
            <button
              key={example.playerId}
              type="button"
              aria-pressed={selected === index}
              className={selected === index ? 'is-active' : undefined}
              onClick={() => choose(index)}
            >
              {example.name}
              {selected === index && (
                <span
                  key={`${selected}-${cycle}`}
                  className={`hce__progress${rotating ? ' is-running' : ''}`}
                  style={{ '--duration': `${ROTATE_MS}ms` } as CSSProperties}
                  aria-hidden="true"
                />
              )}
            </button>
          ))}
        </div>
      )}

      <div className="hce__body" aria-live="polite" aria-busy={status === 'loading'}>
        {status === 'loading' && <div className="hce__skeleton" role="status"><span className="sr-only">Cargando goles registrados en SFA</span></div>}

        {status === 'error' && (
          <div className="hce__error">
            <p>No pudimos cargar los ejemplos.</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>Reintentar</button>
          </div>
        )}

        {current && (
          <div className="hce__case" key={current.example.playerId}>
            <p className="hce__lead">Dos goles de <b>{current.example.name}</b> en partidos distintos. ¿Cuál vale más?</p>

            <div className="hce__pair">
              <GoalContext goal={low} high={false} />
              <span className="hce__vs" aria-hidden="true">vs</span>
              <GoalContext goal={high} high />
            </div>

            <div className="hce__chart" role="img" aria-label={`Gol en el minuto ${low.minute}: ${points(low.pts)} puntos SFA. Gol en el minuto ${high.minute}: ${points(high.pts)} puntos SFA, un ${increase} % más.`}>
              {[low, high].map((goal, index) => (
                <div className={`hce__col${index === 1 ? ' is-high' : ''}`} key={goal.id}>
                  <span className="hce__track" style={{ '--h': goal.pts / max } as CSSProperties}>
                    <span className="hce__bar" />
                    <strong>{points(goal.pts)}<small> pts</small></strong>
                  </span>
                </div>
              ))}
              <span className="hce__delta">+{increase}<small>%</small></span>
            </div>

            <ul className="hce__factors" aria-label="Qué cambia entre los dos goles">
              {changedFactors(current.goals).map(([label, a, b]) => (
                <li key={label}>{label} <span>×{factor(a)}</span><ArrowIcon /><b>×{factor(b)}</b></li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="hce__links">
        {current && <Link to={`/player/${current.example.playerId}?scope=${SCOPE}`}>Ver sus actuaciones <ArrowIcon /></Link>}
        <Link to="/metodologia">Ver la fórmula <ArrowIcon /></Link>
      </div>
    </figure>
  )
}
