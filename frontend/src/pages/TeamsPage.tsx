import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchCompetitions, fetchSeasons, fetchTeamRanking } from '../api/client'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import type { Competition, SeasonItem } from '../types'
import type { RankedTeam, TeamRankingResponse } from '../types/teamRanking'
import './TeamsPage.css'

function score(value: number | null) {
  return value == null ? '-' : value.toLocaleString('es-ES', { maximumFractionDigits: 1 })
}

function seasonLabel(season: string) {
  return `${season}/${Number(season.slice(0, 4)) + 1}`
}

function TeamSource({ team, season }: { team: RankedTeam; season: string }) {
  const historical = (team.elo_season && team.elo_season !== season) || (team.squad_season && team.squad_season !== season)
  const partial = team.elo_raw == null || team.squad_score == null || (team.coverage != null && team.coverage < 0.8)
  return <span className={`teams-source${historical || partial ? ' teams-source--partial' : ''}`}>
    {team.score == null ? 'Sin datos' : historical ? 'Referencia anterior' : partial ? 'Datos parciales' : 'Temporada actual'}
  </span>
}

export default function TeamsPage() {
  const [params, setParams] = useSearchParams()
  const [seasons, setSeasons] = useState<SeasonItem[]>([])
  const [scope, setScope] = useState(params.get('scope') ?? '')
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [competition, setCompetition] = useState(params.get('competition_id') ?? '')
  const [search, setSearch] = useState(params.get('name') ?? '')
  const [query, setQuery] = useState(search)
  const [page, setPage] = useState(Math.max(1, Number(params.get('page')) || 1))
  const [data, setData] = useState<TeamRankingResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const lastSearch = useRef(search)

  useEffect(() => {
    let active = true
    fetchSeasons().then((result) => {
      if (!active) return
      const items = result.seasons.filter((item) => item.kind === 'award_period')
      setSeasons(items)
      if (!scope) setScope((items.find((item) => item.is_latest) ?? items[0])?.key ?? '')
    }).catch(() => { if (active) { setError('No se pudieron cargar las temporadas.'); setLoading(false) } })
    fetchCompetitions().then((items) => { if (active) setCompetitions(items.filter((item) => [10, 1, 3, 6, 7, 9].includes(item.id))) }).catch(() => {})
    return () => { active = false }
  }, [retry])

  useEffect(() => {
    if (search === lastSearch.current) return
    lastSearch.current = search
    const timer = setTimeout(() => { setQuery(search.trim()); setPage(1) }, 300)
    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    if (!scope) return
    const controller = new AbortController()
    setLoading(true)
    setError('')
    fetchTeamRanking({ scope, competition_id: competition ? Number(competition) : undefined, name: query || undefined, page, signal: controller.signal })
      .then((result) => { if (!controller.signal.aborted) setData(result) })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudo cargar el ranking de equipos.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    const next = new URLSearchParams({ scope })
    if (query) next.set('name', query)
    if (competition) next.set('competition_id', competition)
    if (page > 1) next.set('page', String(page))
    setParams(next, { replace: true })
    return () => controller.abort()
  }, [scope, competition, query, page, retry, setParams])

  return (
    <div className="teams-page">
      <header className="teams-header">
        <div><span className="teams-eyebrow">ELO + rendimiento individual</span><h1>Ranking de equipos</h1></div>
        {seasons.length > 0 && <SeasonDropdown items={seasons} value={scope} includeAll={false} onChange={(value) => { setScope(value); setPage(1) }} />}
      </header>
      <div className="teams-context">
        <div><span>Índice de equipos</span><strong>Edición experimental</strong></div>
        <div><span>Ventana de rendimiento</span><strong>Últimos {data?.model.recent_matches ?? 10} partidos</strong></div>
        <div><span>Componentes de referencia</span><strong>{Math.round((data?.model.elo_weight ?? 0.8) * 100)}% ELO <i>/</i> {Math.round((data?.model.squad_weight ?? 0.2) * 100)}% SFA</strong></div>
      </div>
      <div className="teams-toolbar">
        <label className="teams-search"><span>Buscar equipo</span><input type="search" value={search} placeholder="Nombre del equipo" onChange={(event) => setSearch(event.target.value)} /></label>
        <label className="teams-competition"><span>Competición</span><select value={competition} onChange={(event) => { setCompetition(event.target.value); setPage(1) }}><option value="">Todas las competiciones</option>{competitions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <span className="teams-count">{data ? `${data.total} equipos` : '-'}</span>
      </div>
      {data?.model.data_cutoff && <p className="teams-data-date">Partidos puntuados hasta el {new Date(data.model.data_cutoff).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</p>}
      {error && <div className="teams-error" role="alert">{error}<button onClick={() => setRetry((value) => value + 1)}>Reintentar</button></div>}
      <div className={`teams-results${loading ? ' is-loading' : ''}`} aria-busy={loading}>
        {loading && <div className="teams-loader" role="status"><span className="rp-list-loader__spinner" aria-hidden="true" /><span>Cargando equipos</span></div>}
        <div className="teams-table-scroll">
          <table className="teams-table">
            <caption className="sr-only">Ranking de equipos por índice descriptivo ELO y SFA individual</caption>
            <thead><tr><th scope="col">#</th><th scope="col">Equipo</th><th scope="col">Índice</th><th scope="col">ELO</th><th scope="col">SFA individual</th><th scope="col">Cobertura</th></tr></thead>
            <tbody>{data?.ranking.map((team) => <tr key={team.id}>
              <td className="teams-rank">{team.score == null ? '-' : team.rank}</td>
              <td><div className="teams-identity">{team.team_logo_url ? <img src={team.team_logo_url} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.visibility = 'hidden' }} /> : <span className="teams-logo-placeholder" />}
                <div><Link to={`/ranking?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(team.name)}`} title={`Buscar jugadores de ${team.name}`}>{team.name}</Link><span>{team.competition}</span><TeamSource team={team} season={data.season} /></div>
              </div></td>
              <td className="teams-index"><strong>{score(team.score)}</strong><span className="teams-index-track" aria-hidden="true"><i style={{ transform: `scaleX(${(team.score ?? 0) / 100})` }} /></span>
                {team.score != null && (team.effective_elo_weight === 0 || team.effective_squad_weight === 0) && <small>Solo {team.effective_elo_weight === 0 ? 'SFA' : 'ELO'}</small>}
              </td>
              <td className="teams-component"><strong>{score(team.elo_raw)}</strong><span>{team.elo_season ? seasonLabel(team.elo_season) : 'Sin ELO'}{team.elo_source === 'manual_override' ? ' · Semilla manual' : ''}</span></td>
              <td className="teams-component"><strong>{score(team.squad_score)}<small>{team.squad_score != null ? '/100' : ''}</small></strong><span>{team.squad_season ? seasonLabel(team.squad_season) : 'Sin puntuaciones'}</span></td>
              <td className="teams-component"><strong>{team.coverage == null ? '-' : `${Math.round(team.coverage * 100)}%`}</strong><span>{team.scored_appearances}/{team.observed_appearances} actuaciones</span></td>
            </tr>)}</tbody>
          </table>
          {!loading && !error && data?.ranking.length === 0 && <div className="teams-empty">No hay equipos para estos filtros.</div>}
        </div>
      </div>
      {data && data.pagination.total_pages > 1 && <nav className="teams-pagination" aria-label="Páginas de equipos">
        <button disabled={!data.pagination.has_prev || loading} onClick={() => setPage(data.pagination.page - 1)}>Anterior</button>
        <span>Página {data.pagination.page} de {data.pagination.total_pages}</span>
        <button disabled={!data.pagination.has_next || loading} onClick={() => setPage(data.pagination.page + 1)}>Siguiente</button>
      </nav>}
      <details className="teams-method"><summary>Datos y criterio del índice</summary>
        <p>Índice descriptivo de 0 a 100: ELO y rendimiento SFA individual por 90 minutos, normalizado por posición y ponderado por minutos. Las muestras pequeñas se acercan a la referencia de su posición. No incluye bonus colectivos ni modifica los puntos de los jugadores.</p>
        <p>La cobertura indica actuaciones con puntuación entre las actuaciones registradas, no disponibilidad de la plantilla. Si falta un componente, el índice usa el disponible; si falta información actual, puede recurrir a la temporada anterior. Los componentes utilizados se indican en cada fila.</p>
        <p>Los pesos son una primera referencia experimental, no una predicción calibrada. El SFA observado conserva su contexto de partido: este índice no se utiliza para calcular M1. La fecha de cálculo no garantiza la actualización del ELO.</p>
        {data?.model.data_cutoff && <small>Último partido puntuado de la muestra: {new Date(data.model.data_cutoff).toLocaleDateString('es-ES')}</small>}
        {data && <small>Modelo {data.model.version} · Calculado {new Date(data.model.as_of).toLocaleString('es-ES')} · {data.model.population_teams} equipos de referencia</small>}
      </details>
    </div>
  )
}
