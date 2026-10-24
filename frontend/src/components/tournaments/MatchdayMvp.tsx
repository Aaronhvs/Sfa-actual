import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchLatestMvps, fetchMatchdayMvps } from '../../api/client'
import type { LatestMvpsResponse, MatchdayMvp } from '../../types'
import PlayerPortrait from '../shared/PlayerPortrait'
import { ArrowIcon, CompetitionTile, Crest } from './MatchUI'
import './MatchdayMvp.css'

/* ── "Jugador de la jornada": best single-match SFA performance of each round ── */

const pts = (value: number) => Math.round(value).toLocaleString('es-ES')
const surname = (name: string) => name.split(' ').slice(-1)[0]

const REASONS: Record<MatchdayMvp['reasons'][number], string> = {
  behind: 'Remontando',
  level: 'Con empate',
  big_rival: 'Ante un grande',
  away: 'Fuera de casa',
  knockout: 'Eliminatoria',
}

function contributions(mvp: MatchdayMvp) {
  const parts = [
    mvp.goals > 0 && `${mvp.goals} ${mvp.goals === 1 ? 'gol' : 'goles'}`,
    mvp.assists > 0 && `${mvp.assists} ${mvp.assists === 1 ? 'asistencia' : 'asistencias'}`,
  ].filter(Boolean)
  return parts.length ? parts.join(' y ') : 'Sin goles ni asistencias: todo con su juego'
}

function MvpMatch({ mvp }: { mvp: MatchdayMvp }) {
  const { fixture } = mvp
  return (
    <span className="mvp-match">
      <span className={fixture.player_side === 'home' ? 'is-own' : undefined}><Crest team={fixture.home_team} /><em>{fixture.home_team.name}</em></span>
      <b aria-label={`${fixture.home_team.name} ${fixture.home_goals ?? '-'}, ${fixture.away_team.name} ${fixture.away_goals ?? '-'}`}>
        {fixture.home_goals ?? '-'}<i>-</i>{fixture.away_goals ?? '-'}
      </b>
      <span className={fixture.player_side === 'away' ? 'is-own' : undefined}><em>{fixture.away_team.name}</em><Crest team={fixture.away_team} /></span>
    </span>
  )
}

/** Competition page: the round's MVP as a feature card, with earlier rounds one tap away. */
export function CompetitionMvp({ competitionId, season }: { competitionId: number; season: string }) {
  const [items, setItems] = useState<MatchdayMvp[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setItems([])
    fetchMatchdayMvps(competitionId, season).then((response) => {
      if (!active || !response?.items.length) return
      setItems(response.items)
      const latestComplete = [...response.items].reverse().find((item) => item.complete) ?? response.items[response.items.length - 1]
      setSelected(latestComplete.round_key)
    })
    return () => { active = false }
  }, [competitionId, season])

  const mvp = items.find((item) => item.round_key === selected)
  if (!mvp) return null
  const history = [...items].reverse()

  return (
    <section className="mvp" aria-labelledby="mvp-title">
      <div className="mvp-card">
        <PlayerPortrait player={mvp.player} className="mvp-card__photo" />
        <div className="mvp-card__copy">
          <p className="mvp-card__eyebrow">
            <span id="mvp-title">Jugador de la jornada</span>
            <b>{mvp.round_label}</b>
            {!mvp.complete && <em>Provisional · faltan {mvp.pending_fixtures} {mvp.pending_fixtures === 1 ? 'partido' : 'partidos'}</em>}
          </p>
          <h2><Link to={`/player/${mvp.player.id}`}>{mvp.player.name}</Link></h2>
          <MvpMatch mvp={mvp} />
          <p className="mvp-card__why">{contributions(mvp)}</p>
          {mvp.reasons.length > 0 && <ul className="mvp-card__tags">{mvp.reasons.map((reason) => <li key={reason}>{REASONS[reason]}</li>)}</ul>}
        </div>
        <div className="mvp-card__score">
          <b>{pts(mvp.sfa_pts)}</b>
          <span>pts SFA en el partido</span>
          <Link to={`/torneos/partido/${mvp.fixture.external_id}?season=${season}`} className="mvp-card__cta">Ver el partido <ArrowIcon /></Link>
        </div>
      </div>

      {history.length > 1 && (
        <div className="mvp-history">
          <h3>Jornadas anteriores</h3>
          <div className="mvp-history__list" role="group" aria-label="Elegir jornada">
            {history.map((item) => (
              <button
                type="button"
                key={item.round_key}
                className={item.round_key === selected ? 'is-active' : undefined}
                aria-pressed={item.round_key === selected}
                onClick={() => setSelected(item.round_key)}
              >
                <small>{item.round_label.replace('Jornada ', 'J')}</small>
                <PlayerPortrait player={item.player} className="mvp-history__photo" />
                <span><strong>{surname(item.player.name)}</strong><em>{pts(item.sfa_pts)}</em></span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

/** /torneos rail, under the competitions list: last round MVP of every competition. */
export function LatestMvpRail({ season }: { season: string }) {
  const [data, setData] = useState<LatestMvpsResponse | null>(null)

  useEffect(() => {
    let active = true
    fetchLatestMvps(season).then((response) => { if (active) setData(response) })
    return () => { active = false }
  }, [season])

  if (!data?.items.length) return null

  return (
    <section className="mvp-rail" aria-labelledby="mvp-rail-title">
      <h2 id="mvp-rail-title" className="tp-eyebrow">MVP de la jornada</h2>
      <ol>
        {data.items.map(({ competition, mvp }) => (
          <li key={competition.id}>
            <Link to={`/torneos/${competition.id}?season=${season}`} className="mvp-rail__row" title={`${competition.name} · ${mvp.round_label}`}>
              <span className="mvp-rail__photo">
                <PlayerPortrait player={mvp.player} className="mvp-rail__face" />
                <CompetitionTile competition={competition} />
              </span>
              <span className="mvp-rail__who">
                <strong>{mvp.player.name}</strong>
                <small>{competition.name.replace(/ League$/, '')} · {mvp.round_label.replace('Jornada ', 'J')}{!mvp.complete && ' · prov.'}</small>
              </span>
              <b>{pts(mvp.sfa_pts)}</b>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}
