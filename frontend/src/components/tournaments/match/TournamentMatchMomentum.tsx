import type { TournamentMatchMomentumBucket } from '../../../types'

export default function TournamentMatchMomentum({
  buckets,
  homeName,
  awayName,
}: {
  buckets: TournamentMatchMomentumBucket[]
  homeName: string
  awayName: string
}) {
  if (buckets.length === 0) {
    return (
      <section className="trm-section trm-momentum">
        <header><span>Ritmo del partido</span><h2>Impacto SFA por tramo</h2></header>
        <div className="trm-empty">Impacto SFA pendiente de cálculo.</div>
      </section>
    )
  }

  const maximum = Math.max(...buckets.flatMap((item) => [item.home_points, item.away_points]), 1)
  return (
    <section className="trm-section trm-momentum">
      <header className="trm-section__split">
        <div><span>Ritmo del partido</span><h2>Impacto SFA por tramo</h2></div>
        <div className="trm-momentum__legend" aria-label="Leyenda">
          <span><i className="is-home" />{homeName}</span>
          <span><i className="is-away" />{awayName}</span>
        </div>
      </header>
      <p className="trm-section__description">Puntos generados por acciones calculadas en cada tramo de cinco minutos.</p>
      <div className="trm-momentum__chart" role="img" aria-label={`Impacto de ${homeName} arriba y ${awayName} abajo`}>
        {buckets.map((bucket) => {
          const homeHeight = Math.max((bucket.home_points / maximum) * 42, bucket.home_points > 0 ? 3 : 0)
          const awayHeight = Math.max((bucket.away_points / maximum) * 42, bucket.away_points > 0 ? 3 : 0)
          return (
            <div className="trm-momentum__bucket" key={bucket.minute_start} title={`${bucket.minute_start}-${bucket.minute_end}': ${homeName} ${Math.round(bucket.home_points)} pts · ${awayName} ${Math.round(bucket.away_points)} pts`}>
              <i className="is-home" style={{ height: `${homeHeight}%` }} />
              <i className="is-away" style={{ height: `${awayHeight}%` }} />
              <span>{bucket.minute_start % 15 === 0 ? `${bucket.minute_start}'` : ''}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
