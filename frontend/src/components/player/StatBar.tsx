import type { PlayerDetail, PlayerFixture, PlayerSeasonStats } from '../../types'

interface Props {
  player: PlayerDetail
  fixtures: PlayerFixture[]
  seasonStats?: PlayerSeasonStats | null
}

interface StatItem {
  label: string
  value: string | number
  sub?: string
  gold?: boolean
  warn?: boolean
}

function fmt(n: number): string {
  return n.toLocaleString('es-ES')
}

function Item({ item }: { item: StatItem }) {
  return (
    <div className={`stat-bar__item${item.gold ? ' stat-bar__item--gold' : ''}${item.warn ? ' stat-bar__item--warn' : ''}`}>
      <span className={`stat-bar__num${item.gold ? ' stat-bar__num--gold' : ''}${item.warn ? ' stat-bar__num--warn' : ''}`}>
        {item.value}
      </span>
      <span className="stat-bar__label">{item.label}</span>
      {item.sub && <span className="stat-bar__sub">{item.sub}</span>}
    </div>
  )
}

export default function StatBar({ player, fixtures, seasonStats }: Props) {
  const agg = fixtures.reduce(
    (acc, f) => ({
      shots_on:     acc.shots_on     + (f.shots_on     ?? 0),
      dribbles_won: acc.dribbles_won + (f.dribbles_won ?? 0),
      duels_won:    acc.duels_won    + (f.duels_won    ?? 0),
      tackles:      acc.tackles      + (f.tackles_won  ?? 0) + (f.interceptions ?? 0),
      blocks:       acc.blocks       + (f.blocks       ?? 0),
      fouls_drawn:  acc.fouls_drawn  + (f.fouls_drawn  ?? 0),
    }),
    { shots_on: 0, dribbles_won: 0, duels_won: 0, tackles: 0, blocks: 0, fouls_drawn: 0 },
  )

  const totalMinutes = fixtures.reduce((acc, f) => acc + (f.minutes ?? 0), 0)

  const goalParticipations = player.total_goals + player.total_assists
  const minPerParticipation = goalParticipations > 0 && totalMinutes > 0
    ? Math.round(totalMinutes / goalParticipations)
    : null

  const primary: StatItem[] = [
    { label: 'Partidos',     value: player.matches },
    { label: 'Minutos',      value: totalMinutes.toLocaleString('es-ES') },
    { label: 'Goles',        value: player.total_goals },
    { label: 'Asistencias',  value: player.total_assists },
    ...(minPerParticipation !== null ? [{
      label: 'Min/Part.',
      value: minPerParticipation,
      sub: '1 gol o asist.',
      gold: true,
    }] : []),
    ...(!seasonStats ? [{ label: 'Disparos', value: agg.shots_on }] : []),
    { label: 'Regates',      value: agg.dribbles_won },
    { label: 'Duelos gan.',  value: agg.duels_won },
    { label: 'Tackles/Int.', value: agg.tackles },
    { label: 'Bloqueos',     value: agg.blocks },
    { label: 'Faltas rec.',  value: agg.fouls_drawn },
  ]

  const advanced: StatItem[] = seasonStats ? (() => {
    const s = seasonStats
    const isGK = player.position === 'GK'
    const passesCompleted = s.passes_accuracy_avg > 0
      ? Math.round(s.passes_total * s.passes_accuracy_avg / 100)
      : s.passes_total
    return [
      {
        label: 'Pases comp.',
        value: fmt(passesCompleted),
        sub: s.passes_accuracy_avg > 0 ? `${Math.round(s.passes_accuracy_avg)}% prec.` : undefined,
      },
      {
        label: 'Disparos tot.',
        value: fmt(s.shots_total),
        sub: s.shots_on > 0 ? `${fmt(s.shots_on)} a puerta` : undefined,
      },
      {
        label: 'Duelos tot.',
        value: fmt(s.duels_total),
        sub: s.duel_win_rate != null ? `${Math.round(s.duel_win_rate * 100)}% gan.` : undefined,
      },
      ...(isGK || player.position === 'DF' ? [{ label: 'Reg. sufridos', value: fmt(s.dribbles_past) }] : []),
      { label: 'Penales gen.',  value: fmt(s.penalty_won) },
      { label: 'Faltas com.',   value: fmt(s.fouls_committed), warn: s.fouls_committed > 40 },
      { label: 'T. amarillas',  value: fmt(s.cards_yellow), warn: s.cards_yellow > 0 },
      { label: 'T. rojas',      value: fmt(s.cards_red), warn: s.cards_red > 0 },
      ...(isGK ? [
        { label: 'Paradas',    value: fmt(s.saves) },
        { label: 'Goles rec.', value: fmt(s.goals_conceded), warn: true },
      ] : []),
    ]
  })() : []

  return (
    <div className="stat-bar">
      <div className="stat-bar__group">
        {primary.map((item) => <Item key={item.label} item={item} />)}
      </div>
      {advanced.length > 0 && (
        <>
          <p className="stat-bar__section-label">Estadísticas técnicas</p>
          <div className="stat-bar__group">
            {advanced.map((item) => <Item key={item.label} item={item} />)}
          </div>
        </>
      )}
    </div>
  )
}
