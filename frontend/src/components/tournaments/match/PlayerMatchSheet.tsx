import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchPlayer, fetchPlayerEvents, fetchPlayerFixtures } from '../../../api/client'
import type { PlayerEvent, PlayerFixture } from '../../../types'
import { FootballIcon } from '../../shared/FootballVisuals'
import { ArrowIcon } from '../MatchUI'
import { playerPhoto, teamLogo, type MatchPlayer } from './matchModel'

const POSITION: Record<string, string> = { G: 'Portero', D: 'Defensa', M: 'Centrocampista', F: 'Delantero' }
// SFA positions are finer than the lineup's four roles (an EXT is not a generic midfielder).
const SFA_POSITION: Record<string, string> = {
  GK: 'Portero', DC: 'Central', LAT: 'Lateral', MC: 'Centrocampista', MCO: 'Mediapunta', EXT: 'Extremo', DEL: 'Delantero',
}

const BREAKDOWN_LABELS: Record<string, string> = {
  goal: 'Goles',
  goal_penalty: 'Goles de penal',
  assist: 'Asistencias',
  stats: 'Juego (pases, duelos, regates…)',
}

const ACTION_LABELS: Record<string, string> = { goal: 'Gol', goal_penalty: 'Gol de penal', assist: 'Asistencia' }

const points = (value: number) => Math.round(value).toLocaleString('es-ES')
const factor = (value: number) => `×${value.toLocaleString('es-ES', { maximumFractionDigits: 2 })}`

type Loaded = { fixture: PlayerFixture | null; actions: PlayerEvent[]; position: string | null }

function useMatchPlayerData(player: MatchPlayer | null, matchExternalId: number, scope: string) {
  const [state, setState] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; data: Loaded | null }>({ status: 'idle', data: null })

  useEffect(() => {
    if (!player || player.player_id == null) {
      setState({ status: 'idle', data: null })
      return undefined
    }
    let cancelled = false
    setState({ status: 'loading', data: null })
    Promise.all([
      fetchPlayerFixtures(player.player_id, undefined, scope),
      fetchPlayerEvents(player.player_id, undefined, scope).catch(() => [] as PlayerEvent[]),
      fetchPlayer(player.player_id, undefined, scope).then((profile) => profile.position).catch(() => null),
    ])
      .then(([fixtures, events, position]) => {
        if (cancelled) return
        const fixture = fixtures.find((item) => item.fixture_external_id === matchExternalId) ?? null
        const actions = fixture
          ? events.filter((event) => event.fixture_id === fixture.fixture_id && event.event_type !== 'stats').sort((a, b) => a.minute - b.minute)
          : []
        setState({ status: 'ready', data: { fixture, actions, position } })
      })
      .catch(() => { if (!cancelled) setState({ status: 'error', data: null }) })
    return () => { cancelled = true }
  }, [player, matchExternalId, scope])

  return state
}

function ActionRow({ action, playerTeam }: { action: PlayerEvent; playerTeam: string | null }) {
  const [home = 0, away = 0] = (action.score_before ?? '0:0').split(':').map(Number)
  const isHome = playerTeam != null && action.home_team === playerTeam
  const own = isHome ? home : away
  const rival = isHome ? away : home
  const situation = own < rival ? `perdían ${rival}–${own}` : own === rival ? `empate ${own}–${rival}` : `ganaban ${own}–${rival}`
  const factors: string[] = []
  if (Math.abs(action.m1 - 1) >= 0.01) factors.push(`Rival ${factor(action.m1)}`)
  if (Math.abs(action.m2 - 1) >= 0.01) factors.push(`Fase ${factor(action.m2)}`)
  if (Math.abs(action.m3 - 1) >= 0.01) factors.push(`Momento ${factor(action.m3)}`)
  if (Math.abs(action.m4 - 1) >= 0.01) factors.push(`Remate ${factor(action.m4)}`)
  if (Math.abs(action.mvisit - 1) >= 0.01) factors.push(`Visita ${factor(action.mvisit)}`)

  return (
    <li className="pms-action">
      <span className="pms-action__icon" aria-hidden="true"><FootballIcon kind={action.event_type === 'assist' ? 'assist' : 'goal'} /></span>
      <span className="pms-action__what">
        <strong>{ACTION_LABELS[action.event_type] ?? action.event_type} en el {action.minute}'</strong>
        <small>{situation.charAt(0).toUpperCase() + situation.slice(1)}{factors.length > 0 && ` · ${factors.join(' · ')}`}</small>
      </span>
      <b>+{points(action.pts)}</b>
    </li>
  )
}

export default function PlayerMatchSheet({
  player,
  players,
  rank,
  matchExternalId,
  scope,
  onNavigate,
  onClose,
}: {
  player: MatchPlayer | null
  /** Players that took part, in navigation order. */
  players: MatchPlayer[]
  /** 1-based SFA position of each player inside this match. */
  rank: Map<MatchPlayer, number>
  matchExternalId: number
  scope: string
  onNavigate: (player: MatchPlayer) => void
  onClose: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const { status, data } = useMatchPlayerData(player, matchExternalId, scope)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (player && !dialog.open) dialog.showModal()
    if (!player && dialog.open) dialog.close()
  }, [player])

  const index = player ? players.indexOf(player) : -1
  const previous = index > 0 ? players[index - 1] : null
  const next = index >= 0 && index < players.length - 1 ? players[index + 1] : null
  const fixture = data?.fixture ?? null
  const photo = player ? playerPhoto(player.external_id) : null
  const crest = player ? teamLogo(player.team) : null
  const breakdown = fixture?.breakdown
    ? Object.entries(fixture.breakdown).filter(([, entry]) => entry.pts !== 0).sort((a, b) => b[1].pts - a[1].pts)
    : []
  const breakdownTotal = breakdown.reduce((sum, [, entry]) => sum + Math.max(entry.pts, 0), 0) || 1
  const passPct = fixture && fixture.passes_total > 0 ? Math.round((fixture.passes_accurate / fixture.passes_total) * 100) : null
  const minutes = fixture?.minutes ?? (player ? (player.starter ? (player.marks.off ?? 90) : player.marks.on != null ? 90 - player.marks.on : 0) : 0)

  return (
    <dialog
      ref={dialogRef}
      className="pms"
      aria-labelledby="pms-name"
      onClose={onClose}
      onClick={(event) => { if (event.target === event.currentTarget) onClose() }}
    >
      {player && (
        <div className="pms__inner">
          <header className="pms__top">
            <span className="pms__team">
              {crest && <img src={crest} alt="" width={18} height={18} />}
              {player.team.name}
            </span>
            <button type="button" className="pms__icon-btn" onClick={onClose} aria-label="Cerrar">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3.5 3.5 12.5 12.5M12.5 3.5 3.5 12.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>
            </button>
          </header>

          <div className="pms__hero">
            <button type="button" className="pms__icon-btn" onClick={() => previous && onNavigate(previous)} disabled={!previous} aria-label="Jugador anterior">
              <ArrowIcon direction="left" />
            </button>
            <span className="pms__photo">
              {photo ? <img src={photo} alt="" /> : <span aria-hidden="true">{player.name.slice(0, 2).toUpperCase()}</span>}
              {player.sfa_points != null && (
                <b className={`pms__badge${player.sfa_points < 0 ? ' is-neg' : ''}`}>{points(player.sfa_points)}<small>pts</small></b>
              )}
            </span>
            <button type="button" className="pms__icon-btn" onClick={() => next && onNavigate(next)} disabled={!next} aria-label="Jugador siguiente">
              <ArrowIcon />
            </button>
          </div>
          <h2 id="pms-name" className="pms__name">{player.number != null && <small>{player.number}</small>}{player.name}</h2>

          <dl className="pms__facts">
            <div><dt>Posición</dt><dd>{(data?.position && SFA_POSITION[data.position]) ?? POSITION[player.position ?? ''] ?? player.position ?? '—'}</dd></div>
            <div><dt>Minutos</dt><dd>{minutes}'</dd></div>
            <div>
              <dt>En el partido</dt>
              <dd>{rank.get(player) ? `${rank.get(player)}.º de ${rank.size}` : 'Sin puntos'}</dd>
            </div>
          </dl>

          <div className="pms__body">
            {player.player_id == null && (
              <p className="pms__note">Este jugador todavía no tiene puntos SFA calculados, así que solo mostramos su presencia en el partido.</p>
            )}
            {status === 'loading' && <div className="pms__skeleton" role="status"><span className="sr-only">Cargando datos del jugador</span></div>}
            {status === 'error' && <p className="pms__note">No pudimos cargar sus datos de este partido.</p>}

            {status === 'ready' && data && (
              <>
                {data.actions.length > 0 && (
                  <section className="pms__card pms__card--gold" aria-labelledby="pms-actions">
                    <h3 id="pms-actions">Sus acciones decisivas</h3>
                    <ul className="pms__actions">
                      {data.actions.map((action) => <ActionRow key={action.id} action={action} playerTeam={fixture?.player_team ?? null} />)}
                    </ul>
                  </section>
                )}

                {breakdown.length > 0 && (
                  <section className="pms__card" aria-labelledby="pms-breakdown">
                    <h3 id="pms-breakdown">De dónde salen sus puntos</h3>
                    <ul className="pms__breakdown">
                      {breakdown.map(([key, entry]) => (
                        <li key={key}>
                          <span>{BREAKDOWN_LABELS[key] ?? key}{entry.count > 1 && key !== 'stats' ? ` · ${entry.count}` : ''}</span>
                          <b>{points(entry.pts)}</b>
                          <i aria-hidden="true"><em style={{ width: `${(Math.max(entry.pts, 0) / breakdownTotal) * 100}%` }} /></i>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {fixture && (
                  <section aria-labelledby="pms-stats">
                    <h3 id="pms-stats" className="pms__title">Estadísticas del partido</h3>
                    <div className="pms__tiles">
                      <div className={player.marks.goals > 0 ? 'is-hit' : undefined}><b>{player.marks.goals}</b><span>Goles</span></div>
                      <div className={player.marks.assists > 0 ? 'is-hit' : undefined}><b>{player.marks.assists}</b><span>Asistencias</span></div>
                      <div><b>{fixture.rating != null ? fixture.rating.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'}</b><span>Nota fuente</span></div>
                    </div>
                    <dl className="pms__stats">
                      <div><dt>Remates (a puerta)</dt><dd>{fixture.shots_total} <small>({fixture.shots_on})</small></dd></div>
                      <div><dt>Pases completados</dt><dd>{fixture.passes_accurate}/{fixture.passes_total}{passPct != null && <small> · {passPct} %</small>}</dd></div>
                      <div><dt>Pases clave</dt><dd>{fixture.passes_key}</dd></div>
                      <div><dt>Regates completados</dt><dd>{fixture.dribbles_won}</dd></div>
                      <div><dt>Duelos ganados</dt><dd>{fixture.duels_won}</dd></div>
                      <div><dt>Entradas ganadas</dt><dd>{fixture.tackles_won}</dd></div>
                      <div><dt>Intercepciones</dt><dd>{fixture.interceptions}</dd></div>
                      <div><dt>Bloqueos</dt><dd>{fixture.blocks}</dd></div>
                      <div><dt>Despejes</dt><dd>{fixture.clearances}</dd></div>
                      <div><dt>Faltas recibidas</dt><dd>{fixture.fouls_drawn}</dd></div>
                    </dl>
                  </section>
                )}
                {!fixture && <p className="pms__note">No hay estadísticas individuales registradas para este partido.</p>}
              </>
            )}
          </div>

          <footer className="pms__foot">
            {player.player_id != null
              ? <Link to={`/player/${player.player_id}?scope=${scope}`} className="pms__profile">Perfil del jugador <ArrowIcon /></Link>
              : <span />}
            <button type="button" className="pms__done" onClick={onClose}>Cerrar</button>
          </footer>
        </div>
      )}
    </dialog>
  )
}
