import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchCompetitions, fetchSeasons, fetchTeamRanking } from '../api/client'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import TeamRankingRow from '../components/ranking/TeamRankingRow'
import type { Competition, SeasonItem } from '../types'
import type { TeamRankingResponse } from '../types/teamRanking'
import './TeamsPage.css'

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
  const [expandedTeam, setExpandedTeam] = useState<number | null>(null)
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
    setExpandedTeam(null)
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
        <div><span className="teams-eyebrow">Clubes · Clasificación SFA</span><h1>Ranking de equipos</h1></div>
        {seasons.length > 0 && <SeasonDropdown items={seasons} value={scope} includeAll={false} onChange={(value) => { setScope(value); setPage(1) }} />}
      </header>
      <div className="teams-summary"><span className="teams-edition">Edición experimental</span><span>Nivel competitivo + impacto de sus jugadores</span><span className="teams-scale">Puntuación relativa <strong>0–100</strong></span></div>
      <div className="teams-toolbar">
        <label className="teams-search"><span>Buscar equipo</span><input type="search" value={search} placeholder="Nombre del equipo" onChange={(event) => setSearch(event.target.value)} /></label>
        <label className="teams-competition"><span>Competición</span><select value={competition} onChange={(event) => { setCompetition(event.target.value); setPage(1) }}><option value="">Todas las competiciones</option>{competitions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <span className="teams-count">{data ? `${data.total} ${data.total === 1 ? 'equipo' : 'equipos'}` : '-'}</span>
      </div>
      <div className="teams-list-meta">
        <div className="teams-form-legend" aria-label="Leyenda de resultados"><span><i className="teams-form-mark--W">G</i> Ganado</span><span><i className="teams-form-mark--D">E</i> Empatado</span><span><i className="teams-form-mark--L">P</i> Perdido</span></div>
        {data?.model.data_cutoff && <p className="teams-data-date">Puntos hasta el {new Date(data.model.data_cutoff).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</p>}
      </div>
      {error && <div className="teams-error" role="alert">{error}<button onClick={() => setRetry((value) => value + 1)}>Reintentar</button></div>}
      <div className={`teams-results${loading ? ' is-loading' : ''}`} aria-busy={loading}>
        {loading && <div className="teams-loader" role="status"><span className="rp-list-loader__spinner" aria-hidden="true" /><span>Cargando equipos</span></div>}
        <div className="teams-table-scroll">
          <table className="teams-table">
            <caption className="sr-only">Ranking SFA de equipos, resultados recientes y jugador con mayor aporte registrado</caption>
            <thead><tr><th scope="col">#</th><th scope="col">Equipo</th><th scope="col">Últimos 5 resultados</th><th scope="col">Jugador destacado <small>Últimos 10 partidos</small></th><th scope="col" title="Índice relativo de nivel competitivo y rendimiento individual, no puntos acumulados">Puntuación SFA</th><th scope="col"><span className="sr-only">Detalle</span></th></tr></thead>
            <tbody>{data?.ranking.map((team) => <TeamRankingRow key={team.id} team={team} season={data.season} scope={scope} expanded={expandedTeam === team.id} onToggle={() => setExpandedTeam((current) => current === team.id ? null : team.id)} />)}</tbody>
          </table>
          {!loading && !error && data?.ranking.length === 0 && <div className="teams-empty">No hay equipos para estos filtros.</div>}
        </div>
      </div>
      {data && data.pagination.total_pages > 1 && <nav className="teams-pagination" aria-label="Páginas de equipos">
        <button disabled={!data.pagination.has_prev || loading} onClick={() => setPage(data.pagination.page - 1)}>Anterior</button>
        <span>Página {data.pagination.page} de {data.pagination.total_pages}</span>
        <button disabled={!data.pagination.has_next || loading} onClick={() => setPage(data.pagination.page + 1)}>Siguiente</button>
      </nav>}
      <details className="teams-method"><summary>Criterio de la clasificación</summary>
        <p>La puntuación relativa combina {Math.round((data?.model.elo_weight ?? 0.8) * 100)}% de nivel competitivo (ELO) y {Math.round((data?.model.squad_weight ?? 0.2) * 100)}% de rendimiento individual en los últimos {data?.model.recent_matches ?? 10} partidos finalizados. No equivale a puntos de liga ni a probabilidad de victoria.</p>
        <p>El jugador destacado es quien más puntos SFA individuales ha aportado en esa muestra del equipo durante la temporada seleccionada. La racha va del partido más antiguo al más reciente; el detalle muestra el más reciente primero. No consta un ganador fiable de las tandas de penaltis, por lo que esos partidos aparecen sin letra de victoria o derrota.</p>
        <p>Índice descriptivo de 0 a 100: ELO y rendimiento SFA individual por 90 minutos, normalizado por posición y ponderado por minutos. Las muestras pequeñas se acercan a la referencia de su posición. No incluye bonus colectivos ni modifica los puntos de los jugadores.</p>
        <p>La cobertura indica actuaciones con puntuación entre las actuaciones registradas, no disponibilidad de la plantilla. Si falta un componente, el índice usa el disponible; si falta información actual, puede recurrir a la temporada anterior. Los componentes utilizados se indican en cada fila.</p>
        <p>Los pesos son una primera referencia experimental, no una predicción calibrada. El SFA observado conserva su contexto de partido: este índice no se utiliza para calcular M1. La fecha de cálculo no garantiza la actualización del ELO.</p>
        {data?.model.data_cutoff && <small>Último partido puntuado de la muestra: {new Date(data.model.data_cutoff).toLocaleDateString('es-ES')}</small>}
        {data && <small>Modelo {data.model.version} · Calculado {new Date(data.model.as_of).toLocaleString('es-ES')} · {data.model.population_teams} equipos de referencia</small>}
      </details>
    </div>
  )
}
