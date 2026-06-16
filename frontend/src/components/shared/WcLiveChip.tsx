import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchWcFixtures, fetchWcLive } from '../../api/client'
import type { WcFixture } from '../../types'
import { worldCupTeamName } from '../../utils/worldCupTeams'

const FINISHED_STATUSES = new Set(['FT', 'AET', 'PEN'])

function formatMatchTime(iso: string): string {
  return new Date(iso).toLocaleString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function WcLiveChip() {
  const [fixture, setFixture] = useState<WcFixture | null>(null)
  const [mode, setMode] = useState<'live' | 'next'>('live')

  useEffect(() => {
    function check() {
      fetchWcLive()
        .then((res) => {
          const liveFixture = res.live[0] ?? null
          if (liveFixture) {
            setFixture(liveFixture)
            setMode('live')
            return
          }

          fetchWcFixtures(true)
            .then((fixturesRes) => {
              const now = Date.now()
              const nextFixture = fixturesRes.fixtures
                .filter((item) => (
                  !item.is_live
                  && !FINISHED_STATUSES.has(item.status)
                  && new Date(item.played_at).getTime() >= now - 30 * 60_000
                ))
                .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())[0]
                ?? null
              setFixture(nextFixture)
              setMode('next')
            })
            .catch(() => {
              setFixture(null)
              setMode('next')
            })
        })
        .catch(() => {})
    }
    check()
    const timer = setInterval(check, 60_000)
    return () => clearInterval(timer)
  }, [])

  if (!fixture) return null

  const homeName = worldCupTeamName(fixture.home_team)
  const awayName = worldCupTeamName(fixture.away_team)
  const isLive = mode === 'live'
  const matchStatus = fixture.status === 'HT'
    ? 'Descanso'
    : isLive
      ? `${fixture.elapsed ?? ''}'`
      : formatMatchTime(fixture.played_at)
  const homeFlag = fixture.home_team.external_id
    ? `https://media.api-sports.io/football/teams/${fixture.home_team.external_id}.png`
    : null
  const awayFlag = fixture.away_team.external_id
    ? `https://media.api-sports.io/football/teams/${fixture.away_team.external_id}.png`
    : null

  return (
    <div className={`wc-live-chip${isLive ? ' wc-live-chip--live' : ' wc-live-chip--next'}`}>
      <Link
        to={`/mundial/partido/${fixture.external_id}`}
        className="wc-live-chip__match"
        aria-label={
          isLive
            ? `${homeName} ${fixture.home_goals ?? 0} a ${fixture.away_goals ?? 0} ${awayName}, en vivo. Ver partido`
            : `Próximo partido: ${homeName} contra ${awayName}. Ver partido`
        }
      >
        <span className="wc-live-chip__status">
          <i className="wc-live-chip__dot" aria-hidden="true" />
          {isLive ? 'En vivo' : 'Próximo'}
        </span>
        <span className="wc-live-chip__side wc-live-chip__side--home">
          <span className="wc-live-chip__team">{homeName}</span>
          {homeFlag && <img src={homeFlag} alt="" className="wc-live-chip__flag" />}
        </span>
        <strong className="wc-live-chip__score">
          {isLive ? (fixture.home_goals ?? 0) : 'vs'}
          {isLive && <span>:</span>}
          {isLive ? (fixture.away_goals ?? 0) : ''}
        </strong>
        <span className="wc-live-chip__side">
          {awayFlag && <img src={awayFlag} alt="" className="wc-live-chip__flag" />}
          <span className="wc-live-chip__team">{awayName}</span>
        </span>
        <span className="wc-live-chip__minute">{matchStatus}</span>
      </Link>
      <Link to="/mundial" className="wc-live-chip__more">
        Ver Mundial
      </Link>
    </div>
  )
}
