import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchWcLive } from '../../api/client'

export default function WcLiveChip() {
  const [hasLive, setHasLive] = useState(false)
  const [liveCount, setLiveCount] = useState(0)

  useEffect(() => {
    function check() {
      fetchWcLive()
        .then((res) => {
          setHasLive(res.has_live)
          setLiveCount(res.live.length)
        })
        .catch(() => {})
    }
    check()
    const timer = setInterval(check, 60_000)
    return () => clearInterval(timer)
  }, [])

  if (!hasLive) return null

  return (
    <Link to="/mundial" className="wc-live-chip" aria-label={`${liveCount} partido${liveCount > 1 ? 's' : ''} del Mundial en vivo. Ver partidos`}>
      <span className="wc-live-chip__dot" aria-hidden="true" />
      <span className="wc-live-chip__text">
        {liveCount > 1 ? `${liveCount} en vivo` : 'EN VIVO'}
      </span>
      <span className="wc-live-chip__label">Mundial</span>
    </Link>
  )
}
