import { useEffect, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fetchRanking, fetchSeasons, fetchTeamRanking } from '../api/client'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import type { RankedPlayer } from '../types'
import type { RankedTeam } from '../types/teamRanking'
import { competitionLabel } from '../utils/footballLabels'
import { tournamentCompetitionLogoByName } from '../utils/tournaments'
import { levelBand, strengthFromElo } from '../utils/teams'
import './TeamPage.css'

const POSITION: Record<string, string> = {
  GK: 'Portero', DC: 'Central', LAT: 'Lateral', MC: 'Centrocampista', MCO: 'Mediapunta', EXT: 'Extremo', DEL: 'Delantero',
}
const OUTCOME: Record<string, string> = { W: 'G', D: 'E', L: 'P' }

const pts = (value: number) => Math.round(value).toLocaleString('es-ES')
const one = (value: number) => value.toLocaleString('es-ES', { maximumFractionDigits: 1 })
const shortDate = (iso: string) => new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(new Date(iso)).replace('.', '')

type Loaded = { team: RankedTeam; scope: string; season: string; players: RankedPlayer[] }

export default function TeamPage() {
  const navigate = useNavigate()
  const { externalId } = useParams<{ externalId: string }>()
  const [params] = useSearchParams()
  const name = params.get('name') ?? ''
  const id = Number(externalId)
  const [data, setData] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setData(null)
    setError(null)
    if (!name || !Number.isFinite(id)) {
      setError('Equipo no encontrado.')
      return () => { active = false }
    }
    ;(async () => {
      const catalog = await fetchSeasons()
      const periods = catalog.seasons.filter((item) => item.kind === 'award_period')
      const current = periods.find((item) => item.is_latest) ?? periods[0]
      if (!current) throw new Error('Sin temporada')
      const [teams, ranking] = await Promise.all([
        fetchTeamRanking({ scope: current.key, name, page: 1 }),
        fetchRanking({ scope: current.key, name, limit: 50 }),
      ])
      // Name search is fuzzy ("Barcelona" also finds "Barcelona SC"): pin the club by its crest id.
      const team = teams.ranking.find((item) => item.team_logo_url?.endsWith(`/teams/${id}.png`))
        ?? teams.ranking.find((item) => item.name === name)
      if (!team) throw new Error('Equipo no encontrado')
      const players = ranking.ranking
        .filter((player) => player.team === team.name)
        .sort((a, b) => b.sfa_pts - a.sfa_pts)
      if (active) setData({ team, scope: current.key, season: current.season, players })
    })().catch(() => { if (active) setError('No pudimos cargar este equipo.') })
    return () => { active = false }
  }, [id, name])

  const goBack = () => {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) navigate(-1)
    else navigate('/torneos')
  }

  if (error) {
    return (
      <main className="tm-page">
        <button type="button" className="pf-back tm-back" onClick={goBack}><ArrowIcon direction="left" /> Volver</button>
        <div className="tm-empty" role="alert">{error}</div>
      </main>
    )
  }

  if (!data) {
    return (
      <main className="tm-page" aria-busy="true">
        <span className="sr-only" role="status">Cargando equipo</span>
        <div className="tm-skel tm-skel--hero" />
        <div className="tm-skel tm-skel--body" />
      </main>
    )
  }

  const { team, scope, season, players } = data
  const level = strengthFromElo(team.elo_raw)
  const leader = players[0]
  const squadTotal = players.reduce((sum, player) => sum + player.sfa_pts, 0)
  const goals = players.reduce((sum, player) => sum + player.goals, 0)
  const assists = players.reduce((sum, player) => sum + player.assists, 0)
  const compLogo = tournamentCompetitionLogoByName(team.competition)
  const results = team.recent_results
  const wins = results.filter((result) => result.outcome === 'W').length
  const maxPlayer = Math.max(...players.map((player) => player.sfa_pts), 1)

  return (
    <main className="tm-page">
      <nav className="tm-crumbs" aria-label="Ruta">
        <button type="button" className="pf-back tm-back" onClick={goBack}><ArrowIcon direction="left" /> Volver</button>
      </nav>

      <div className="tm-hero">
        <section className="tm-id">
          {team.team_logo_url && <img className="tm-id__wash" src={team.team_logo_url} alt="" aria-hidden="true" />}
          {team.team_logo_url && <img className="tm-id__crest" src={team.team_logo_url} alt="" width={112} height={112} />}
          <div>
            <h1>{team.name}</h1>
            <p className="tm-id__meta">
              {compLogo && <span className="tp-tile"><img src={compLogo} alt="" /></span>}
              {competitionLabel(team.competition)}
              <span>· Temporada {season}/{String(Number(season) + 1).slice(-2)}</span>
            </p>
            <ul className="tm-form" aria-label="Últimos resultados, del más antiguo al más reciente">
              {results.map((result) => (
                <li key={result.fixture_external_id}>
                  <Link
                    to={`/torneos/partido/${result.fixture_external_id}?season=${season}`}
                    className={`tm-form__pill is-${result.outcome ?? 'none'}`}
                    title={`${result.is_home ? 'vs' : 'en'} ${result.opponent_name} · ${result.goals_for ?? '-'}–${result.goals_against ?? '-'} · ${shortDate(result.played_at)}`}
                  >
                    {result.outcome ? OUTCOME[result.outcome] : '·'}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {level != null && (
          <section className="tm-level" aria-labelledby="tm-level-title">
            <span className="pf-eyebrow pf-eyebrow--gold" id="tm-level-title">Nivel como rival</span>
            <div className="tm-level__row">
              <span className="tm-level__dial" style={{ '--p': level / 100 } as CSSProperties}>
                <b>{Math.round(level)}</b><small>/100</small>
              </span>
              <span className="tm-level__copy">
                <strong>{levelBand(level)}</strong>
                <small>ELO {team.elo_raw != null ? Math.round(team.elo_raw).toLocaleString('es-ES') : '—'} · escala del motor SFA</small>
              </span>
            </div>
            <p>
              Cuanto más alto, más valen las acciones de quien juega <b>contra</b> {team.name}: el multiplicador de rival (M1) va de <b>×0,6</b> ante los más débiles a <b>×1,8</b> ante los más fuertes.
            </p>
            <Link to="/metodologia" className="tm-level__link">Cómo se calcula <ArrowIcon /></Link>
          </section>
        )}
      </div>

      <ul className="tm-kpis">
        <li><span className="pf-eyebrow">Puntos SFA de la plantilla</span><b>{pts(squadTotal)}</b><small>{players.length} jugadores puntuados</small></li>
        <li><span className="pf-eyebrow">Goles · asistencias</span><b>{goals} · {assists}</b><small>de sus jugadores en la temporada</small></li>
        <li><span className="pf-eyebrow">Últimos {results.length}</span><b>{wins} {wins === 1 ? 'victoria' : 'victorias'}</b><small>{results.map((result) => `${result.goals_for ?? '-'}–${result.goals_against ?? '-'}`).join(' · ')}</small></li>
        {leader && <li><span className="pf-eyebrow">Su referente</span><b className="is-name">{leader.name}</b><small>{pts(leader.sfa_pts)} pts SFA · #{leader.rank} del ranking</small></li>}
      </ul>

      <div className="tm-split">
        <section className="pf-panel" aria-labelledby="tm-squad-title">
          <header className="pf-panel__head"><div><h2 id="tm-squad-title">Plantilla por puntos SFA</h2><p>Quién sostiene al equipo esta temporada</p></div></header>
          {players.length === 0 ? <p className="tm-empty-inline">Todavía no hay jugadores puntuados.</p> : (
            <ol className="tm-squad">
              {players.map((player, index) => (
                <li key={player.id}>
                  <Link to={`/player/${player.id}?scope=${scope}`}>
                    <b className="tm-squad__rank">{index + 1}</b>
                    <span className="tm-squad__photo">{player.photo_url && <img src={player.photo_url} alt="" loading="lazy" />}</span>
                    <span className="tm-squad__who">
                      <strong>{player.name}</strong>
                      <small>{POSITION[player.position] ?? player.position} · {player.goals} G · {player.assists} A · {player.matches} PJ</small>
                    </span>
                    <span className="tm-squad__bar" aria-hidden="true"><i style={{ width: `${(player.sfa_pts / maxPlayer) * 100}%` }} /></span>
                    <em>{pts(player.sfa_pts)}</em>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="pf-panel" aria-labelledby="tm-results-title">
          <header className="pf-panel__head"><div><h2 id="tm-results-title">Últimos partidos</h2><p>Del más reciente al más antiguo</p></div></header>
          <ul className="tm-results">
            {[...results].reverse().map((result) => (
              <li key={result.fixture_external_id}>
                <Link to={`/torneos/partido/${result.fixture_external_id}?season=${season}`}>
                  <span className={`tm-form__pill is-${result.outcome ?? 'none'}`}>{result.outcome ? OUTCOME[result.outcome] : '·'}</span>
                  <span className="tm-results__rival">
                    <small>{result.is_home ? 'vs' : 'en'}</small>
                    {result.opponent_logo_url && <img src={result.opponent_logo_url} alt="" width={20} height={20} loading="lazy" />}
                    <strong>{result.opponent_name}</strong>
                  </span>
                  <b>{result.goals_for ?? '-'}–{result.goals_against ?? '-'}</b>
                  <small className="tm-results__date">{shortDate(result.played_at)}</small>
                </Link>
              </li>
            ))}
          </ul>
          {team.squad_score != null && (
            <p className="tm-note">
              Rendimiento de su plantilla en los últimos partidos: <b>{one(team.squad_score)}/100</b> (rendimiento SFA por 90', ajustado por posición).
            </p>
          )}
        </section>
      </div>
    </main>
  )
}
