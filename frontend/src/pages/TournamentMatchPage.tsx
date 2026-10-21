import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fetchSeasons, fetchTeamRanking, fetchTournamentFixtureDetail } from '../api/client'
import { MatchEvents, MatchHero, MatchLineups, MatchMomentum, MatchStats, type TeamLevels } from '../components/tournaments/match/MatchView'
import PlayerMatchSheet from '../components/tournaments/match/PlayerMatchSheet'
import { buildMatchModel, type MatchPlayer } from '../components/tournaments/match/matchModel'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import type { TournamentMatchDetail } from '../types'
import { tournamentCompetitionLogoByName, tournamentStageLabel } from '../utils/tournaments'
import { strengthFromElo } from '../utils/teams'
import './TournamentMatchPage.css'

export default function TournamentMatchPage() {
  const navigate = useNavigate()
  const { fixtureId } = useParams<{ fixtureId: string }>()
  const [searchParams] = useSearchParams()
  const season = searchParams.get('season') ?? '2026'
  const numericFixtureId = Number(fixtureId)
  const [detail, setDetail] = useState<TournamentMatchDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const polling = useRef(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setDetail(null)
    if (!Number.isFinite(numericFixtureId)) {
      setError('Partido no válido.')
      setLoading(false)
      return () => { active = false }
    }
    fetchTournamentFixtureDetail(numericFixtureId, season)
      .then((result) => { if (active) setDetail(result) })
      .catch(() => { if (active) setError('No se pudo cargar el partido.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [numericFixtureId, season])

  useEffect(() => {
    if (!detail?.fixture.is_live || !Number.isFinite(numericFixtureId)) return
    let active = true
    const refresh = async () => {
      if (polling.current) return
      polling.current = true
      try {
        const result = await fetchTournamentFixtureDetail(numericFixtureId, season, true)
        if (active) {
          setDetail((previous) => {
            if (!previous) return result
            return {
              ...result,
              venue: result.venue.name || result.venue.city ? result.venue : previous.venue,
              referee: result.referee ?? previous.referee,
              lineups: result.lineups.length > 0 ? result.lineups : previous.lineups,
              statistics: result.statistics.length > 0 ? result.statistics : previous.statistics,
              events: result.events.length > 0 ? result.events : previous.events,
              sfa_momentum: result.sfa_momentum.length > 0 ? result.sfa_momentum : previous.sfa_momentum,
            }
          })
        }
      } catch {
        // Keep the last canonical snapshot visible during a transient refresh failure.
      } finally {
        polling.current = false
      }
    }
    const timer = window.setInterval(refresh, 30_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [detail?.fixture.is_live, numericFixtureId, season])

  const lineupTeams = useMemo(() => new Set(detail?.lineups.map((lineup) => lineup.team.external_id) ?? []), [detail])
  const model = useMemo(() => (detail ? buildMatchModel(detail) : null), [detail])
  const [selected, setSelected] = useState<MatchPlayer | null>(null)
  const [levels, setLevels] = useState<TeamLevels>({ home: null, away: null })
  const homeTeam = detail?.fixture.home_team
  const awayTeam = detail?.fixture.away_team

  // Each side's competitive level (the same input as the rival multiplier, M1).
  useEffect(() => {
    if (!homeTeam || !awayTeam) return undefined
    let active = true
    setLevels({ home: null, away: null })
    const levelOf = async (teamScope: string, name: string, externalId: number | null) => {
      const result = await fetchTeamRanking({ scope: teamScope, name, page: 1 })
      const team = result.ranking.find((item) => externalId != null && item.team_logo_url?.endsWith(`/teams/${externalId}.png`))
        ?? result.ranking.find((item) => item.name === name)
      return strengthFromElo(team?.elo_raw)
    }
    fetchSeasons()
      .then((catalog) => {
        const teamScope = catalog.seasons.find((item) => item.kind === 'award_period' && item.season === season)?.key
        if (!teamScope) return
        return Promise.all([
          levelOf(teamScope, homeTeam.name, homeTeam.external_id).catch(() => null),
          levelOf(teamScope, awayTeam.name, awayTeam.external_id).catch(() => null),
        ]).then(([home, away]) => { if (active) setLevels({ home, away }) })
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [homeTeam, awayTeam, season])
  // Everyone who stepped on the pitch, home then away, starters before substitutes.
  const sheetPlayers = useMemo(() => (model
    ? (['home', 'away'] as const).flatMap((side) => [
        ...model.players.filter((player) => player.side === side && player.starter),
        ...model.players.filter((player) => player.side === side && !player.starter && player.marks.on != null),
      ])
    : []), [model])
  const sheetRank = useMemo(() => new Map(model?.ranked.map((player, index) => [player, index + 1]) ?? []), [model])
  const scope = `season-${season}`

  function goBack() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) navigate(-1)
    else navigate('/torneos')
  }

  if (loading) {
    return (
      <main className="mt-page" aria-busy="true">
        <span className="sr-only" role="status">Cargando partido</span>
        <div className="mt-skel mt-skel--hero" />
        <div className="mt-skel mt-skel--pitch" />
      </main>
    )
  }

  if (error || !detail || !model) {
    return (
      <main className="mt-page">
        <button type="button" className="mt-back" onClick={goBack}><ArrowIcon direction="left" /> Todos los partidos</button>
        <div className="mt-empty" role="alert">{error ?? 'Partido no encontrado.'}</div>
      </main>
    )
  }

  const { fixture } = detail
  const competitionLogo = tournamentCompetitionLogoByName(fixture.competition_name)

  return (
    <main className="mt-page">
      <nav className="mt-crumbs" aria-label="Ruta">
        <button type="button" className="mt-back" onClick={goBack}><ArrowIcon direction="left" /> Todos los partidos</button>
        <span aria-hidden="true">/</span>
        {fixture.competition_id != null ? (
          <Link to={`/torneos/${fixture.competition_id}?season=${season}`} className="mt-crumbs__comp">
            {competitionLogo && <span className="tp-tile"><img src={competitionLogo} alt="" /></span>}
            {fixture.competition_name ?? 'Competición'}
          </Link>
        ) : <span className="mt-crumbs__comp">{fixture.competition_name ?? 'Competición'}</span>}
        <span className="mt-crumbs__stage">· {tournamentStageLabel(fixture.stage, fixture.matchday)}</span>
      </nav>

      <MatchHero detail={detail} model={model} scope={scope} onSelect={setSelected} levels={levels} />
      <MatchLineups detail={detail} model={model} scope={scope} onSelect={setSelected} />
      {detail.lineups.length > 0 && lineupTeams.size < 2 && <p className="mt-note">La alineación de uno de los equipos todavía no fue publicada.</p>}
      <MatchMomentum detail={detail} model={model} />
      <div className="mt-split">
        <MatchEvents detail={detail} model={model} scope={scope} />
        <MatchStats statistics={detail.statistics} homeTeam={fixture.home_team} awayTeam={fixture.away_team} />
      </div>

      <PlayerMatchSheet
        player={selected}
        players={sheetPlayers}
        rank={sheetRank}
        matchExternalId={fixture.external_id}
        scope={scope}
        onNavigate={setSelected}
        onClose={() => setSelected(null)}
      />
    </main>
  )
}
