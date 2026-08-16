import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fetchTournamentFixtureDetail } from '../api/client'
import TournamentMatchHeader from '../components/tournaments/match/TournamentMatchHeader'
import TournamentMatchLineups from '../components/tournaments/match/TournamentMatchLineups'
import TournamentMatchMomentum from '../components/tournaments/match/TournamentMatchMomentum'
import TournamentMatchPerformance from '../components/tournaments/match/TournamentMatchPerformance'
import TournamentMatchStatistics from '../components/tournaments/match/TournamentMatchStatistics'
import TournamentMatchTimeline from '../components/tournaments/match/TournamentMatchTimeline'
import type { TournamentMatchDetail } from '../types'

type MatchTab = 'summary' | 'statistics' | 'timeline' | 'lineups' | 'performance'

const TABS: Array<[MatchTab, string]> = [
  ['summary', 'Resumen'],
  ['statistics', 'Estadísticas'],
  ['timeline', 'Cronología'],
  ['lineups', 'Alineaciones'],
  ['performance', 'Rendimiento SFA'],
]

function MatchInfo({ detail }: { detail: TournamentMatchDetail }) {
  const formations = detail.lineups.map((lineup) => ({ name: lineup.team.name, formation: lineup.formation }))
  const leaders = detail.lineups
    .flatMap((lineup) => [...lineup.start_xi, ...lineup.substitutes].map((player) => ({ ...player, team: lineup.team.name })))
    .filter((player) => player.sfa_points != null)
    .sort((a, b) => (b.sfa_points ?? 0) - (a.sfa_points ?? 0))
    .slice(0, 3)
  return (
    <aside className="trm-rail" aria-label="Información del partido">
      <section>
        <header><span>Partido</span><h2>Información</h2></header>
        <dl>
          <div><dt>Estadio</dt><dd>{detail.venue.name ?? 'Por confirmar'}</dd></div>
          <div><dt>Ciudad</dt><dd>{detail.venue.city ?? 'Por confirmar'}</dd></div>
          <div><dt>Árbitro</dt><dd>{detail.referee ?? 'Por confirmar'}</dd></div>
        </dl>
      </section>
      {formations.length > 0 && (
        <section>
          <header><span>Planteamiento</span><h2>Formaciones</h2></header>
          <dl>{formations.map((item) => <div key={item.name}><dt>{item.name}</dt><dd>{item.formation ?? 'Pendiente'}</dd></div>)}</dl>
        </section>
      )}
      <section>
        <header><span>Rendimiento actual</span><h2>Líderes SFA</h2></header>
        {leaders.length > 0 ? (
          <ol className="trm-rail__leaders">
            {leaders.map((player, index) => (
              <li key={`${player.external_id ?? player.name}-${index}`}>
                <span>{index + 1}</span>
                <div><strong>{player.name}</strong><small>{player.team}</small></div>
                <b>{Math.round(player.sfa_points ?? 0).toLocaleString('es-ES')} pts</b>
              </li>
            ))}
          </ol>
        ) : <p className="trm-rail__pending">Puntos pendientes de cálculo.</p>}
      </section>
    </aside>
  )
}

export default function TournamentMatchPage() {
  const navigate = useNavigate()
  const { fixtureId } = useParams<{ fixtureId: string }>()
  const [searchParams] = useSearchParams()
  const season = searchParams.get('season') ?? '2026'
  const numericFixtureId = Number(fixtureId)
  const [detail, setDetail] = useState<TournamentMatchDetail | null>(null)
  const [tab, setTab] = useState<MatchTab>('summary')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const polling = useRef(false)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

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
        if (active) setDetail(result)
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
  const scope = `season-${season}`

  function goBack() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) navigate(-1)
    else navigate('/torneos')
  }

  if (loading) {
    return <main className="trm-page"><div className="trm-skeleton"><i /><i /><i /></div></main>
  }

  if (error || !detail) {
    return (
      <main className="trm-page">
        <button type="button" className="trm-back" onClick={goBack}><span aria-hidden="true">←</span> Volver a Torneos</button>
        <div className="trm-empty trm-empty--error">{error ?? 'Partido no encontrado.'}</div>
      </main>
    )
  }

  const { fixture } = detail
  const homeExternalId = fixture.home_team.external_id

  return (
    <main className="trm-page">
      <div className="trm-actions">
        <button type="button" className="trm-back" onClick={goBack}><span aria-hidden="true">←</span> Volver a Torneos</button>
        {fixture.competition_id != null && <Link to={`/torneos/${fixture.competition_id}?season=${season}`}>Ver torneo <span aria-hidden="true">→</span></Link>}
      </div>

      <TournamentMatchHeader fixture={fixture} />

      <nav className="trm-tabs" role="tablist" aria-label="Detalle del partido">
        {TABS.map(([id, label]) => (
          <button
            type="button"
            role="tab"
            id={`trm-tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`trm-panel-${id}`}
            className={tab === id ? 'is-active' : ''}
            onClick={() => setTab(id)}
            key={id}
          >{label}</button>
        ))}
      </nav>

      <div id={`trm-panel-${tab}`} role="tabpanel" aria-labelledby={`trm-tab-${tab}`} className="trm-content">
        {tab === 'summary' && (
          <div className="trm-summary">
            <div className="trm-summary__main">
              <TournamentMatchMomentum buckets={detail.sfa_momentum} homeName={fixture.home_team.name} awayName={fixture.away_team.name} />
              <TournamentMatchTimeline events={detail.events} homeTeamExternalId={homeExternalId} />
            </div>
            <MatchInfo detail={detail} />
          </div>
        )}
        {tab === 'statistics' && <TournamentMatchStatistics statistics={detail.statistics} />}
        {tab === 'timeline' && <TournamentMatchTimeline events={detail.events} homeTeamExternalId={homeExternalId} />}
        {tab === 'lineups' && <TournamentMatchLineups lineups={detail.lineups} scope={scope} />}
        {tab === 'performance' && <TournamentMatchPerformance lineups={detail.lineups} scope={scope} />}
      </div>

      {detail.lineups.length > 0 && lineupTeams.size < 2 && <p className="trm-partial-note">La alineación de uno de los equipos todavía no fue publicada.</p>}
    </main>
  )
}
