import { useEffect, useMemo, useState } from 'react'
import { fetchCompare, fetchSeasons } from '../api/client'
import MomentumChart from '../components/compare/MomentumChart'
import PlayerPicker from '../components/compare/PlayerPicker'
import { StatSection } from '../components/compare/ComparisonRows'
import type { CompareMetric } from '../components/compare/ComparisonRows'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import type {
  ComparePlayerAnalytics,
  CompareResponse,
  PlayerDetail,
  RankedPlayer,
  SeasonItem,
} from '../types'
import { seasonItemValue } from '../utils/season'

function fmtInteger(value: number) {
  return Math.round(value).toLocaleString('es-ES')
}

function fmtDecimal(value: number) {
  return value.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

function fmtPercent(value: number) {
  return `${value.toLocaleString('es-ES', { maximumFractionDigits: 1 })}%`
}

function fmtPoints(value: number) {
  return `${fmtInteger(value)} pts`
}

function ratio(numerator: number, denominator: number) {
  return denominator > 0 ? numerator / denominator * 100 : null
}

function per90(value: number, minutes: number) {
  return minutes > 0 ? value / minutes * 90 : null
}

function initials(name: string) {
  return name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
}

function comparisonPeriodLabel(scope: string | null, season: string) {
  if (scope?.startsWith('season-')) {
    const startYear = Number(scope.slice('season-'.length))
    if (Number.isFinite(startYear)) return `Temporada ${startYear}/${startYear + 1}`
  }
  if (scope?.startsWith('world-cup-')) {
    return `Mundial ${scope.slice('world-cup-'.length)}`
  }
  return scope ?? season
}

interface DerivedStats {
  matches: number
  minutes: number
  goals: number
  assists: number
  contributionsPer90: number | null
  shotsTotal: number
  shotsOn: number
  conversion: number | null
  penaltyWon: number
  passesTotal: number
  passAccuracy: number | null
  keyPasses: number
  dribblesWon: number
  dribblesAttempted: number
  dribbleSuccess: number | null
  dribblesPer90: number | null
  dribblesPast: number
  duelsWon: number
  duelsTotal: number
  duelSuccess: number | null
  duelsPer90: number | null
  tacklesWon: number
  interceptions: number
  blocks: number
  defensiveActionsPer90: number | null
  foulsDrawn: number
  foulsCommitted: number
  yellowCards: number
  redCards: number
  disciplinePtsLost: number
  eliteFixtures: number
  difficultOpponentAppearances: number
  keyMomentAppearances: number
  contributionStreak: number
  hatTricks: number
  goalBraces: number
  assistBraces: number
  goalAndAssistMatches: number
  mostValuableGoal: number | null
  bestMatch: number | null
  saves: number
  goalsConceded: number
}

function deriveStats(detail: PlayerDetail, analytics: ComparePlayerAnalytics): DerivedStats {
  const { stats, events, fixtures } = analytics
  const minutes = stats?.minutes ?? fixtures.reduce((sum, fixture) => sum + fixture.minutes, 0)
  const matches = stats?.matches ?? detail.matches
  const goals = stats?.goals ?? detail.total_goals
  const assists = stats?.assists ?? detail.total_assists
  const shotsTotal = stats?.shots_total ?? fixtures.reduce((sum, fixture) => sum + fixture.shots_total, 0)
  const shotsOn = stats?.shots_on ?? fixtures.reduce((sum, fixture) => sum + fixture.shots_on, 0)
  const passesTotal = stats?.passes_total ?? fixtures.reduce((sum, fixture) => sum + fixture.passes_total, 0)
  const keyPasses = stats?.passes_key ?? fixtures.reduce((sum, fixture) => sum + fixture.passes_key, 0)
  const dribblesWon = stats?.dribbles_won ?? fixtures.reduce((sum, fixture) => sum + fixture.dribbles_won, 0)
  const duelsWon = stats?.duels_won ?? fixtures.reduce((sum, fixture) => sum + fixture.duels_won, 0)
  const tacklesWon = stats?.tackles_won ?? fixtures.reduce((sum, fixture) => sum + fixture.tackles_won, 0)
  const interceptions = stats?.interceptions ?? fixtures.reduce((sum, fixture) => sum + fixture.interceptions, 0)
  const blocks = stats?.blocks ?? fixtures.reduce((sum, fixture) => sum + fixture.blocks, 0)
  const goalContributions = goals + assists
  const decisiveEvents = events.filter((event) => event.event_type !== 'stats' && event.minute > 0 && event.pts > 0)
  const difficultOpponentFixtures = new Set(
    decisiveEvents.filter((event) => event.m1 >= 1.15).map((event) => event.fixture_id),
  )
  const keyMomentFixtures = new Set(
    decisiveEvents.filter((event) => event.m3 >= 1.6).map((event) => event.fixture_id),
  )
  const eliteFixtures = fixtures.filter((fixture) => fixture.sfa_pts >= 2500).length
  const fixtureGoalCount = (fixture: ComparePlayerAnalytics['fixtures'][number]) => (
    (fixture.breakdown?.goal?.count ?? 0) + (fixture.breakdown?.goal_penalty?.count ?? 0)
  )
  const fixtureAssistCount = (fixture: ComparePlayerAnalytics['fixtures'][number]) => (
    (fixture.breakdown?.assist?.count ?? 0) + (fixture.breakdown?.corner_assist?.count ?? 0)
  )
  const hatTricks = fixtures.filter((fixture) => fixtureGoalCount(fixture) >= 3).length
  const goalBraces = fixtures.filter((fixture) => fixtureGoalCount(fixture) === 2).length
  const assistBraces = fixtures.filter((fixture) => fixtureAssistCount(fixture) >= 2).length
  const goalAndAssistMatches = fixtures.filter((fixture) => (
    fixtureGoalCount(fixture) > 0 && fixtureAssistCount(fixture) > 0
  )).length
  const goalEvents = events.filter((event) => ['goal', 'goal_penalty'].includes(event.event_type))
  const mostValuableGoal = goalEvents.length > 0
    ? Math.max(...goalEvents.map((event) => event.pts))
    : null
  const bestMatch = fixtures.length > 0
    ? Math.max(...fixtures.map((fixture) => fixture.sfa_pts))
    : null

  const scoringFixtures = new Set(
    events
      .filter((event) => ['goal', 'goal_penalty', 'assist', 'corner_assist'].includes(event.event_type))
      .map((event) => event.fixture_id),
  )
  let contributionStreak = 0
  let currentStreak = 0
  for (const fixture of [...fixtures].sort(
    (a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime(),
  )) {
    if (scoringFixtures.has(fixture.fixture_id)) {
      currentStreak += 1
      contributionStreak = Math.max(contributionStreak, currentStreak)
    } else {
      currentStreak = 0
    }
  }

  const breakdown = detail.breakdown ?? {}
  const disciplinePtsLost = Math.abs(
    (breakdown.yellow_card?.pts ?? 0)
    + (breakdown.red_card?.pts ?? 0)
    + (breakdown.fouls_committed?.pts ?? 0),
  )

  return {
    matches,
    minutes,
    goals,
    assists,
    contributionsPer90: per90(goalContributions, minutes),
    shotsTotal,
    shotsOn,
    conversion: ratio(goals, shotsTotal),
    penaltyWon: stats?.penalty_won ?? 0,
    passesTotal,
    passAccuracy: stats ? stats.passes_accuracy_avg : null,
    keyPasses,
    dribblesWon,
    dribblesAttempted: stats?.dribbles_attempts ?? 0,
    dribbleSuccess: stats?.dribble_success_rate != null ? stats.dribble_success_rate * 100 : null,
    dribblesPer90: per90(dribblesWon, minutes),
    dribblesPast: stats?.dribbles_past ?? 0,
    duelsWon,
    duelsTotal: stats?.duels_total ?? 0,
    duelSuccess: stats?.duel_win_rate != null ? stats.duel_win_rate * 100 : null,
    duelsPer90: per90(duelsWon, minutes),
    tacklesWon,
    interceptions,
    blocks,
    defensiveActionsPer90: per90(tacklesWon + interceptions + blocks, minutes),
    foulsDrawn: stats?.fouls_drawn ?? fixtures.reduce((sum, fixture) => sum + fixture.fouls_drawn, 0),
    foulsCommitted: stats?.fouls_committed ?? 0,
    yellowCards: stats?.cards_yellow ?? 0,
    redCards: stats?.cards_red ?? 0,
    disciplinePtsLost,
    eliteFixtures,
    difficultOpponentAppearances: difficultOpponentFixtures.size,
    keyMomentAppearances: keyMomentFixtures.size,
    contributionStreak,
    hatTricks,
    goalBraces,
    assistBraces,
    goalAndAssistMatches,
    mostValuableGoal,
    bestMatch,
    saves: stats?.saves ?? 0,
    goalsConceded: stats?.goals_conceded ?? 0,
  }
}

function PlayerSummary({ player, side }: { player: PlayerDetail; side: 'a' | 'b' }) {
  return (
    <article className={`cmp-player cmp-player--${side}`}>
      <span className="cmp-player__rank">SFA #{player.global_rank}</span>
      <div className="cmp-player__visual">
        {player.photo_url
          ? <img src={player.photo_url} alt={player.name} className="cmp-player__photo" />
          : <div className="cmp-player__photo-placeholder" aria-hidden="true">{initials(player.name)}</div>
        }
      </div>
      <div className="cmp-player__identity">
        <h2>{player.name}</h2>
        <span>{player.team} · {player.position}</span>
      </div>
      <strong className="cmp-player__score">{fmtInteger(player.sfa_pts)}</strong>
      <small>SFA pts</small>
    </article>
  )
}

function ComparisonSummary({ data }: { data: CompareResponse }) {
  const total = data.player_a.sfa_pts + data.player_b.sfa_pts
  const aShare = total > 0 ? data.player_a.sfa_pts / total * 100 : 50
  return (
    <section className="cmp-summary" aria-label="Resumen del enfrentamiento">
      <PlayerSummary player={data.player_a} side="a" />
      <div className="cmp-summary__center">
        <span className="cmp-summary__vs">VS</span>
        <div className="cmp-summary__score-track" aria-hidden="true">
          <span className="cmp-summary__score-a" style={{ transform: `scaleX(${aShare / 100})` }} />
          <span className="cmp-summary__score-b" style={{ transform: `scaleX(${(100 - aShare) / 100})` }} />
        </div>
        <span className="cmp-summary__scope">
          {comparisonPeriodLabel(data.scope, data.season)}
        </span>
      </div>
      <PlayerSummary player={data.player_b} side="b" />
    </section>
  )
}

function metric(
  label: string,
  a: number | null,
  b: number | null,
  format?: (value: number) => string,
  lowerIsBetter = false,
): CompareMetric {
  return { label, a, b, format, lowerIsBetter }
}

function CompareResults({ data }: { data: CompareResponse }) {
  const a = useMemo(() => deriveStats(data.player_a, data.player_a_analytics), [data])
  const b = useMemo(() => deriveStats(data.player_b, data.player_b_analytics), [data])

  const general = [
    metric('Puntos SFA', data.player_a.sfa_pts, data.player_b.sfa_pts, fmtPoints),
    metric('Partidos', a.matches, b.matches, fmtInteger),
    metric('Minutos', a.minutes, b.minutes, fmtInteger),
  ]
  const attack = [
    metric('Goles', a.goals, b.goals, fmtInteger),
    metric('Asistencias', a.assists, b.assists, fmtInteger),
    metric('Promedio de gol o asistencia por 90\'', a.contributionsPer90, b.contributionsPer90, fmtDecimal),
    metric('Hat-tricks', a.hatTricks, b.hatTricks, fmtInteger),
    metric('Dobletes de gol', a.goalBraces, b.goalBraces, fmtInteger),
    metric('Dobletes de asistencias', a.assistBraces, b.assistBraces, fmtInteger),
    metric('Gol y asistencia en un partido', a.goalAndAssistMatches, b.goalAndAssistMatches, fmtInteger),
    metric('Remates', a.shotsTotal, b.shotsTotal, fmtInteger),
    metric('Remates a puerta', a.shotsOn, b.shotsOn, fmtInteger),
    metric('Conversión de gol', a.conversion, b.conversion, fmtPercent),
    metric('Penaltis provocados', a.penaltyWon, b.penaltyWon, fmtInteger),
  ]
  const passing = [
    metric('Pases intentados', a.passesTotal, b.passesTotal, fmtInteger),
    metric('Precisión de pase', a.passAccuracy, b.passAccuracy, fmtPercent),
    metric('Pases clave (ocasiones de gol creadas)', a.keyPasses, b.keyPasses, fmtInteger),
  ]
  const duels = [
    metric('Regates ganados', a.dribblesWon, b.dribblesWon, fmtInteger),
    metric('Regates intentados', a.dribblesAttempted, b.dribblesAttempted, fmtInteger),
    metric('Éxito en regate', a.dribbleSuccess, b.dribbleSuccess, fmtPercent),
    metric('Regates ganados por 90\'', a.dribblesPer90, b.dribblesPer90, fmtDecimal),
    metric('Duelos ganados', a.duelsWon, b.duelsWon, fmtInteger),
    metric('Duelos totales', a.duelsTotal, b.duelsTotal, fmtInteger),
    metric('Éxito en duelos', a.duelSuccess, b.duelSuccess, fmtPercent),
    metric('Duelos ganados por 90\'', a.duelsPer90, b.duelsPer90, fmtDecimal),
    metric('Faltas recibidas', a.foulsDrawn, b.foulsDrawn, fmtInteger),
  ]
  const defense = [
    metric('Entradas ganadas', a.tacklesWon, b.tacklesWon, fmtInteger),
    metric('Intercepciones', a.interceptions, b.interceptions, fmtInteger),
    metric('Bloqueos', a.blocks, b.blocks, fmtInteger),
    metric('Acciones defensivas por 90\'', a.defensiveActionsPer90, b.defensiveActionsPer90, fmtDecimal),
    metric('Regateado por rival', a.dribblesPast, b.dribblesPast, fmtInteger, true),
  ]
  const context = [
    metric('Apariciones contra rivales difíciles', a.difficultOpponentAppearances, b.difficultOpponentAppearances, fmtInteger),
    metric('Apariciones en momentos clave o adversos', a.keyMomentAppearances, b.keyMomentAppearances, fmtInteger),
    metric('Actuaciones élite', a.eliteFixtures, b.eliteFixtures, fmtInteger),
    metric('Gol más valioso', a.mostValuableGoal, b.mostValuableGoal, fmtPoints),
    metric('Mejor partido (puntos SFA)', a.bestMatch, b.bestMatch, fmtPoints),
    metric('Racha con G+A', a.contributionStreak, b.contributionStreak, (value) => `${fmtInteger(value)} PJ`),
  ]
  const discipline = [
    metric('Faltas cometidas', a.foulsCommitted, b.foulsCommitted, fmtInteger, true),
    metric('Tarjetas amarillas', a.yellowCards, b.yellowCards, fmtInteger, true),
    metric('Tarjetas rojas', a.redCards, b.redCards, fmtInteger, true),
    metric('Puntos perdidos', a.disciplinePtsLost, b.disciplinePtsLost, fmtPoints, true),
  ]
  const goalkeeping = [
    metric('Paradas', a.saves, b.saves, fmtInteger),
    metric('Goles encajados', a.goalsConceded, b.goalsConceded, fmtInteger, true),
  ]

  return (
    <div className="cmp-results">
      <ComparisonSummary data={data} />
      <MomentumChart
        fixturesA={data.player_a_analytics.fixtures}
        fixturesB={data.player_b_analytics.fixtures}
        nameA={data.player_a.name}
        nameB={data.player_b.name}
      />
      <div className="cmp-stat-grid">
        <StatSection title="Rendimiento general" metrics={general} />
        <StatSection title="Ataque y definición" metrics={attack} />
        <StatSection title="Pase y creación" metrics={passing} />
        <StatSection title="Regate y duelos" metrics={duels} />
        <StatSection title="Trabajo defensivo" metrics={defense} />
        <StatSection title="Contexto SFA" metrics={context} className="cmp-stat-section--context" />
        <StatSection title="Disciplina" metrics={discipline} />
        {(a.saves > 0 || b.saves > 0 || a.goalsConceded > 0 || b.goalsConceded > 0) && (
          <StatSection title="Portería" metrics={goalkeeping} />
        )}
      </div>
    </div>
  )
}

export default function ComparePage() {
  const [seasons, setSeasons] = useState<SeasonItem[]>([])
  const [scope, setScope] = useState('')
  const [selectedA, setSelectedA] = useState<RankedPlayer | null>(null)
  const [selectedB, setSelectedB] = useState<RankedPlayer | null>(null)
  const [data, setData] = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSeasons()
      .then(({ seasons: items }) => {
        setSeasons(items)
        const latest = items.find((item) => item.is_latest) ?? items[0]
        if (latest) setScope(seasonItemValue(latest))
      })
      .catch(() => setError('No se pudieron cargar las temporadas.'))
  }, [])

  useEffect(() => {
    if (!selectedA || !selectedB || !scope) {
      setData(null)
      return
    }

    let active = true
    setLoading(true)
    setError(null)
    fetchCompare(selectedA.id, selectedB.id, scope)
      .then((result) => { if (active) setData(result) })
      .catch(() => { if (active) setError('No se pudo completar la comparación.') })
      .finally(() => { if (active) setLoading(false) })

    return () => { active = false }
  }, [scope, selectedA?.id, selectedB?.id])

  const selectedCount = Number(Boolean(selectedA)) + Number(Boolean(selectedB))

  return (
    <main className="compare-page">
      <header className="cmp-page-header">
        <div>
          <span className="cmp-page-header__eyebrow">Head to head SFA</span>
          <h1>Comparar jugadores</h1>
        </div>
        {seasons.length > 0 && (
          <SeasonDropdown items={seasons} value={scope} onChange={setScope} includeAll={false} />
        )}
      </header>

      <section className="cmp-selection" aria-label="Seleccionar jugadores">
        <PlayerPicker
          label="Jugador A"
          selected={selectedA}
          onSelect={(player) => setSelectedA(player)}
          onClear={() => setSelectedA(null)}
          excludeId={selectedB?.id}
          scope={scope}
        />
        <span className="cmp-selection__versus" aria-hidden="true">VS</span>
        <PlayerPicker
          label="Jugador B"
          selected={selectedB}
          onSelect={(player) => setSelectedB(player)}
          onClear={() => setSelectedB(null)}
          excludeId={selectedA?.id}
          scope={scope}
        />
      </section>

      {loading && (
        <div className="cmp-loading" aria-label="Cargando comparación">
          <div className="skeleton cmp-loading__summary" />
          <div className="skeleton cmp-loading__chart" />
          <div className="cmp-loading__rows">
            {Array.from({ length: 8 }).map((_, index) => <div className="skeleton" key={index} />)}
          </div>
        </div>
      )}

      {!loading && error && <div className="cmp-state cmp-state--error" role="alert">{error}</div>}

      {!loading && !error && data && <CompareResults data={data} />}

      {!loading && !error && !data && (
        <section className="cmp-state cmp-state--empty">
          <div className="cmp-state__versus" aria-hidden="true">{selectedCount === 1 ? '1/2' : 'VS'}</div>
          <h2>{selectedCount === 1 ? 'Selecciona el segundo jugador' : 'Elige dos jugadores'}</h2>
          <p>La comparación se construye con el periodo seleccionado.</p>
        </section>
      )}
    </main>
  )
}
