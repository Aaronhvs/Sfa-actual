import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { Competition, RankedPlayer, SeasonItem } from '../types'
import { fetchRanking, fetchCompetitions, fetchSeasons } from '../api/client'
import RankingFilterSelect, { type RankingFilterOption } from '../components/ranking/RankingFilterSelect'
import { RankingRow, RankingTile } from '../components/ranking/RankingEntries'
import HomeRankingGallery from '../components/HomeRankingGallery'
import { ArrowIcon } from '../components/tournaments/MatchUI'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import WcLiveChip from '../components/shared/WcLiveChip'
import { useCountUp } from '../hooks/useCountUp'
import { isWorldCupSeason } from '../utils/season'
import './RankingPage.css'

const PODIUM_SIZE = 3
const LIST_PAGE_SIZE = 10
const WORLD_CUP_COMPETITION_ID = 350
const SEARCH_DEBOUNCE_MS = 350
const MAIN_COMPETITION_IDS = [10, 1, 3, 6, 7, 9]

const POSITIONS = [
  { value: '', label: 'Todas' },
  { value: 'DEL', label: 'Delanteros' },
  { value: 'EXT', label: 'Extremos' },
  { value: 'MCO', label: 'Mediapuntas' },
  { value: 'MC', label: 'Centrocampistas' },
  { value: 'LAT', label: 'Laterales' },
  { value: 'DC', label: 'Centrales' },
]

const PROFILES: RankingFilterOption[] = [
  { value: '', label: 'Todos los perfiles' },
  { value: 'Promesa', label: 'Promesas' },
  { value: 'Veterano', label: 'Veteranos' },
  { value: 'Goleador', label: 'Goleadores' },
  { value: 'Asistidor', label: 'Asistidores' },
]

function numberParam(value: string | null): number | undefined {
  if (!value) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function pageParam(value: string | null): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed - 1 : 0
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

function buildRankingParams({
  season,
  position,
  bonusFilter,
  competition,
  search,
  page,
  view = 'compact',
}: {
  season: string
  position: string
  bonusFilter: string
  competition?: number
  search: string
  page: number
  view?: string
}) {
  const params = new URLSearchParams()
  if (season) params.set('scope', season)
  if (position) params.set('position', position)
  if (bonusFilter) params.set('bonus_label', bonusFilter)
  if (competition) params.set('competition_id', String(competition))
  if (search.trim()) params.set('name', search.trim())
  if (page > 0) params.set('page', String(page + 1))
  if (view === 'gallery') params.set('view', 'gallery')
  return params
}

export default function RankingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
  // 'gallery' is the legacy URL value for the photo cards; the list is the default view.
  const [view, setView] = useState(searchParams.get('view') === 'gallery' ? 'gallery' : 'compact')
  const [catalogError, setCatalogError] = useState(false)
  const [catalogRetry, setCatalogRetry] = useState(0)
  const [season, setSeason] = useState<string>(searchParams.get('scope') ?? '')
  const [position, setPosition] = useState(searchParams.get('position') ?? '')
  const [bonusFilter, setBonusFilter] = useState(searchParams.get('bonus_label') ?? '')
  const [competition, setCompetition] = useState<number | undefined>(numberParam(searchParams.get('competition_id')))
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [search, setSearch] = useState(searchParams.get('name') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('name') ?? '')
  const [podiumPlayers, setPodiumPlayers] = useState<RankedPlayer[]>([])
  const [listPlayers, setListPlayers] = useState<RankedPlayer[]>([])
  const [totalPlayers, setTotalPlayers] = useState(0)
  const [initialLoading, setInitialLoading] = useState(true)
  const [isContextRefreshing, setIsContextRefreshing] = useState(false)
  const [isListRefreshing, setIsListRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [committedPodiumContext, setCommittedPodiumContext] = useState('')
  const [page, setPage] = useState(pageParam(searchParams.get('page')))
  const [pageDir, setPageDir] = useState<'next' | 'prev'>('next')
  const [committedListKey, setCommittedListKey] = useState('')
  const [committedPage, setCommittedPage] = useState(page)
  const [committedDirection, setCommittedDirection] = useState(pageDir)
  const [retryCount, setRetryCount] = useState(0)
  const lastSearchRef = useRef(search)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasRankingResultRef = useRef(false)
  const committedPodiumContextRef = useRef('')
  const rankingRequestIdRef = useRef(0)
  const isWcSeason = isWorldCupSeason(season, seasonItems)
  const isAllTime = season === 'all'
  const usesPodiumLayout = !debouncedSearch
  const podiumContextKey = [
    season,
    position,
    bonusFilter,
    competition ?? '',
  ].join('|')
  const listOffset = usesPodiumLayout
    ? PODIUM_SIZE + (page * LIST_PAGE_SIZE)
    : page * LIST_PAGE_SIZE
  const listRequestKey = [podiumContextKey, debouncedSearch, page, listOffset].join('|')

  useEffect(() => {
    let active = true
    setCatalogError(false)
    if (!season) setInitialLoading(true)
    fetchSeasons().then(data => {
      if (!active) return
      if (!data.seasons.length) throw new Error('No hay temporadas disponibles')
      setSeasonItems(data.seasons)
      if (!searchParams.get('scope')) {
        const legacySeason = searchParams.get('season')
        const legacyItem = data.seasons.find(item => item.season === legacySeason && (legacySeason !== '2026' || item.kind === 'tournament'))
        const fallback = legacyItem?.key ?? data.seasons.find(item => item.is_latest)?.key ?? data.seasons[0].key
        setSeason(fallback)
        setSearchParams(params => { const next = new URLSearchParams(params); next.set('scope', fallback); next.delete('season'); return next }, { replace: true })
      }
    }).catch(() => {
      if (!active) return
      setCatalogError(true)
      if (!season) setInitialLoading(false)
    })
    return () => { active = false }
  }, [catalogRetry])

  useEffect(() => {
    if (isWcSeason || competitions.length > 0) return
    fetchCompetitions().then(setCompetitions).catch(() => {})
  }, [isWcSeason, competitions.length])

  useEffect(() => {
    if (isWcSeason) {
      document.body.classList.add('mode-tournament')
    } else {
      document.body.classList.remove('mode-tournament')
    }
    return () => {
      document.body.classList.remove('mode-tournament')
    }
  }, [isWcSeason])

  useEffect(() => {
    if (!isWcSeason) return
    setCompetition(undefined)
  }, [isWcSeason])

  useEffect(() => {
    if (!season) return
    setSearchParams(buildRankingParams({
      season,
      position,
      bonusFilter,
      competition,
      search: debouncedSearch,
      page,
      view,
    }), { replace: true })
  }, [season, position, bonusFilter, competition, debouncedSearch, page, view, setSearchParams])

  useEffect(() => {
    if (search === lastSearchRef.current) return
    lastSearchRef.current = search
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setPage(0)
      setPageDir('next')
      setDebouncedSearch(search.trim())
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [search])

  useEffect(() => {
    if (!season) return
    const controller = new AbortController()
    const requestId = ++rankingRequestIdRef.current
    const hasRankingResult = hasRankingResultRef.current
    const hasCurrentPodium = usesPodiumLayout
      && committedPodiumContextRef.current === podiumContextKey

    if (!hasRankingResult) {
      setInitialLoading(true)
    } else if (hasCurrentPodium) {
      setIsListRefreshing(true)
    } else {
      setIsContextRefreshing(true)
    }
    setError(null)
    setRefreshError(null)

    const requestRanking = (limit: number, offset: number) => fetchRanking({
      scope: season,
      position: position || undefined,
      competition_id: competition,
      limit,
      offset,
      name: debouncedSearch || undefined,
      bonus_label: bonusFilter || undefined,
      signal: controller.signal,
    })

    const request = !usesPodiumLayout
      ? requestRanking(LIST_PAGE_SIZE, listOffset).then((data) => ({
          podium: [] as RankedPlayer[],
          list: data.ranking,
          total: data.total,
        }))
      : hasCurrentPodium
        ? requestRanking(LIST_PAGE_SIZE, listOffset).then((data) => ({
            podium: null,
            list: data.ranking,
            total: data.total,
          }))
        : page === 0
          ? requestRanking(PODIUM_SIZE + LIST_PAGE_SIZE, 0).then((data) => ({
              podium: data.ranking.slice(0, PODIUM_SIZE),
              list: data.ranking.slice(PODIUM_SIZE),
              total: data.total,
            }))
          : Promise.all([
              requestRanking(PODIUM_SIZE, 0),
              requestRanking(LIST_PAGE_SIZE, listOffset),
            ]).then(([podiumData, listData]) => ({
              podium: podiumData.ranking,
              list: listData.ranking,
              total: listData.total,
            }))

    request
      .then(({ podium, list, total }) => {
        if (controller.signal.aborted || requestId !== rankingRequestIdRef.current) return
        hasRankingResultRef.current = true
        if (podium !== null) {
          const committedContext = usesPodiumLayout ? podiumContextKey : ''
          committedPodiumContextRef.current = committedContext
          setCommittedPodiumContext(committedContext)
          setPodiumPlayers(podium)
        }
        setListPlayers(list)
        setCommittedListKey(listRequestKey)
        setCommittedPage(page)
        setCommittedDirection(pageDir)
        setTotalPlayers(total)
        setInitialLoading(false)
        setIsContextRefreshing(false)
        setIsListRefreshing(false)
      })
      .catch((requestError: unknown) => {
        if (isAbortError(requestError) || requestId !== rankingRequestIdRef.current) return
        const message = requestError instanceof Error
          ? requestError.message
          : 'Error al cargar el ranking'
        if (hasRankingResult) {
          setRefreshError(message)
        } else {
          setError(message)
        }
        setInitialLoading(false)
        setIsContextRefreshing(false)
        setIsListRefreshing(false)
      })

    return () => {
      controller.abort()
    }
  }, [
    bonusFilter,
    competition,
    debouncedSearch,
    listOffset,
    listRequestKey,
    page,
    podiumContextKey,
    position,
    season,
    usesPodiumLayout,
    retryCount,
  ])

  const showHero = usesPodiumLayout && podiumPlayers.length > 0
  const top3 = showHero ? podiumPlayers : []
  const currentPagePlayers = listPlayers
  const listBusy = isContextRefreshing || isListRefreshing
    || (hasRankingResultRef.current && committedListKey !== listRequestKey && !refreshError)
  const visiblePage = refreshError ? committedPage : page
  const visibleOffset = usesPodiumLayout
    ? PODIUM_SIZE + visiblePage * LIST_PAGE_SIZE
    : visiblePage * LIST_PAGE_SIZE
  const visibleTotalPlayers = usesPodiumLayout
    ? Math.max(totalPlayers - PODIUM_SIZE, 0)
    : totalPlayers
  const totalPages = visibleTotalPlayers > 0 ? Math.ceil(visibleTotalPlayers / LIST_PAGE_SIZE) : 0
  const hasNextPage = visiblePage + 1 < totalPages
  const hasPrevPage = visiblePage > 0
  const visibleRangeStart = totalPlayers > 0 && currentPagePlayers.length > 0
    ? visibleOffset + 1
    : 0
  const visibleRangeEnd = totalPlayers > 0
    ? Math.min(visibleOffset + currentPagePlayers.length, totalPlayers)
    : 0

  const mainCompetitions = competitions
    .filter((c) => MAIN_COMPETITION_IDS.includes(c.id))
    .sort((a, b) => MAIN_COMPETITION_IDS.indexOf(a.id) - MAIN_COMPETITION_IDS.indexOf(b.id))
  const competitionOptions: RankingFilterOption[] = [
    { value: '', label: 'Todas las competiciones' },
    ...mainCompetitions.map((item) => ({ value: String(item.id), label: item.name })),
  ]

  const activeComp = competitions.find((c) => c.id === competition)
  const seasonLabel = seasonItems.find((item) => item.key === season)?.label ?? (isAllTime ? 'Total histórico' : '')
  const hasFilters = Boolean(position || bonusFilter || competition || search)
  const rankingReturnTo = `/ranking?${buildRankingParams({
    season,
    position,
    bonusFilter,
    competition,
    search: debouncedSearch,
    page,
    view,
  }).toString()}`
  const playerHref = (id: number) => `/player/${id}?${new URLSearchParams({ scope: season, returnTo: rankingReturnTo })}`

  const animatedTotal = useCountUp(totalPlayers)
  function resetListPage() {
    setPage(0)
    setPageDir('next')
  }

  function changePosition(nextPosition: string) {
    resetListPage()
    setPosition(nextPosition)
  }

  function changeBonusFilter(nextBonusFilter: string) {
    resetListPage()
    setBonusFilter(nextBonusFilter)
  }

  function changeCompetition(nextCompetition?: number) {
    resetListPage()
    setCompetition(nextCompetition)
  }

  function resetFilters() {
    resetListPage()
    setPosition('')
    setBonusFilter('')
    setCompetition(undefined)
    setSearch('')
    setDebouncedSearch('')
  }

  function goNext() {
    if (!hasNextPage) return
    setPageDir('next')
    setPage(visiblePage + 1)
  }

  function goPrev() {
    if (!hasPrevPage) return
    setPageDir('prev')
    setPage(visiblePage - 1)
  }

  function goToPage(nextPage: number) {
    if (nextPage === visiblePage) return
    setPageDir(nextPage > page ? 'next' : 'prev')
    setPage(nextPage)
  }

  const visiblePages = Array.from({ length: totalPages }, (_, index) => index)
    .filter((index) => (
      index === 0
      || index === totalPages - 1
      || Math.abs(index - visiblePage) <= 1
    ))

  const listTitle = debouncedSearch
    ? `Resultados para “${debouncedSearch}”`
    : 'Clasificación completa'

  return (
    <main className={`rk-page${isWcSeason ? ' rk-page--wc' : ''}`}>
      <header className="rk-head">
        <div>
          <p className="tp-eyebrow">
            {seasonLabel ? `Temporada ${seasonLabel}` : 'Ranking'}
            {totalPlayers > 0 && ` · ${animatedTotal.toLocaleString('es-ES')} jugadores puntuados`}
          </p>
          <h1>{isWcSeason ? 'Ranking del Mundial' : 'Ranking SFA'}</h1>
        </div>
        <Link to="/metodologia" className="rk-head__link">Cómo se calculan los puntos <ArrowIcon /></Link>
      </header>

      <section className="rk-toolbar" aria-label="Filtros del ranking">
        <div className="rk-toolbar__row">
          {seasonItems.length > 0 && (
            <SeasonDropdown
              items={seasonItems}
              value={season}
              onChange={(nextSeason) => {
                resetListPage()
                setSeason(nextSeason)
              }}
              includeAll={true}
            />
          )}
          <label className="rk-search">
            <span className="sr-only">Buscar jugador o equipo</span>
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <circle cx="6.5" cy="6.5" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10.5 10.5 14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input type="search" placeholder="Buscar jugador o equipo" value={search} onChange={(event) => setSearch(event.target.value)} />
            {search && <button type="button" onClick={() => setSearch('')} aria-label="Limpiar búsqueda">×</button>}
          </label>
          <RankingFilterSelect label="Perfil" ariaLabel="Filtrar por perfil" value={bonusFilter} options={PROFILES} onChange={changeBonusFilter} />
          {!isWcSeason && (
            <RankingFilterSelect
              label="Competición"
              ariaLabel="Filtrar por competición"
              value={competition === undefined ? '' : String(competition)}
              options={competitionOptions}
              onChange={(next) => changeCompetition(next ? Number(next) : undefined)}
            />
          )}
        </div>
        <div className="rk-toolbar__row rk-toolbar__row--positions">
          <span className="rk-positions__label" aria-hidden="true">Posición</span>
          <div className="tp-segment rk-positions" role="group" aria-label="Filtrar por posición">
            {POSITIONS.map(({ value, label }) => (
              <button type="button" key={value || 'all'} className={position === value ? 'is-active' : undefined} aria-pressed={position === value} onClick={() => changePosition(value)}>
                {label}
              </button>
            ))}
          </div>
          {hasFilters && <button type="button" className="rk-reset" onClick={resetFilters}>Restablecer filtros</button>}
        </div>
        {(listBusy || refreshError) && (
          <p className="rk-status" role="status">
            {refreshError ? 'No se pudieron aplicar los filtros. Se conservan los resultados anteriores.' : 'Actualizando resultados…'}
            {refreshError && <button type="button" onClick={() => setRetryCount((value) => value + 1)}>Reintentar</button>}
          </p>
        )}
      </section>

      {catalogError && (
        <div className="rk-state" role="alert">
          <strong>No pudimos cargar las temporadas.</strong>
          <button type="button" onClick={() => setCatalogRetry((value) => value + 1)}>Reintentar</button>
        </div>
      )}
      {isWcSeason && <div className="rk-wc"><WcLiveChip /></div>}

      {initialLoading && (
        <div className="rk-skeleton" role="status">
          <span className="sr-only">Cargando ranking</span>
          <div className="rk-skel rk-skel--podium" />
          <div className="rk-skel rk-skel--list" />
        </div>
      )}

      {!initialLoading && error && (
        <div className="rk-state" role="alert">
          <strong>No pudimos cargar el ranking.</strong>
          <button type="button" onClick={() => setRetryCount((value) => value + 1)}>Reintentar</button>
        </div>
      )}

      {season && !initialLoading && !error && (
        <>
          {showHero && (
            <section className="rk-podium sfa-podium" aria-label="Podio del ranking" aria-busy={isContextRefreshing}>
              <HomeRankingGallery key={committedPodiumContext} players={top3} playerUrl={playerHref} />
            </section>
          )}

          <section className="rk-list" aria-labelledby="rk-list-title" aria-busy={listBusy}>
            <header className="rk-list__head">
              <div>
                <h2 id="rk-list-title">{listTitle}</h2>
                <p>
                  {visibleRangeStart > 0 ? `${visibleRangeStart}–${visibleRangeEnd} de ${totalPlayers.toLocaleString('es-ES')} jugadores` : 'Sin jugadores'}
                  {activeComp && ` · ${activeComp.name}`}
                </p>
              </div>
              <div className="tp-segment" role="group" aria-label="Formato de la clasificación">
                <button type="button" className={view === 'compact' ? 'is-active' : undefined} aria-pressed={view === 'compact'} onClick={() => setView('compact')}>Lista</button>
                <button type="button" className={view === 'gallery' ? 'is-active' : undefined} aria-pressed={view === 'gallery'} onClick={() => setView('gallery')}>Fichas</button>
              </div>
            </header>

            {currentPagePlayers.length === 0 && !listBusy ? (
              <div className="rk-state">
                <strong>
                  {search
                    ? `Sin resultados para “${search}”`
                    : showHero ? 'Los primeros puestos reúnen todos los resultados de estos filtros.' : 'Sin jugadores para los filtros seleccionados.'}
                </strong>
                {hasFilters && <button type="button" onClick={resetFilters}>Restablecer filtros</button>}
              </div>
            ) : (
              <>
                <div className={`rk-list__body${listBusy ? ' is-loading' : ''}`}>
                  {view === 'gallery' ? (
                    <div key={committedListKey} aria-hidden={listBusy || undefined} className={`rk-tiles is-${committedDirection}`}>
                      {currentPagePlayers.map((player) => (
                        <RankingTile key={player.id} player={player} href={playerHref(player.id)} isWorldCup={isWcSeason} />
                      ))}
                    </div>
                  ) : (
                    // Two half-page columns on desktop (4–8 | 9–13); they stack into one list on narrow screens.
                    <div key={committedListKey} aria-hidden={listBusy || undefined} className={`rk-columns is-${committedDirection}`}>
                      {[currentPagePlayers.slice(0, Math.ceil(currentPagePlayers.length / 2)), currentPagePlayers.slice(Math.ceil(currentPagePlayers.length / 2))]
                        .filter((column) => column.length > 0)
                        .map((column, index) => (
                          <div className="tp-group rk-rows" key={index}>
                            <div className="rk-rows__head" aria-hidden="true">
                              <span>#</span><span>Jugador</span><span>G</span><span>A</span><span>PJ</span><span>Pts SFA</span>
                            </div>
                            {column.map((player) => (
                              <RankingRow key={player.id} player={player} href={playerHref(player.id)} isWorldCup={isWcSeason} />
                            ))}
                          </div>
                        ))}
                    </div>
                  )}
                </div>

                {totalPages > 1 && (
                  <nav className="rk-pager" aria-label="Páginas del ranking">
                    <button type="button" className="rk-pager__step" onClick={goPrev} disabled={!hasPrevPage || listBusy} aria-label="Página anterior">
                      <ArrowIcon direction="left" />
                    </button>
                    <ol>
                      {visiblePages.map((pageIndex, index) => {
                        const previousVisible = visiblePages[index - 1]
                        const needsGap = previousVisible != null && pageIndex - previousVisible > 1
                        return (
                          <li key={pageIndex}>
                            {needsGap && <span className="rk-pager__gap" aria-hidden="true">…</span>}
                            <button
                              type="button"
                              className={pageIndex === visiblePage ? 'is-active' : undefined}
                              disabled={listBusy}
                              onClick={() => goToPage(pageIndex)}
                              aria-label={`Página ${pageIndex + 1}`}
                              aria-current={pageIndex === visiblePage ? 'page' : undefined}
                            >
                              {pageIndex + 1}
                            </button>
                          </li>
                        )
                      })}
                    </ol>
                    <button type="button" className="rk-pager__step" onClick={goNext} disabled={!hasNextPage || listBusy} aria-label="Página siguiente">
                      <ArrowIcon />
                    </button>
                  </nav>
                )}
              </>
            )}
          </section>
        </>
      )}
    </main>
  )
}
