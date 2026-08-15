import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRanking } from '../../api/client'
import type { RankedPlayer } from '../../types'

const POSITION_CYCLE = [
  { value: 'DC', label: 'Defensa central' },
  { value: 'LAT', label: 'Lateral' },
  { value: 'MC', label: 'Mediocentro' },
  { value: 'MCO', label: 'Mediocentro ofensivo' },
  { value: 'EXT', label: 'Extremo' },
  { value: 'DEL', label: 'Delantero' },
  { value: 'GK', label: 'Portero' },
] as const

interface PositionBoard {
  value: string
  label: string
  players: RankedPlayer[]
}

interface LeaderData {
  scorers: RankedPlayer[]
  assisters: RankedPlayer[]
  positions: PositionBoard[]
}

interface Props {
  season: string
  competitionId?: number
  contextLabel: string
}

function formatPoints(value: number) {
  return Math.round(value).toLocaleString('es-ES')
}

function PlayerPhoto({ player }: { player: RankedPlayer }) {
  return (
    <span className="trn-leader-row__photo">
      {player.photo_url
        ? <img src={player.photo_url} alt="" loading="lazy" decoding="async" />
        : <span aria-hidden="true">{player.name.slice(0, 2).toUpperCase()}</span>}
    </span>
  )
}

function LeaderList({
  players,
  scope,
  metric,
}: {
  players: RankedPlayer[]
  scope: string
  metric: 'goals' | 'assists' | 'points'
}) {
  if (players.length === 0) {
    return <p className="trn-leader-column__empty">Sin datos disponibles</p>
  }

  return (
    <ol className="trn-leader-list">
      {players.map((player, index) => {
        const value = metric === 'goals'
          ? player.goals
          : metric === 'assists'
            ? player.assists
            : formatPoints(player.sfa_pts)
        const suffix = metric === 'points' ? ' pts' : ''
        return (
          <li key={player.id}>
            <Link to={`/player/${player.id}?scope=${scope}`}>
              <b>{index + 1}</b>
              <PlayerPhoto player={player} />
              <span className="trn-leader-row__identity">
                <strong>{player.name}</strong>
                <small>
                  {player.team_logo_url && <img src={player.team_logo_url} alt="" loading="lazy" decoding="async" />}
                  <span>{player.team}</span>
                </small>
              </span>
              <em className={metric === 'points' ? 'is-points' : ''}>{value}{suffix}</em>
            </Link>
          </li>
        )
      })}
    </ol>
  )
}

function LeaderSkeleton() {
  return (
    <div className="trn-leaders__grid is-loading" aria-hidden="true">
      {[0, 1, 2].map((column) => (
        <div className="trn-leader-column" key={column}>
          <span className="trn-leader-skeleton trn-leader-skeleton--title" />
          {[0, 1, 2].map((row) => <span className="trn-leader-skeleton trn-leader-skeleton--row" key={row} />)}
        </div>
      ))}
    </div>
  )
}

export default function TournamentLeaders({ season, competitionId, contextLabel }: Props) {
  const scope = `season-${season}`
  const [data, setData] = useState<LeaderData>({ scorers: [], assisters: [], positions: [] })
  const [positionIndex, setPositionIndex] = useState(0)
  const [cycleRevision, setCycleRevision] = useState(0)
  const [paused, setPaused] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)

    const load = (extra: { bonus_label?: string; position?: string }) => (
      fetchRanking({
        scope,
        competition_id: competitionId,
        limit: 3,
        ...extra,
      }).then((response) => response.ranking).catch(() => [])
    )

    Promise.all([
      load({ bonus_label: 'Goleador' }),
      load({ bonus_label: 'Asistidor' }),
      ...POSITION_CYCLE.map((position) => load({ position: position.value })),
    ]).then(([scorers, assisters, ...positionResults]) => {
      if (!active) return
      const positions = POSITION_CYCLE
        .map((position, index) => ({ ...position, players: positionResults[index] }))
        .filter((position) => position.players.length > 0)
      setData({ scorers, assisters, positions })
      setPositionIndex(0)
    }).finally(() => {
      if (active) setLoading(false)
    })

    return () => { active = false }
  }, [competitionId, scope])

  const activePosition = data.positions[positionIndex] ?? null
  const reduceMotion = useMemo(() => (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ), [])

  useEffect(() => {
    if (paused || reduceMotion || data.positions.length < 2) return undefined
    const timer = window.setInterval(() => {
      setPositionIndex((current) => (current + 1) % data.positions.length)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [cycleRevision, data.positions.length, paused, reduceMotion])

  const movePosition = (direction: -1 | 1) => {
    if (data.positions.length < 2) return
    setPositionIndex((current) => (
      (current + direction + data.positions.length) % data.positions.length
    ))
    setCycleRevision((current) => current + 1)
  }

  const handleBlur = (event: React.FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false)
  }

  return (
    <section
      className="trn-leaders"
      aria-label={`Lideres de ${contextLabel}`}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={handleBlur}
    >
      <header className="trn-leaders__header">
        <div><span>Rendimiento individual</span><h2>Lideres de {contextLabel}</h2></div>
        <small>Top 3</small>
      </header>

      {loading ? <LeaderSkeleton /> : (
        <div className="trn-leaders__grid">
          <article className="trn-leader-column">
            <header><span>Goleadores</span><small>Goles</small></header>
            <LeaderList players={data.scorers} scope={scope} metric="goals" />
          </article>

          <article className="trn-leader-column">
            <header><span>Asistencias</span><small>Asist.</small></header>
            <LeaderList players={data.assisters} scope={scope} metric="assists" />
          </article>

          <article className="trn-leader-column trn-leader-column--position">
            <header>
              <span>Top por posicion</span>
              <div className="trn-leader-column__nav">
                <button type="button" onClick={() => movePosition(-1)} disabled={data.positions.length < 2} aria-label="Posicion anterior">&#8592;</button>
                <small>{activePosition?.label ?? 'Sin posicion'}</small>
                <button type="button" onClick={() => movePosition(1)} disabled={data.positions.length < 2} aria-label="Posicion siguiente">&#8594;</button>
              </div>
            </header>
            <div className="trn-leader-position" key={activePosition?.value ?? 'empty'}>
              <LeaderList players={activePosition?.players ?? []} scope={scope} metric="points" />
            </div>
          </article>
        </div>
      )}
    </section>
  )
}
