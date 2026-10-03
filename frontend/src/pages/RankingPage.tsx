import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { Competition, RankedPlayer, RankingPlayerExplanation, SeasonItem } from '../types'
import { fetchRanking, fetchCompetitions, fetchRankingExplanations, fetchSeasons } from '../api/client'
import FilterBar from '../components/ranking/FilterBar'
import RankingCard from '../components/ranking/RankingCard'
import RankingExplanationModal from '../components/ranking/RankingExplanationModal'
import ShowcaseCard from '../components/ranking/ShowcaseCard'
import TopRankingNarrativeCarousel from '../components/ranking/TopRankingNarrativeCarousel'
import SeasonDropdown from '../components/shared/SeasonDropdown'
import WorldCupPageHeader from '../components/shared/WorldCupPageHeader'
import WcLiveChip from '../components/shared/WcLiveChip'
import { useCountUp } from '../hooks/useCountUp'
import { isWorldCupSeason } from '../utils/season'

const PODIUM_SIZE = 3
const LIST_PAGE_SIZE = 10
const WORLD_CUP_COMPETITION_ID = 350
const SEARCH_DEBOUNCE_MS = 350
const MAIN_COMPETITION_IDS = [10, 1, 3, 6, 7, 9]
const WORLD_CUP_POSITION_OPTIONS = ['DEL', 'EXT', 'MCO', 'MC', 'LAT', 'DC']
const BONUS_FILTER_OPTIONS = ['Promesa', 'Veterano', 'Goleador', 'Asistidor']

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
}: {
  season: string
  position: string
  bonusFilter: string
  competition?: number
  search: string
  page: number
}) {
  const params = new URLSearchParams()
  if (season) params.set('scope', season)
  if (position) params.set('position', position)
  if (bonusFilter) params.set('bonus_label', bonusFilter)
  if (competition) params.set('competition_id', String(competition))
  if (search.trim()) params.set('name', search.trim())
  if (page > 0) params.set('page', String(page + 1))
  return params
}

export default function RankingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
  const [season, setSeason] = useState<string>(searchParams.get('scope') ?? '')
  const [position, setPosition] = useState(searchParams.get('position') ?? '')
  const [bonusFilter, setBonusFilter] = useState(searchParams.get('bonus_label') ?? '')
  const [competition, setCompetition] = useState<number | undefined>(numberParam(searchParams.get('competition_id')))
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [search, setSearch] = useState(searchParams.get('name') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('name') ?? '')
  const [podiumPlayers, setPodiumPlayers] = useState<RankedPlayer[]>([])
  const [listPlayers, setListPlayers] = useState<RankedPlayer[]>([])
  const [rankingExplanations, setRankingExplanations] = useState<RankingPlayerExplanation[]>([])
  const [selectedAnalysis, setSelectedAnalysis] = useState<RankingPlayerExplanation | null>(null)
  const [totalPlayers, setTotalPlayers] = useState(0)
  const [initialLoading, setInitialLoading] = useState(true)
  const [isContextRefreshing, setIsContextRefreshing] = useState(false)
  const [isListRefreshing, setIsListRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [committedPodiumContext, setCommittedPodiumContext] = useState('')
  const [page, setPage] = useState(pageParam(searchParams.get('page')))
  const [pageDir, setPageDir] = useState<'next' | 'prev'>('next')
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasRankingResultRef = useRef(false)
  const committedPodiumContextRef = useRef('')
  const rankingRequestIdRef = useRef(0)
  const explanationRequestIdRef = useRef(0)
  const isWcSeason = isWorldCupSeason(season, seasonItems)
  const selectedSeasonItem = seasonItems.find((item) => item.key === season)
  const isAllTime = season === 'all'
  const explanationScope = isAllTime ? 'all_time' : isWcSeason ? 'world_cup' : 'award_period'
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
  const narrativePlayerIds = podiumPlayers.map((player) => player.id)
  const narrativePlayerIdsKey = narrativePlayerIds.join(',')

  useEffect(() => {
    fetchSeasons()
      .then((data) => {
        setSeasonItems(data.seasons)
        const fromUrl = searchParams.get('scope')
        const legacySeason = searchParams.get('season')
        if (!fromUrl) {
          const legacyItem = legacySeason
            ? data.seasons.find((item) => (
              item.season === legacySeason
              && (legacySeason !== '2026' || item.kind === 'tournament')
            ))
            : undefined
          const fallback = legacyItem?.key
            ?? data.seasons.find((item) => item.is_latest)?.key
            ?? data.seasons[0]?.key
          if (fallback) {
            setSeason(fallback)
            setSearchParams({ scope: fallback }, { replace: true })
          }
        }
      })
      .catch(() => {})
  }, [])

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
    }), { replace: true })
  }, [season, position, bonusFilter, competition, debouncedSearch, page, setSearchParams])

  useEffect(() => {
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
          explanationRequestIdRef.current += 1
          const committedContext = usesPodiumLayout ? podiumContextKey : ''
          committedPodiumContextRef.current = committedContext
          setCommittedPodiumContext(committedContext)
          setPodiumPlayers(podium)
          setRankingExplanations([])
          setSelectedAnalysis(null)
        }
        setListPlayers(list)
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
  ])

  useEffect(() => {
    const shouldLoadNarratives = usesPodiumLayout
      && (isAllTime || selectedSeasonItem != null)
      && podiumPlayers.length === PODIUM_SIZE
      && committedPodiumContext === podiumContextKey
    if (!shouldLoadNarratives) {
      explanationRequestIdRef.current += 1
      setRankingExplanations([])
      return
    }
    const controller = new AbortController()
    const requestId = ++explanationRequestIdRef.current
    const expectedPlayerIds = [...narrativePlayerIds]
    setRankingExplanations([])
    fetchRankingExplanations({
      season: isAllTime ? 'all' : selectedSeasonItem!.season,
      competition_id: isWcSeason ? WORLD_CUP_COMPETITION_ID : competition,
      scope: explanationScope,
      scope_key: isAllTime ? 'all' : selectedSeasonItem!.key,
      position: position || undefined,
      bonus_label: bonusFilter || undefined,
      limit: PODIUM_SIZE,
      use_total: true,
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted || requestId !== explanationRequestIdRef.current) return
        const byPlayerId = new Map(data.explanations.map((item) => [item.player_id, item]))
        const alignedExplanations = expectedPlayerIds
          .map((playerId) => byPlayerId.get(playerId))
          .filter((item): item is RankingPlayerExplanation => item != null)
        if (alignedExplanations.length === expectedPlayerIds.length) {
          setRankingExplanations(alignedExplanations)
        }
      })
      .catch((requestError: unknown) => {
        if (!isAbortError(requestError) && requestId === explanationRequestIdRef.current) {
          setRankingExplanations([])
        }
      })
    return () => {
      controller.abort()
    }
  }, [
    bonusFilter,
    committedPodiumContext,
    competition,
    explanationScope,
    isAllTime,
    isWcSeason,
    narrativePlayerIdsKey,
    podiumContextKey,
    position,
    season,
    selectedSeasonItem,
    usesPodiumLayout,
  ])

  const showHero = usesPodiumLayout && podiumPlayers.length > 0
  const top3 = showHero ? podiumPlayers : []
  const currentPagePlayers = listPlayers
  const visibleTotalPlayers = usesPodiumLayout
    ? Math.max(totalPlayers - PODIUM_SIZE, 0)
    : totalPlayers
  const totalPages = visibleTotalPlayers > 0 ? Math.ceil(visibleTotalPlayers / LIST_PAGE_SIZE) : 0
  const hasNextPage = page + 1 < totalPages
  const hasPrevPage = page > 0
  const visibleRangeStart = totalPlayers > 0 && currentPagePlayers.length > 0
    ? listOffset + 1
    : 0
  const visibleRangeEnd = totalPlayers > 0
    ? Math.min(listOffset + currentPagePlayers.length, totalPlayers)
    : 0

  const mainCompetitions = competitions
    .filter((c) => MAIN_COMPETITION_IDS.includes(c.id))
    .sort((a, b) => MAIN_COMPETITION_IDS.indexOf(a.id) - MAIN_COMPETITION_IDS.indexOf(b.id))

  const activeComp = competitions.find((c) => c.id === competition)
  const contextParts = [activeComp?.name, position || null, bonusFilter || null].filter(Boolean)
  const contextLabel = contextParts.length > 0 ? contextParts.join(' - ') : null
  const rankingReturnTo = `/ranking?${buildRankingParams({
    season,
    position,
    bonusFilter,
    competition,
    search: debouncedSearch,
    page,
  }).toString()}`

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

  const seasonPicker = seasonItems.length > 0 ? (
    <div className="rp-season-picker">
      <div className="rp-season-picker__label">
        <span className="rp-season-picker__hint">Temporada del ranking</span>
        <small>Elige que tabla estas viendo</small>
      </div>
      <SeasonDropdown
        items={seasonItems}
        value={season}
        onChange={(nextSeason) => {
          resetListPage()
          setSeason(nextSeason)
        }}
        includeAll={true}
      />
    </div>
  ) : null

  function goNext() {
    if (!hasNextPage) return
    setPageDir('next')
    setPage((p) => p + 1)
  }

  function goPrev() {
    if (!hasPrevPage) return
    setPageDir('prev')
    setPage((p) => p - 1)
  }

  function goToPage(nextPage: number) {
    if (nextPage === page) return
    setPageDir(nextPage > page ? 'next' : 'prev')
    setPage(nextPage)
  }

  const visiblePages = Array.from({ length: totalPages }, (_, index) => index)
    .filter((index) => (
      index === 0
      || index === totalPages - 1
      || Math.abs(index - page) <= 1
    ))

  return (
    <div className="ranking-page">
      {isWcSeason ? (
        <WorldCupPageHeader />
      ) : (
        <WorldCupPageHeader
          variant="standard"
          eyebrow={season === 'all'
            ? 'Stats Football Award - Historial'
            : 'Stats Football Award - Clasificacion SFA'}
          title="No todos los goles valen igual"
          subtitle="Ranking de impacto SFA: el contexto cambia cada punto."
          showLogo={true}
        />
      )}

      <section
        className={`rp-control-deck${isWcSeason ? ' rp-control-deck--wc' : ''}`}
        aria-label={isWcSeason ? 'Controles del ranking mundial' : 'Controles del ranking'}
      >
        <WcLiveChip />
        {seasonPicker}
        <Link to="/metodologia" className="rp-control-deck__method">
          <span>
            <strong>Entiende los puntos</strong>
            <small>Por que un gol vale mas que otro</small>
          </span>
          <i aria-hidden="true">Ver guia</i>
        </Link>
      </section>

      <section
        className={`rp-intro${isWcSeason ? ' rp-intro--wc' : ''}`}
        aria-labelledby="rp-intro-title"
      >
        <div className="rp-intro__copy">
          <span className="rp-intro__eyebrow">
            {isWcSeason ? 'Edicion especial Mundial: lee el ranking en 10 segundos' : 'Que mide SFA'}
          </span>
          <h2 id="rp-intro-title">
            {isWcSeason
              ? 'SFA no pregunta cuantos hizo. Pregunta cuando pesaron.'
              : 'No contamos solo acciones: medimos cuanto cambiaron el partido.'}
          </h2>
        </div>
        <div className="rp-intro__formula" aria-label="Formula simple del ranking SFA">
          <span>Gol</span>
          <i>+</i>
          <span>Rival</span>
          <i>+</i>
          <span>Momento</span>
          <i>+</i>
          <span>Fase</span>
          <i>=</i>
          <strong>Puntos SFA</strong>
        </div>
        <div className="rp-intro__proof">
          <p>
            Un gol al 0-0 en eliminatoria vale mas que uno con el partido resuelto.
          </p>
          <p>
            Tambien pesan asistencias, defensa, pases y apariciones en partidos grandes.
          </p>
        </div>
        <Link to="/metodologia" className="rp-intro__link">
          Como funciona SFA
          <span aria-hidden="true">-&gt;</span>
        </Link>
      </section>

      {isWcSeason && (
        <div className="rp-world-cup-match-preview">
          <WcLiveChip />
        </div>
      )}

      {initialLoading && (
        <>
          <div className="players-showcase">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton skeleton-showcase-card" />
            ))}
          </div>
          <div className="rp-table-section">
            <div className="ranking-cards-grid">
              {Array.from({ length: LIST_PAGE_SIZE }).map((_, i) => (
                <div key={i} className="skeleton rc-skeleton" />
              ))}
            </div>
          </div>
        </>
      )}

      {!initialLoading && error && (
        <div className="empty-state">
          {isWcSeason ? `Mundial 2026 - ${error}` : error}
        </div>
      )}

      {!initialLoading && !error && (
        <>
          {showHero && rankingExplanations.length > 0 && (
            <TopRankingNarrativeCarousel
              players={top3}
              explanations={rankingExplanations}
              onOpenAnalysis={setSelectedAnalysis}
            />
          )}
          {showHero && (
            <section
              className={`rp-podium${isWcSeason ? ' rp-podium--wc' : ''}`}
              aria-label="Podio del ranking"
              aria-busy={isContextRefreshing}
            >
              <div className="players-showcase">
                {top3.map((p, index) => (
                  <ShowcaseCard
                    key={p.id}
                    player={p}
                    detail={null}
                    isFirst={index === 0}
                    podiumPlace={index + 1}
                    scope={season}
                    isWorldCup={isWcSeason}
                    returnTo={rankingReturnTo}
                  />
                ))}
              </div>
            </section>
          )}

          <div
            className={`rp-table-section${isWcSeason ? ' rp-table-section--wc' : ''}`}
            aria-busy={isContextRefreshing || isListRefreshing}
          >
            <div
              className={`rp-refresh-status${isContextRefreshing || isListRefreshing || refreshError ? ' is-visible' : ''}${refreshError ? ' is-error' : ''}`}
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              {isContextRefreshing
                ? 'Actualizando ranking...'
                : isListRefreshing
                  ? 'Actualizando jugadores...'
                  : refreshError
                    ? 'No se pudo actualizar. Mostrando los ultimos datos.'
                    : ''}
            </div>
            <div className={`rp-ranking-head${isWcSeason ? ' rp-ranking-head--wc' : ''}`}>
              <div>
                <span>{isWcSeason ? 'Edicion Mundial' : 'Clasificacion completa'}</span>
                <h2>Todos los jugadores</h2>
              </div>
              {isWcSeason && (
                <div className="wc-ranking-tools">
                  <label className="wc-position-filter">
                    <span>Posicion</span>
                    <strong aria-hidden="true">{position || 'Todas'}</strong>
                    <select
                      value={position}
                      onChange={(event) => changePosition(event.target.value)}
                      aria-label="Filtrar ranking mundial por posicion"
                    >
                      <option value="">Todas</option>
                      {WORLD_CUP_POSITION_OPTIONS.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label className="wc-position-filter">
                    <span>Perfil</span>
                    <strong aria-hidden="true">{bonusFilter || 'Todos'}</strong>
                    <select
                      value={bonusFilter}
                      onChange={(event) => changeBonusFilter(event.target.value)}
                      aria-label="Filtrar ranking mundial por promesa o veterano"
                    >
                      <option value="">Todos</option>
                      {BONUS_FILTER_OPTIONS.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label className="wc-ranking-search">
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <circle cx="8.5" cy="8.5" r="5.5" />
                      <path d="m13 13 4 4" />
                    </svg>
                    <input
                      type="search"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Buscar jugador o seleccion"
                      aria-label="Buscar en el ranking del Mundial"
                    />
                    {search && (
                      <button
                        type="button"
                        onClick={() => setSearch('')}
                        aria-label="Limpiar busqueda"
                      >
                        x
                      </button>
                    )}
                  </label>
                </div>
              )}
            </div>

            {!isWcSeason && (
              <FilterBar
                position={position}
                onPosition={changePosition}
                bonusFilter={bonusFilter}
                onBonusFilter={changeBonusFilter}
                competition={competition}
                onCompetition={changeCompetition}
                competitions={mainCompetitions}
                search={search}
                onSearch={setSearch}
              />
            )}

            {contextLabel && (
              <div className="rp-context-label">
                {contextLabel}
              </div>
            )}

            {currentPagePlayers.length === 0 ? (
              <div className="empty-state">
                {search
                  ? `Sin resultados para "${search}"`
                  : isWcSeason
                    ? 'Mundial 2026 - Sin jugadores para los filtros seleccionados.'
                    : 'Sin jugadores para los filtros seleccionados.'}
              </div>
            ) : (
              <>
                <div className="ranking-table-head" aria-hidden="true">
                  <span>Pos.</span>
                  <span />
                  <span>Jugador</span>
                  <span>Rol</span>
                  <span>PJ</span>
                  <span>G + A</span>
                  <span>Puntos SFA</span>
                </div>
                <div className="rp-ranking-list-viewport">
                  <div
                    key={`${page}-${pageDir}`}
                    className={`ranking-cards-grid ranking-cards-grid--${pageDir === 'next' ? 'from-right' : 'from-left'}`}
                  >
                    {currentPagePlayers.map((p, i) => (
                      <RankingCard
                        key={p.id}
                        player={p}
                        index={i}
                        competitionName={activeComp?.name}
                        scope={season}
                        isWorldCup={isWcSeason}
                        returnTo={rankingReturnTo}
                      />
                    ))}
                  </div>
                </div>

                {totalPages > 1 && (
                  <nav className="ranking-pagination" aria-label="Paginas del ranking">
                    <button
                      className="pagination-btn pagination-btn--prev"
                      onClick={goPrev}
                      disabled={!hasPrevPage}
                      aria-label="Ir a la pagina anterior"
                    >
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <path d="m10 3-5 5 5 5" />
                      </svg>
                      <span>Anterior</span>
                    </button>

                    <div className="ranking-pagination__center">
                      <div className="pagination-pages">
                        {visiblePages.map((pageIndex, index) => {
                          const previousVisible = visiblePages[index - 1]
                          const needsGap = previousVisible != null && pageIndex - previousVisible > 1
                          return (
                            <span className="pagination-pages__slot" key={pageIndex}>
                              {needsGap && <span className="pagination-ellipsis">...</span>}
                              <button
                                className={`pagination-page${pageIndex === page ? ' pagination-page--active' : ''}`}
                                onClick={() => goToPage(pageIndex)}
                                aria-label={`Ir a la pagina ${pageIndex + 1}`}
                                aria-current={pageIndex === page ? 'page' : undefined}
                              >
                                {pageIndex + 1}
                              </button>
                            </span>
                          )
                        })}
                      </div>
                      <div className="pagination-progress" aria-hidden="true">
                        <span style={{ transform: `scaleX(${(page + 1) / totalPages})` }} />
                      </div>
                      <span className="ranking-pagination__status">
                        {visibleRangeStart > 0
                          ? `${visibleRangeStart}-${visibleRangeEnd} de ${totalPlayers} jugadores`
                          : '0 jugadores'}
                      </span>
                    </div>

                    <button
                      className="pagination-btn pagination-btn--next"
                      onClick={goNext}
                      disabled={!hasNextPage}
                      aria-label="Ir a la pagina siguiente"
                    >
                      <span>Siguiente</span>
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <path d="m6 3 5 5-5 5" />
                      </svg>
                    </button>
                  </nav>
                )}
                <div className="rp-ranking-total" aria-label="Jugadores contabilizados">
                  <span>{totalPlayers > 0 ? animatedTotal.toLocaleString('es-ES') : '--'}</span>
                  <small>Jugadores contabilizados</small>
                </div>
              </>
            )}
          </div>
          <RankingExplanationModal
            explanation={selectedAnalysis}
            onClose={() => setSelectedAnalysis(null)}
          />
        </>
      )}
    </div>
  )
}
