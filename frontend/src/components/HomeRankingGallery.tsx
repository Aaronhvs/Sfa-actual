import { useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import PlayerPortrait from './shared/PlayerPortrait'
import type { RankedPlayer } from '../types'
import './HomeRankingGallery.css'
import { FootballIcon, TeamCrest } from './shared/FootballVisuals'

export default function HomeRankingGallery({ players, playerUrl }: {
  players: RankedPlayer[]
  playerUrl: (id: number) => string
}) {
  const [active, setActive] = useState<number | null>(0)
  const listRef = useRef<HTMLOListElement>(null)
  const before = useRef<DOMRect[]>([])

  function expand(index: number, animate = true) {
    const panels = listRef.current?.querySelectorAll<HTMLElement>('.sfa-gallery__panel')
    // Only the mobile accordion reflows. Keep desktop comparison columns stable.
    before.current = animate && window.matchMedia('(max-width: 680px)').matches
      ? Array.from(panels ?? []).map((panel) => panel.getBoundingClientRect())
      : []
    setActive(index === active ? null : index)
  }

  useLayoutEffect(() => {
    if (!before.current.length) return
    const panels = Array.from(listRef.current?.querySelectorAll<HTMLElement>('.sfa-gallery__panel') ?? [])
    const cancel = () => panels.forEach((panel) => {
      panel.getAnimations().forEach((animation) => animation.cancel())
      panel.querySelector('.sfa-gallery__backdrop')?.getAnimations().forEach((animation) => animation.cancel())
    })
    cancel()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      before.current = []
      return
    }
    const after = panels.map((panel) => panel.getBoundingClientRect())
    panels.forEach((panel, index) => {
      const previous = before.current[index]
      const next = after[index]
      if (!previous || !next.width || !next.height) return
      if (Math.abs(previous.left - next.left) < 0.5 && Math.abs(previous.top - next.top) < 0.5) return
      // Move following accordion rows without scaling photographs or text.
      panel.animate([
        { transform: `translate(${previous.left - next.left}px, ${previous.top - next.top}px)` },
        { transform: 'none' },
      ], { duration: 260, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' })
    })
    before.current = []
    return cancel
  }, [active])

  return (
    <ol className="sfa-gallery" ref={listRef} aria-label="Los tres primeros del ranking SFA">
      {players.map((player, index) => (
        <li className={`sfa-gallery__panel${index === active ? ' is-expanded' : ''}${player.rank === 1 ? ' is-leader' : ''}`} key={player.id} data-player-id={player.id}>
          <div className="sfa-gallery__backdrop" aria-hidden="true" />
          <div className="sfa-gallery__visual">
            <span className="sfa-gallery__top"><span className="sfa-gallery__rank" aria-label={`Puesto ${player.rank}`}>{player.rank}</span></span>
            <PlayerPortrait player={player} className="sfa-gallery__portrait" eager allowArtwork />
            <span className="sfa-gallery__identity"><span className="sfa-gallery__name">{player.name}</span><span className="sfa-gallery__team"><TeamCrest key={player.team} url={player.team_logo_url} name={player.team} /></span></span>
            <span className="sfa-gallery__score">{player.sfa_pts.toLocaleString('es-ES', { maximumFractionDigits: 0 })}<span>puntos SFA</span></span>
            <span className="sfa-gallery__stats">
              <span><strong><FootballIcon kind="goal" />{player.goals}</strong><span>Goles</span></span>
              <span><strong><FootballIcon kind="assist" />{player.assists}</strong><span>Asistencias</span></span>
              <span><strong><FootballIcon kind="matches" />{player.matches}</strong><span>Partidos</span></span>
            </span>
          </div>
          <button type="button" className="sfa-gallery__toggle" aria-expanded={index === active}
            aria-label={`${index === active ? 'Contraer' : 'Ampliar'} ficha de ${player.name}`}
            aria-controls={`sfa-gallery-detail-${player.id}`} onClick={(event) => expand(index, event.detail !== 0)}>
            <span className="sfa-gallery__expand" aria-hidden="true">{index === active ? '−' : '+'}</span>
          </button>
          <div className="sfa-gallery__detail" id={`sfa-gallery-detail-${player.id}`}>
            <Link to={playerUrl(player.id)} aria-label={`Ver actuaciones de ${player.name}`}>
              <span>Ver actuaciones</span>
              <svg className="sfa-gallery__cta-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" /></svg>
            </Link>
          </div>
        </li>
      ))}
    </ol>
  )
}
