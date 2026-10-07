import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import type { RankedTeam, TeamRecentResult } from '../../types/teamRanking'

export function teamScore(value: number | null) {
  return value == null ? '-' : value.toLocaleString('es-ES', { maximumFractionDigits: 1 })
}

const outcomes = { W: { letter: 'G', label: 'Victoria' }, D: { letter: 'E', label: 'Empate' }, L: { letter: 'P', label: 'Derrota' } }

function displayedOutcome(result: TeamRecentResult) {
  return result.status === 'PEN' ? null : result.outcome
}

function resultLabel(result: TeamRecentResult) {
  const knownOutcome = displayedOutcome(result)
  const outcome = knownOutcome ? outcomes[knownOutcome].label : result.status === 'PEN' ? 'Ganador por penaltis no disponible' : 'Resultado incompleto'
  const goals = result.goals_for == null || result.goals_against == null ? '' : `, ${result.goals_for}-${result.goals_against}`
  const penalties = result.status === 'PEN' ? ', definido en penaltis' : ''
  return `${outcome}${goals} ante ${result.opponent_name}, ${result.is_home ? 'local' : 'visitante'}${penalties}, ${new Date(result.played_at).toLocaleDateString('es-ES')}`
}

function TeamForm({ results }: { results: TeamRecentResult[] }) {
  if (!results.length) return <span className="teams-unavailable">Sin resultados registrados</span>
  return <div className="teams-form" aria-label="Últimos resultados, del más antiguo al más reciente">
    {results.map((result, index) => <Link key={result.fixture_external_id}
      to={`/torneos/partido/${result.fixture_external_id}`}
      className={`teams-form-mark teams-form-mark--${displayedOutcome(result) ?? 'unknown'}${index === results.length - 1 ? ' is-latest' : ''}`}
      title={resultLabel(result)} aria-label={resultLabel(result)}>
      {displayedOutcome(result) ? outcomes[displayedOutcome(result)!].letter : '-'}
    </Link>)}
  </div>
}

function seasonLabel(season: string) {
  const year = Number(season.slice(0, 4))
  return `${year}/${year + 1}`
}

export default function TeamRankingRow({ team, season, scope, expanded, onToggle }: {
  team: RankedTeam; season: string; scope: string; expanded: boolean; onToggle: () => void
}) {
  const results = team.recent_results ?? []
  const player = team.featured_player
  const historical = (team.elo_season && team.elo_season !== season) || (team.squad_season && team.squad_season !== season)
  const partial = team.elo_raw == null || team.squad_score == null
  const detailId = `team-details-${team.id}`
  return <Fragment>
    <tr className={`teams-row${expanded ? ' is-expanded' : ''}${team.rank <= 3 && team.score != null ? ' is-leading' : ''}`}>
      <td className="teams-rank">{team.score == null ? '-' : team.rank}</td>
      <td className="teams-team-cell"><div className="teams-identity">
        {team.team_logo_url ? <img src={team.team_logo_url} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.visibility = 'hidden' }} /> : <span className="teams-logo-placeholder" />}
        <div><Link to={`/ranking?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(team.name)}`} title={`Buscar jugadores de ${team.name}`}>{team.name}</Link><span>{team.competition}</span>
          {(team.score == null || historical || partial) && <span className="teams-source">{team.score == null ? 'Sin puntuación' : historical ? 'Incluye temporada anterior' : 'Datos parciales'}</span>}
        </div>
      </div></td>
      <td className="teams-form-cell"><span className="teams-mobile-label">Últimos resultados</span><TeamForm results={results} /></td>
      <td className="teams-featured-cell"><span className="teams-mobile-label">Jugador destacado</span>
        {player ? <Link className="teams-featured" to={`/player/${player.id}?scope=${encodeURIComponent(scope)}`} title={`Mayor aporte SFA registrado en los últimos diez partidos: ${player.name}`}>
          {player.photo_url ? <img src={player.photo_url} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.visibility = 'hidden' }} /> : <span className="teams-player-placeholder" aria-hidden="true">{player.name.charAt(0)}</span>}
          <span><strong>{player.name}</strong><small>{Math.round(player.individual_points).toLocaleString('es-ES')} pts SFA</small></span>
        </Link> : <span className="teams-unavailable">Sin actuaciones puntuadas</span>}
      </td>
      <td className="teams-index"><strong>{teamScore(team.score)}</strong><small>/100</small></td>
      <td className="teams-expand-cell"><button className="teams-expand" aria-expanded={expanded} aria-controls={detailId} aria-label={`${expanded ? 'Cerrar' : 'Ver'} detalle de ${team.name}`} title={`${expanded ? 'Cerrar' : 'Ver'} detalle`} onClick={onToggle}>{expanded ? '-' : '+'}</button></td>
    </tr>
    {expanded && <tr className="teams-detail-row"><td colSpan={6}><div className="teams-detail" id={detailId}>
      <section className="teams-detail-results" aria-label={`Resultados de ${team.name}`}>
        <h2>Últimos partidos</h2>
        {results.length ? [...results].reverse().map((result) => <Link className="teams-match" key={result.fixture_external_id} to={`/torneos/partido/${result.fixture_external_id}`}>
          <span className={`teams-form-mark teams-form-mark--${displayedOutcome(result) ?? 'unknown'}`}>{displayedOutcome(result) ? outcomes[displayedOutcome(result)!].letter : '-'}</span>
          <time dateTime={result.played_at}>{new Date(result.played_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}</time>
          {result.opponent_logo_url && <img src={result.opponent_logo_url} alt="" loading="lazy" />}
          <span className="teams-match-opponent">{result.opponent_name}<small>{result.is_home ? 'Local' : 'Visitante'}{result.status === 'PEN' ? ' · Penaltis · Ganador no disponible' : ''}</small></span>
          <strong>{result.goals_for ?? '-'} : {result.goals_against ?? '-'}</strong>
        </Link>) : <p className="teams-unavailable">Sin partidos finalizados registrados en esta temporada.</p>}
      </section>
      <section className="teams-detail-data" aria-label={`Datos de ${team.name}`}>
        <h2>Detrás de la puntuación</h2>
        <dl>
          <div><dt>Nivel competitivo <small>ELO</small></dt><dd>{teamScore(team.elo_raw)}<small>{team.elo_season ? seasonLabel(team.elo_season) : 'Sin datos'}{team.elo_source === 'manual_override' ? ' · Semilla manual' : ''}</small></dd></div>
          <div><dt>Jugadores de campo <small>Rendimiento SFA normalizado</small></dt><dd>{teamScore(team.squad_score)}{team.squad_score != null && <span>/100</span>}<small>{team.squad_season ? seasonLabel(team.squad_season) : 'Sin datos'}</small></dd></div>
        </dl>
        <p>{Math.round(team.effective_elo_weight * 100)}% nivel competitivo · {Math.round(team.effective_squad_weight * 100)}% rendimiento individual</p>
        {team.squad_data_cutoff && <p>Actuaciones puntuadas hasta el {new Date(team.squad_data_cutoff).toLocaleDateString('es-ES')}.</p>}
      </section>
    </div></td></tr>}
  </Fragment>
}
