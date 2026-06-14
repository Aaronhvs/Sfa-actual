import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchWcLive } from '../../api/client'
import type { WcFixture } from '../../types'
import { worldCupTeamName } from '../../utils/worldCupTeams'

export default function WcLiveChip() {
  const [liveFixture, setLiveFixture] = useState<WcFixture | null>(null)

  useEffect(() => {
    function check() {
      fetchWcLive()
        .then((res) => {
          setLiveFixture(res.live[0] ?? null)
        })
        .catch(() => {})
    }
    check()
    const timer = setInterval(check, 60_000)
    return () => clearInterval(timer)
  }, [])

  if (!liveFixture) return null

  const homeName = worldCupTeamName(liveFixture.home_team)
  const awayName = worldCupTeamName(liveFixture.away_team)
  const matchStatus = liveFixture.status === 'HT'
    ? 'Descanso'
    : `${liveFixture.elapsed ?? ''}'`
  const homeFlag = liveFixture.home_team.external_id
    ? `https://media.api-sports.io/football/teams/${liveFixture.home_team.external_id}.png`
    : null
  const awayFlag = liveFixture.away_team.external_id
    ? `https://media.api-sports.io/football/teams/${liveFixture.away_team.external_id}.png`
    : null

  return (
    <Link
      to="/mundial"
      className="wc-live-chip"
      aria-label={`${homeName} ${liveFixture.home_goals ?? 0} a ${liveFixture.away_goals ?? 0} ${awayName}, en vivo. Ver partido`}
    >
      <span className="wc-live-chip__status">
        <i className="wc-live-chip__dot" aria-hidden="true" />
        En vivo
      </span>
      <span className="wc-live-chip__side wc-live-chip__side--home">
        <span className="wc-live-chip__team">{homeName}</span>
        {homeFlag && <img src={homeFlag} alt="" className="wc-live-chip__flag" />}
      </span>
      <strong className="wc-live-chip__score">
        {liveFixture.home_goals ?? 0}
        <span>:</span>
        {liveFixture.away_goals ?? 0}
      </strong>
      <span className="wc-live-chip__side">
        {awayFlag && <img src={awayFlag} alt="" className="wc-live-chip__flag" />}
        <span className="wc-live-chip__team">{awayName}</span>
      </span>
      <span className="wc-live-chip__minute">{matchStatus}</span>
    </Link>
  )
}
