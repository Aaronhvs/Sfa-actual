import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import './ComparePage.css'
import { fetchCompare, fetchPlayerAchievements, fetchPlayerIndividualHonors, fetchRanking, fetchSeasons } from '../api/client'
import PlayerPicker from '../components/compare/PlayerPicker'
import {
  BestPanel,
  DetailPanel,
  DuelHero,
  fmt,
  ImpactPanel,
  SourcesAbsolute,
  StyleDuel,
  WhyPanel,
  type Extras,
  TrendPanel,
  sideStyle,
  type Metric,
} from '../components/compare/CompareView'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import type {
  ComparePlayerAnalytics,
  CompareResponse,
  PlayerDetail,
  RankedPlayer,
  SeasonItem,
} from '../types'
import { seasonItemValue } from '../utils/season'

function ratio(numerator: number, denominator: number) {
  return denominator > 0 ? numerator / denominator * 100 : null
}

function per90(value: number, minutes: number) {
  return minutes > 0 ? value / minutes * 90 : null
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
  sfaGoals: number
  sfaAssists: number
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

  const bd = detail.breakdown ?? {}
  return {
    sfaGoals: (bd.goal?.count ?? 0) + (bd.goal_penalty?.count ?? 0),
    sfaAssists: (bd.assist?.count ?? 0) + (bd.corner_assist?.count ?? 0),
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

function buildGroups(a: DerivedStats, b: DerivedStats) {
  const m = (label: string, x: number | null, y: number | null, format: (value: number) => string, lowerIsBetter = false, hint?: string): Metric => ({ label, a: x, b: y, format, lowerIsBetter, hint })
  const groups = [
    { id: 'attack', label: 'Ataque', metrics: [
      m('Goles puntuados por SFA', a.sfaGoals, b.sfaGoals, fmt.int),
      m('Asistencias puntuadas por SFA', a.sfaAssists, b.sfaAssists, fmt.int),
      m('Goles totales (fuente)', a.goals, b.goals, fmt.int, false, 'Incluye partidos o competiciones que SFA no puntúa'),
      m("Goles + asistencias por 90'", a.contributionsPer90, b.contributionsPer90, fmt.two),
      m('Remates', a.shotsTotal, b.shotsTotal, fmt.int),
      m('Remates a puerta', a.shotsOn, b.shotsOn, fmt.int),
      m('Conversión de gol', a.conversion, b.conversion, fmt.pct),
      m('Penales provocados', a.penaltyWon, b.penaltyWon, fmt.int),
      m('Dobletes de gol', a.goalBraces, b.goalBraces, fmt.int),
      m('Gol y asistencia en un partido', a.goalAndAssistMatches, b.goalAndAssistMatches, fmt.int),
    ] },
    { id: 'creation', label: 'Creación', metrics: [
      m('Pases clave', a.keyPasses, b.keyPasses, fmt.int),
      m('Precisión de pase', a.passAccuracy, b.passAccuracy, fmt.pct),
      m('Pases', a.passesTotal, b.passesTotal, fmt.int),
      m('Regates ganados', a.dribblesWon, b.dribblesWon, fmt.int),
      m('Éxito en regate', a.dribbleSuccess, b.dribbleSuccess, fmt.pct),
      m("Regates por 90'", a.dribblesPer90, b.dribblesPer90, fmt.two),
      m('Faltas recibidas', a.foulsDrawn, b.foulsDrawn, fmt.int),
    ] },
    { id: 'defense', label: 'Defensa', metrics: [
      m('Duelos ganados', a.duelsWon, b.duelsWon, fmt.int),
      m('Éxito en duelos', a.duelSuccess, b.duelSuccess, fmt.pct),
      m('Entradas ganadas', a.tacklesWon, b.tacklesWon, fmt.int),
      m('Intercepciones', a.interceptions, b.interceptions, fmt.int),
      m('Bloqueos', a.blocks, b.blocks, fmt.int),
      m("Acciones defensivas por 90'", a.defensiveActionsPer90, b.defensiveActionsPer90, fmt.two),
      m('Regateado por el rival', a.dribblesPast, b.dribblesPast, fmt.int, true),
    ] },
    { id: 'discipline', label: 'Disciplina', metrics: [
      m('Faltas cometidas', a.foulsCommitted, b.foulsCommitted, fmt.int, true),
      m('Tarjetas amarillas', a.yellowCards, b.yellowCards, fmt.int, true),
      m('Tarjetas rojas', a.redCards, b.redCards, fmt.int, true),
      m('Puntos perdidos', a.disciplinePtsLost, b.disciplinePtsLost, fmt.pts, true),
    ] },
  ]
  if (a.saves > 0 || b.saves > 0 || a.goalsConceded > 0 || b.goalsConceded > 0) {
    groups.push({ id: 'gk', label: 'Portería', metrics: [m('Paradas', a.saves, b.saves, fmt.int), m('Goles encajados', a.goalsConceded, b.goalsConceded, fmt.int, true)] })
  }
  return groups
}

const NO_EXTRAS: Extras = { titles: 0, honors: 0 }

/** Titles/phases and individual awards also feed the SFA total; the compare endpoint does not include them. */
function useExtras(playerId: number, scope: string | null) {
  const [extras, setExtras] = useState<Extras | null>(null)
  useEffect(() => {
    let active = true
    setExtras(null)
    Promise.all([
      fetchPlayerAchievements(playerId, undefined, scope ?? undefined).catch(() => []),
      fetchPlayerIndividualHonors(playerId, undefined, scope ?? undefined).catch(() => []),
    ]).then(([achievements, honors]) => {
      if (!active) return
      setExtras({
        titles: achievements.reduce((sum, item) => sum + item.bonus_pts, 0),
        honors: honors.reduce((sum, item) => sum + item.bonus_pts, 0),
      })
    })
    return () => { active = false }
  }, [playerId, scope])
  return extras
}

function CompareResults({ data }: { data: CompareResponse }) {
  const a = useMemo(() => deriveStats(data.player_a, data.player_a_analytics), [data])
  const b = useMemo(() => deriveStats(data.player_b, data.player_b_analytics), [data])
  const groups = useMemo(() => buildGroups(a, b), [a, b])
  const extrasA = useExtras(data.player_a.id, data.scope)
  const extrasB = useExtras(data.player_b.id, data.scope)
  const ready = extrasA != null && extrasB != null
  return (
    <div className="cv-results">
      <DuelHero data={data} periodLabel={comparisonPeriodLabel(data.scope, data.season)} minutesA={a.minutes} minutesB={b.minutes} />
      {ready
        ? <WhyPanel data={data} extrasA={extrasA ?? NO_EXTRAS} extrasB={extrasB ?? NO_EXTRAS} minutesA={a.minutes} minutesB={b.minutes} />
        : <div className="cv-skel cv-skel--why" role="status"><span className="sr-only">Calculando la diferencia</span></div>}
      <StyleDuel data={data} />
      <ImpactPanel data={data} minutesA={a.minutes} minutesB={b.minutes} />
      <div className="cv-grid-2">
        {ready && <SourcesAbsolute data={data} extrasA={extrasA ?? NO_EXTRAS} extrasB={extrasB ?? NO_EXTRAS} />}
        <BestPanel data={data} />
      </div>
      <TrendPanel data={data} />
      <DetailPanel groups={groups} nameA={data.player_a.name} nameB={data.player_b.name} />
    </div>
  )
}

/** The picker only needs identity fields; a PlayerDetail from the API covers them. */
function asPicked(player: PlayerDetail): RankedPlayer {
  return { ...(player as unknown as RankedPlayer), rank: player.global_rank, goals: player.total_goals, assists: player.total_assists }
}

function Suggestions({ scope, onPick }: { scope: string; onPick: (a: RankedPlayer, b: RankedPlayer) => void }) {
  const [top, setTop] = useState<RankedPlayer[]>([])
  useEffect(() => {
    if (!scope) return undefined
    let active = true
    fetchRanking({ scope, limit: 4 }).then((result) => { if (active) setTop(result.ranking) }).catch(() => undefined)
    return () => { active = false }
  }, [scope])
  const pairs: Array<[number, number]> = [[0, 1], [0, 2], [1, 2], [2, 3]]
  const duels = pairs.flatMap(([i, j]) => (top[i] && top[j] ? [[top[i], top[j]] as const] : []))
  if (duels.length === 0) return null
  return (
    <div className="cv-suggest">
      <span className="pf-eyebrow">Duelos del momento</span>
      <ul>
        {duels.map(([x, y]) => (
          <li key={`${x.id}-${y.id}`}>
            <button type="button" onClick={() => onPick(x, y)}>
              <span className="cv-suggest__faces">
                <span>{x.photo_url && <img src={x.photo_url} alt="" />}</span>
                <span>{y.photo_url && <img src={y.photo_url} alt="" />}</span>
              </span>
              <span className="cv-suggest__names"><strong>{x.name}</strong><small>vs</small><strong>{y.name}</strong></span>
              <ArrowIcon />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const [seasons, setSeasons] = useState<SeasonItem[]>([])
  const [scope, setScope] = useState(params.get('scope') ?? '')
  const [selectedA, setSelectedA] = useState<RankedPlayer | null>(null)
  const [selectedB, setSelectedB] = useState<RankedPlayer | null>(null)
  const [data, setData] = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const urlA = Number(params.get('a')) || null
  const urlB = Number(params.get('b')) || null

  useEffect(() => {
    fetchSeasons()
      .then(({ seasons: items }) => {
        setSeasons(items)
        if (!scope) {
          const latest = items.find((item) => item.is_latest) ?? items[0]
          if (latest) setScope(seasonItemValue(latest))
        }
      })
      .catch(() => setError('No se pudieron cargar las temporadas.'))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const idA = selectedA?.id ?? urlA
  const idB = selectedB?.id ?? urlB

  useEffect(() => {
    if (!idA || !idB || !scope) {
      setData(null)
      return undefined
    }
    let active = true
    setLoading(true)
    setError(null)
    fetchCompare(idA, idB, scope)
      .then((result) => {
        if (!active) return
        setData(result)
        // Players restored from a shared link fill the pickers once the comparison arrives.
        setSelectedA((current) => current ?? asPicked(result.player_a))
        setSelectedB((current) => current ?? asPicked(result.player_b))
      })
      .catch(() => { if (active) setError('No se pudo completar la comparación.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [scope, idA, idB])

  useEffect(() => {
    const next = new URLSearchParams()
    if (scope) next.set('scope', scope)
    if (idA) next.set('a', String(idA))
    if (idB) next.set('b', String(idB))
    setParams(next, { replace: true })
  }, [scope, idA, idB, setParams])

  const clear = (side: 'a' | 'b') => {
    setData(null)
    if (side === 'a') setSelectedA(null)
    else setSelectedB(null)
    const next = new URLSearchParams(params)
    next.delete(side)
    setParams(next, { replace: true })
  }

  const swap = () => {
    setSelectedA(selectedB)
    setSelectedB(selectedA)
    if (data) setData({ ...data, player_a: data.player_b, player_b: data.player_a, player_a_analytics: data.player_b_analytics, player_b_analytics: data.player_a_analytics })
  }

  const selectedCount = Number(Boolean(idA)) + Number(Boolean(idB))

  return (
    <main className="cv-page" style={sideStyle()}>
      <header className="cv-head">
        <div>
          <p className="tp-eyebrow">Cara a cara SFA</p>
          <h1>Comparador</h1>
          <p className="cv-head__lead">Quién tiene más impacto y, sobre todo, en qué contexto lo consigue.</p>
        </div>
        {seasons.length > 0 && <SeasonDropdown items={seasons} value={scope} onChange={setScope} includeAll={false} />}
      </header>

      <section className="cv-pick" aria-label="Seleccionar jugadores">
        <div className="cv-pick__slot is-a">
          <PlayerPicker label="Jugador A" selected={selectedA} onSelect={setSelectedA} onClear={() => clear('a')} excludeId={idB ?? undefined} scope={scope} />
        </div>
        <button type="button" className="cv-pick__swap" onClick={swap} disabled={!selectedA && !selectedB} aria-label="Intercambiar jugadores" title="Intercambiar">
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M4 7h11l-3-3M16 13H5l3 3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
        <div className="cv-pick__slot is-b">
          <PlayerPicker label="Jugador B" selected={selectedB} onSelect={setSelectedB} onClear={() => clear('b')} excludeId={idA ?? undefined} scope={scope} />
        </div>
      </section>

      {loading && (
        <div className="cv-loading" role="status">
          <span className="sr-only">Cargando comparación</span>
          <div className="cv-skel cv-skel--hero" />
          <div className="cv-skel cv-skel--body" />
        </div>
      )}

      {!loading && error && <div className="cv-state" role="alert">{error}</div>}

      {!loading && !error && data && <CompareResults data={data} />}

      {!loading && !error && !data && (
        <section className="cv-empty">
          <span className="cv-empty__vs" aria-hidden="true">{selectedCount === 1 ? '1/2' : 'VS'}</span>
          <h2>{selectedCount === 1 ? 'Elige el segundo jugador' : 'Elige dos jugadores'}</h2>
          <p>Compara su impacto SFA, cuánto vale cada acción y en qué contexto la consiguen.</p>
          {selectedCount === 0 && <Suggestions scope={scope} onPick={(x, y) => { setSelectedA(x); setSelectedB(y) }} />}
        </section>
      )}
    </main>
  )
}
