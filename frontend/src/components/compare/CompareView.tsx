import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fetchPlayerLeads } from '../../api/client'
import type { CompareResponse, PlayerDetail, PlayerEvent, PlayerFixture, PlayerLead, PlayerSeasonStats } from '../../types'
import { competitionLabel } from '../../utils/footballLabels'
import PlayerPortrait from '../shared/PlayerPortrait'

export type Side = 'a' | 'b'

const POSITION: Record<string, string> = {
  GK: 'Portero', DC: 'Central', LAT: 'Lateral', MC: 'Centrocampista', MCO: 'Mediapunta', EXT: 'Extremo', DEL: 'Delantero',
}

export const fmt = {
  int: (value: number) => Math.round(value).toLocaleString('es-ES'),
  dec: (value: number) => value.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  two: (value: number) => value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (value: number) => `${Math.round(value)} %`,
  pts: (value: number) => `${Math.round(value).toLocaleString('es-ES')} pts`,
  mult: (value: number) => `×${value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
}

const shortDate = (iso: string) => new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(new Date(iso)).replace('.', '')

/* ── Butterfly row: the shared comparison primitive ─────────────────────── */

export type Metric = {
  label: string
  a: number | null
  b: number | null
  format: (value: number) => string
  lowerIsBetter?: boolean
  hint?: string
}

export function Butterfly({ metrics, nameA, nameB }: { metrics: Metric[]; nameA?: string; nameB?: string }) {
  return (
    <div className="cv-fly">
      {nameA && nameB && (
        <div className="cv-fly__names" aria-hidden="true"><span className="is-a">{nameA}</span><span className="is-b">{nameB}</span></div>
      )}
      <ul>
        {metrics.filter((metric) => (metric.a ?? 0) !== 0 || (metric.b ?? 0) !== 0).map((metric) => {
          const a = metric.a ?? 0
          const b = metric.b ?? 0
          const max = Math.max(Math.abs(a), Math.abs(b)) || 1
          const tie = a === b || metric.a == null || metric.b == null
          const aWins = !tie && (metric.lowerIsBetter ? a < b : a > b)
          const bWins = !tie && !aWins
          return (
            <li key={metric.label} title={metric.hint}>
              <b className={`cv-fly__val is-a${aWins ? ' is-win' : ''}`}>{metric.a == null ? '—' : metric.format(metric.a)}</b>
              <span className="cv-fly__bar is-a" aria-hidden="true"><i className={aWins ? 'is-win' : undefined} style={{ width: `${(Math.abs(a) / max) * 100}%` }} /></span>
              <span className="cv-fly__label">{metric.label}{metric.hint && <small>{metric.hint}</small>}</span>
              <span className="cv-fly__bar is-b" aria-hidden="true"><i className={bWins ? 'is-win' : undefined} style={{ width: `${(Math.abs(b) / max) * 100}%` }} /></span>
              <b className={`cv-fly__val is-b${bWins ? ' is-win' : ''}`}>{metric.b == null ? '—' : metric.format(metric.b)}</b>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Panel({ title, sub, children, className = '' }: { title: string; sub?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`pf-panel cv-panel ${className}`}>
      <header className="pf-panel__head"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div></header>
      {children}
    </section>
  )
}

/* ── Duel hero ──────────────────────────────────────────────────────────── */

function DuelCard({ player, side, scope, lead }: { player: PlayerDetail; side: Side; scope: string | null; lead: boolean }) {
  return (
    <Link to={`/player/${player.id}${scope ? `?scope=${encodeURIComponent(scope)}` : ''}`} className={`cv-duel__card is-${side}${lead ? ' is-lead' : ''}`}>
      <span className="cv-duel__rank" aria-hidden="true">{player.global_rank > 0 ? player.global_rank : ''}</span>
      <PlayerPortrait player={player} className="cv-duel__photo" eager allowArtwork />
      <span className="cv-duel__copy">
        <span className="cv-duel__meta">{player.team} · {POSITION[player.position] ?? player.position}</span>
        <strong className="cv-duel__name">{player.name}</strong>
        <span className="cv-duel__pts">{fmt.int(player.sfa_pts)}<small> pts SFA</small></span>
        {player.global_rank > 0 && <span className="cv-duel__chip">#{player.global_rank} del ranking</span>}
      </span>
    </Link>
  )
}

export function DuelHero({ data, periodLabel, minutesA, minutesB }: { data: CompareResponse; periodLabel: string; minutesA: number; minutesB: number }) {
  const { player_a: a, player_b: b } = data
  const total = Math.max(a.sfa_pts, 0) + Math.max(b.sfa_pts, 0) || 1
  const share = Math.max(a.sfa_pts, 0) / total
  const diff = a.sfa_pts - b.sfa_pts
  const leader = diff >= 0 ? a : b
  const gap = Math.abs(diff)
  const gapPct = Math.min(a.sfa_pts, b.sfa_pts) > 0 ? (gap / Math.min(a.sfa_pts, b.sfa_pts)) * 100 : null

  return (
    <section className="cv-duel" aria-label="Resumen del duelo">
      <DuelCard player={a} side="a" scope={data.scope} lead={diff >= 0} />
      <div className="cv-duel__center">
        <span className="cv-duel__vs">VS</span>
        <span className="cv-duel__period">{periodLabel}</span>
        <div className="cv-duel__share" aria-label={`${a.name} ${Math.round(share * 100)} % de los puntos, ${b.name} ${Math.round((1 - share) * 100)} %`}>
          <i className="is-a" style={{ flexGrow: share }} />
          <i className="is-b" style={{ flexGrow: 1 - share }} />
        </div>
        <span className="cv-duel__verdict">
          <b>{leader.name.split(' ').slice(-1)[0]}</b> lidera por <b>{fmt.int(gap)} pts</b>{gapPct != null && ` (+${Math.round(gapPct)} %)`}
        </span>
        <span className="cv-duel__sample">{a.matches} PJ · {fmt.int(minutesA)}' &nbsp;|&nbsp; {b.matches} PJ · {fmt.int(minutesB)}'</span>
      </div>
      <DuelCard player={b} side="b" scope={data.scope} lead={diff < 0} />
    </section>
  )
}

/* ── Impact: efficiency + context of decisive actions ───────────────────── */

type ImpactNumbers = {
  per90: number | null
  perMatch: number | null
  decisive: number
  avgDecisive: number | null
  avgMultiplier: number | null
  tight: number | null
  pressure: number | null
  away: number | null
  stage: number | null
  strongRival: number | null
  gamePlayShare: number | null
}

function impactOf(player: PlayerDetail, events: PlayerEvent[], fixtures: PlayerFixture[], minutes: number): ImpactNumbers {
  const actions = events.filter((event) => event.event_type !== 'stats' && event.pts > 0)
  const byFixture = new Map(fixtures.map((fixture) => [fixture.fixture_id, fixture]))
  const share = (test: (event: PlayerEvent) => boolean) => (actions.length ? (actions.filter(test).length / actions.length) * 100 : null)
  const levelOrBehind = (event: PlayerEvent) => {
    const own = byFixture.get(event.fixture_id)?.player_team ?? player.team
    const [home = 0, away = 0] = (event.score_before ?? '0:0').split(':').map(Number)
    return (event.home_team === own ? home - away : away - home) <= 0
  }
  const stats = player.breakdown?.stats?.pts ?? 0
  return {
    per90: minutes > 0 ? (player.sfa_pts / minutes) * 90 : null,
    perMatch: player.matches > 0 ? player.sfa_pts / player.matches : null,
    decisive: actions.length,
    avgDecisive: actions.length ? actions.reduce((sum, event) => sum + event.pts, 0) / actions.length : null,
    avgMultiplier: actions.length ? actions.reduce((sum, event) => sum + event.m1 * event.m2 * event.m3 * event.m4 * event.mvisit, 0) / actions.length : null,
    tight: share(levelOrBehind),
    pressure: share((event) => event.m3 > 1),
    away: share((event) => event.mvisit > 1),
    stage: share((event) => event.m2 > 1),
    strongRival: share((event) => event.m1 >= 1),
    gamePlayShare: player.sfa_pts > 0 ? (stats / player.sfa_pts) * 100 : null,
  }
}

/* ── The single most valuable action, explained in words, not multipliers ── */

/** Turns the engine's factors into plain reasons a fan recognises. */
function reasonsFor(event: PlayerEvent, ownTeam: string) {
  const reasons: Array<{ text: string; up: boolean }> = []
  const [home = 0, away = 0] = (event.score_before ?? '0:0').split(':').map(Number)
  const diff = event.home_team === ownTeam ? home - away : away - home
  if (event.m3 > 1) reasons.push({ text: diff < 0 ? 'Con el equipo perdiendo' : diff === 0 ? 'Con el partido empatado' : 'Momento decisivo', up: true })
  else if (event.m3 < 1) reasons.push({ text: 'Con el partido ya resuelto', up: false })
  if (event.m2 > 1) reasons.push({ text: 'Fase de peso (Champions, final…)', up: true })
  if (event.m1 >= 1) reasons.push({ text: 'Ante un rival de nivel', up: true })
  else if (event.m1 < 0.75) reasons.push({ text: 'Ante un rival menor', up: false })
  if (event.mvisit > 1) reasons.push({ text: 'Jugando fuera de casa', up: true })
  if (event.m4 > 1) reasons.push({ text: 'Remate difícil', up: true })
  else if (event.m4 < 1) reasons.push({ text: 'De penal', up: false })
  return reasons
}

function BestAction({ player, events, fixtures, side }: { player: PlayerDetail; events: PlayerEvent[]; fixtures: PlayerFixture[]; side: Side }) {
  const actions = events.filter((event) => event.event_type !== 'stats' && event.pts > 0)
  const best = actions.reduce<PlayerEvent | null>((top, event) => (!top || event.pts > top.pts ? event : top), null)
  if (!best) return <div className={`cv-act is-${side}`}><span className="cv-act__who">{player.name}</span><p className="cv-act__empty">Sin goles ni asistencias en el periodo</p></div>
  const fixture = fixtures.find((item) => item.fixture_id === best.fixture_id)
  const ownTeam = fixture?.player_team ?? player.team
  const [home = 0, away = 0] = (best.score_before ?? '0:0').split(':').map(Number)
  const isHome = best.home_team === ownTeam
  const after = isHome ? `${home + 1}–${away}` : `${home}–${away + 1}`
  const kind = best.event_type === 'assist' || best.event_type === 'corner_assist' ? 'Asistencia' : best.event_type === 'goal_penalty' ? 'Gol de penal' : 'Gol'
  const average = actions.reduce((sum, event) => sum + event.pts, 0) / actions.length
  const href = fixture?.fixture_external_id ? `/torneos/partido/${fixture.fixture_external_id}` : null
  const body = (
    <>
      <span className="cv-act__who">{player.name}</span>
      <span className="cv-act__match">
        {fixture?.home_team_logo && <img src={fixture.home_team_logo} alt="" width={22} height={22} />}
        <b>{after}</b>
        {fixture?.away_team_logo && <img src={fixture.away_team_logo} alt="" width={22} height={22} />}
      </span>
      <span className="cv-act__what">{kind} en el {best.minute}' · {best.home_team} – {best.away_team}</span>
      <small className="cv-act__meta">{competitionLabel(best.competition)} · {shortDate(best.played_at)}</small>
      <strong className="cv-act__pts">{fmt.int(best.pts)} <small>pts</small></strong>
      <small className="cv-act__ratio">{(best.pts / average).toLocaleString('es-ES', { maximumFractionDigits: 1 })} veces lo que vale su gol o asistencia media</small>
      <ul className="cv-act__why" aria-label="Por qué valió tanto">
        {reasonsFor(best, ownTeam).map((reason) => <li key={reason.text} className={reason.up ? 'is-up' : 'is-down'}>{reason.text}</li>)}
      </ul>
    </>
  )
  return href ? <Link to={href} className={`cv-act is-${side}`}>{body}</Link> : <div className={`cv-act is-${side}`}>{body}</div>
}

export function ImpactPanel({ data, minutesA, minutesB }: { data: CompareResponse; minutesA: number; minutesB: number }) {
  const a = impactOf(data.player_a, data.player_a_analytics.events, data.player_a_analytics.fixtures, minutesA)
  const b = impactOf(data.player_b, data.player_b_analytics.events, data.player_b_analytics.fixtures, minutesB)
  const efficiency: Metric[] = [
    { label: "Puntos SFA por 90'", a: a.per90, b: b.per90, format: fmt.int, hint: 'Igual minutos para los dos' },
    { label: 'Puntos SFA por partido', a: a.perMatch, b: b.perMatch, format: fmt.int },
  ]
  const context: Metric[] = [
    { label: 'Con el partido igualado o en contra', a: a.tight, b: b.tight, format: fmt.pct },
    { label: 'En momentos de presión', a: a.pressure, b: b.pressure, format: fmt.pct, hint: 'Minutos finales o marcador apretado' },
    { label: 'Lejos de casa', a: a.away, b: b.away, format: fmt.pct },
    { label: 'En fases de peso', a: a.stage, b: b.stage, format: fmt.pct, hint: 'Champions, finales o eliminatorias' },
    { label: 'Ante rivales de nivel', a: a.strongRival, b: b.strongRival, format: fmt.pct, hint: 'Equipos fuertes según su nivel' },
  ]
  return (
    <div className="cv-grid-2">
      <Panel title="Cuánto rinden y su acción más valiosa" sub="El rendimiento por minuto y el gol o asistencia que más puntos les dio">
        <Butterfly metrics={efficiency} nameA={data.player_a.name} nameB={data.player_b.name} />
        <div className="cv-acts">
          <BestAction player={data.player_a} events={data.player_a_analytics.events} fixtures={data.player_a_analytics.fixtures} side="a" />
          <BestAction player={data.player_b} events={data.player_b_analytics.events} fixtures={data.player_b_analytics.fixtures} side="b" />
        </div>
      </Panel>
      <Panel title="En qué contexto deciden" sub={`% de sus goles y asistencias (${a.decisive} frente a ${b.decisive})`}>
        <Butterfly metrics={context} nameA={data.player_a.name} nameB={data.player_b.name} />
      </Panel>
    </div>
  )
}

/* ── Chapters: context first, raw numbers second ───────────────────────── */

export function ChapterHead({ index, title, text }: { index: number; title: string; text: string }) {
  return (
    <header className="cv-chapter">
      <span className="cv-chapter__index" aria-hidden="true">{index}</span>
      <div><h2>{title}</h2><p>{text}</p></div>
    </header>
  )
}

/* ── Verdict: resolves "the one behind has better numbers" in plain words ── */

type RawCount = { label: string; a: number; b: number }

function rawCounts(sa: PlayerSeasonStats | null, sb: PlayerSeasonStats | null): RawCount[] {
  if (!sa || !sb) return []
  return [
    { label: 'goles', a: sa.goals, b: sb.goals },
    { label: 'asistencias', a: sa.assists, b: sb.assists },
    { label: 'tiros a puerta', a: sa.shots_on, b: sb.shots_on },
    { label: 'pases clave', a: sa.passes_key, b: sb.passes_key },
    { label: 'regates completados', a: sa.dribbles_won, b: sb.dribbles_won },
    { label: 'duelos ganados', a: sa.duels_won, b: sb.duels_won },
  ]
}

export function Verdict({ data, minutesA, minutesB }: { data: CompareResponse; minutesA: number; minutesB: number }) {
  const leaderSide: Side = data.player_a.sfa_pts >= data.player_b.sfa_pts ? 'a' : 'b'
  const trailerSide: Side = leaderSide === 'a' ? 'b' : 'a'
  const players = { a: data.player_a, b: data.player_b }
  const short = (side: Side) => players[side].name.split(' ').slice(-1)[0]
  const impact = {
    a: impactOf(data.player_a, data.player_a_analytics.events, data.player_a_analytics.fixtures, minutesA),
    b: impactOf(data.player_b, data.player_b_analytics.events, data.player_b_analytics.fixtures, minutesB),
  }
  const relative = (ahead: number, behind: number) => (ahead - behind) / Math.max(Math.abs(behind), 1)

  // Raw counts where the player behind is ahead: the source of the "but his numbers are better" doubt.
  const trailerWins = rawCounts(data.player_a_analytics.stats, data.player_b_analytics.stats)
    .filter((row) => row[trailerSide] > row[leaderSide])
    .sort((x, y) => relative(y[trailerSide], y[leaderSide]) - relative(x[trailerSide], x[leaderSide]))
    .slice(0, 2)

  // What actually moves the SFA total, keeping only the ones where the leader is clearly ahead.
  const playPts = (side: Side) => players[side].breakdown?.stats?.pts ?? 0
  const candidates = [
    { label: 'Cada gol o asistencia vale más', hint: 'puntos de media por acción decisiva', a: impact.a.avgDecisive, b: impact.b.avgDecisive, format: fmt.int },
    { label: 'Decide con el partido igualado o en contra', hint: '% de sus goles y asistencias', a: impact.a.tight, b: impact.b.tight, format: fmt.pct },
    { label: 'Lo hace ante rivales de nivel', hint: '% de sus goles y asistencias', a: impact.a.strongRival, b: impact.b.strongRival, format: fmt.pct },
    { label: 'Más peso en Champions y eliminatorias', hint: '% de sus goles y asistencias', a: impact.a.stage, b: impact.b.stage, format: fmt.pct },
    { label: 'Aporta más con su juego', hint: 'puntos por pases, regates, duelos…', a: playPts('a'), b: playPts('b'), format: fmt.int },
    { label: 'Rinde más por minuto', hint: "puntos SFA por 90'", a: impact.a.per90, b: impact.b.per90, format: fmt.int },
  ]
  const reasons = candidates
    .flatMap((row) => (row.a == null || row.b == null ? [] : [{ ...row, lead: row[leaderSide] as number, rest: row[trailerSide] as number }]))
    .filter((row) => relative(row.lead, row.rest) > 0.08)
    .sort((x, y) => relative(y.lead, y.rest) - relative(x.lead, x.rest))
    .slice(0, 3)

  const list = (items: string[]) => (items.length > 1 ? `${items.slice(0, -1).join(', ')} y ${items[items.length - 1]}` : items[0])

  return (
    <section className={`pf-panel cv-panel cv-verdict is-${leaderSide}`} aria-labelledby="cv-verdict-title">
      <span className="pf-eyebrow">El veredicto</span>
      <h2 id="cv-verdict-title">
        {trailerWins.length > 0 ? (
          <>
            <span className={`is-${trailerSide}`}>{short(trailerSide)}</span> tiene más {list(trailerWins.map((row) => `${row.label} (${row[trailerSide]} frente a ${row[leaderSide]})`))},
            {' '}pero <span className={`is-${leaderSide}`}>{short(leaderSide)}</span> suma más puntos SFA.
          </>
        ) : (
          <><span className={`is-${leaderSide}`}>{short(leaderSide)}</span> manda también en los números brutos, y además sus acciones pesan más.</>
        )}
      </h2>
      {reasons.length > 0 && (
        <>
          <p className="cv-verdict__lead">{trailerWins.length > 0 ? 'Porque SFA no cuenta cuántas veces, sino cuánto vale cada una:' : 'Dónde saca la diferencia:'}</p>
          <ul className="cv-verdict__reasons">
            {reasons.map((row) => (
              <li key={row.label}>
                <span className="cv-verdict__what"><strong>{row.label}</strong><small>{row.hint}</small></span>
                <span className="cv-verdict__nums">
                  <b className={`is-${leaderSide}`}>{row.format(row.lead)}</b>
                  <small>vs</small>
                  <b className={`is-${trailerSide}`}>{row.format(row.rest)}</b>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

/* ── Distinctions: each player's podium places, side by side ────────────── */

const LEAD_TITLES: Record<PlayerLead['metric'], string> = {
  shot_conversion: 'Eficacia de cara a puerta',
  goals_per90: 'Goles por partido',
  goal_contributions_per90: 'Goles y asistencias',
  key_passes_per90: 'Pases clave',
  dribbles_per90: 'Regates completados',
  defensive_actions_per90: 'Entradas e intercepciones',
  duel_win_rate: 'Duelos ganados',
  save_rate: 'Paradas',
  big_game_points_per90: 'Contra los grandes',
}

function leadWhere(lead: PlayerLead) {
  const comp = lead.group.competition_name ? competitionLabel(lead.group.competition_name) : 'Toda la temporada'
  return lead.group.position ? `${comp} · en su posición` : comp
}

export function LeadsDuel({ data }: { data: CompareResponse }) {
  const [leads, setLeads] = useState<{ a: PlayerLead[]; b: PlayerLead[] }>({ a: [], b: [] })
  const scope = data.scope ?? `season-${data.season}`
  useEffect(() => {
    let active = true
    setLeads({ a: [], b: [] })
    Promise.all([fetchPlayerLeads(data.player_a.id, scope), fetchPlayerLeads(data.player_b.id, scope)]).then(([a, b]) => {
      if (active) setLeads({ a: a?.supported ? a.items : [], b: b?.supported ? b.items : [] })
    })
    return () => { active = false }
  }, [data.player_a.id, data.player_b.id, scope])
  if (!leads.a.length && !leads.b.length) return null
  const column = (side: Side, player: PlayerDetail) => (
    <div className={`cv-leads__col is-${side}`}>
      <span className="cv-leads__who">{player.name}</span>
      {leads[side].length ? (
        <ul>
          {leads[side].map((lead) => (
            <li key={lead.metric} className={`is-p${lead.rank}`}>
              <b>#{lead.rank}</b>
              <span><strong>{LEAD_TITLES[lead.metric]}</strong><small>{leadWhere(lead)}</small></span>
            </li>
          ))}
        </ul>
      ) : <p className="cv-leads__none">No está en el podio de ninguna estadística</p>}
    </div>
  )
  return (
    <Panel title="Dónde está entre los mejores" sub="Estadísticas en las que es top 3 frente a jugadores comparables">
      <div className="cv-leads">{column('a', data.player_a)}{column('b', data.player_b)}</div>
    </Panel>
  )
}

/* ── Why one leads: the points gap split by component (adds up exactly) ── */

export type Extras = { titles: number; honors: number }

type Component = { key: string; label: string; hint: string; a: number; b: number }

function componentsOf(player: PlayerDetail, extras: Extras) {
  const bd = player.breakdown ?? {}
  const value = (...keys: string[]) => keys.reduce((sum, key) => sum + (bd[key]?.pts ?? 0), 0)
  const play = value('stats')
  const goals = value('goal', 'goal_penalty')
  const assists = value('assist', 'corner_assist')
  const known = play + goals + assists + extras.titles + extras.honors
  return { play, goals, assists, titles: extras.titles, honors: extras.honors, other: player.sfa_pts - known }
}

export function sourceRows(data: CompareResponse, extrasA: Extras, extrasB: Extras): Component[] {
  const a = componentsOf(data.player_a, extrasA)
  const b = componentsOf(data.player_b, extrasB)
  const rows: Component[] = [
    { key: 'play', label: 'Juego', hint: 'Pases, regates, duelos, recuperaciones… en cada partido', a: a.play, b: b.play },
    { key: 'goals', label: 'Goles', hint: 'Incluye penales, con su contexto', a: a.goals, b: b.goals },
    { key: 'assists', label: 'Asistencias', hint: 'Incluye córners asistidos', a: a.assists, b: b.assists },
    { key: 'titles', label: 'Títulos y fases', hint: 'Campeonatos y rondas alcanzadas', a: a.titles, b: b.titles },
    { key: 'honors', label: 'Distinciones', hint: 'Pichichi, máximo asistidor…', a: a.honors, b: b.honors },
    { key: 'other', label: 'Otros ajustes', hint: 'Bonus de perfil y correcciones', a: a.other, b: b.other },
  ]
  return rows.filter((row) => Math.abs(row.a) >= 1 || Math.abs(row.b) >= 1)
}

function PlayDrivers({ data, minutesA, minutesB }: { data: CompareResponse; minutesA: number; minutesB: number }) {
  const sa = data.player_a_analytics.stats
  const sb = data.player_b_analytics.stats
  if (!sa || !sb) return null
  const p90 = (value: number, minutes: number) => (minutes > 0 ? (value / minutes) * 90 : 0)
  const drivers = [
    { label: 'Regates completados', a: p90(sa.dribbles_won, minutesA), b: p90(sb.dribbles_won, minutesB) },
    { label: 'Duelos ganados', a: p90(sa.duels_won, minutesA), b: p90(sb.duels_won, minutesB) },
    { label: 'Faltas recibidas', a: p90(sa.fouls_drawn, minutesA), b: p90(sb.fouls_drawn, minutesB) },
    { label: 'Pases clave', a: p90(sa.passes_key, minutesA), b: p90(sb.passes_key, minutesB) },
    { label: 'Entradas + intercep.', a: p90(sa.tackles_won + sa.interceptions, minutesA), b: p90(sb.tackles_won + sb.interceptions, minutesB) },
    { label: 'Pases', a: p90(sa.passes_total, minutesA), b: p90(sb.passes_total, minutesB) },
  ]
  return (
    <div className="cv-why__drivers">
      <span className="pf-eyebrow">Qué mueve el juego · por 90'</span>
      <ul>
        {drivers.map((driver) => {
          const lead = driver.a === driver.b ? null : driver.a > driver.b ? 'a' : 'b'
          return (
            <li key={driver.label}>
              <b className={lead === 'a' ? 'is-a' : undefined}>{fmt.dec(driver.a)}</b>
              <span>{driver.label}</span>
              <b className={lead === 'b' ? 'is-b' : undefined}>{fmt.dec(driver.b)}</b>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function WhyPanel({ data, extrasA, extrasB, minutesA, minutesB }: { data: CompareResponse; extrasA: Extras; extrasB: Extras; minutesA: number; minutesB: number }) {
  const rows = sourceRows(data, extrasA, extrasB)
  const gap = data.player_a.sfa_pts - data.player_b.sfa_pts
  const leader = gap >= 0 ? data.player_a : data.player_b
  const leaderSide: Side = gap >= 0 ? 'a' : 'b'
  const maxDiff = Math.max(...rows.map((row) => Math.abs(row.a - row.b)), 1)
  const sorted = [...rows].sort((x, y) => Math.abs(y.a - y.b) - Math.abs(x.a - x.b))
  // Each player's wins summed separately: easier to read than a signed total.
  const gainA = rows.reduce((sum, row) => sum + Math.max(row.a - row.b, 0), 0)
  const gainB = rows.reduce((sum, row) => sum + Math.max(row.b - row.a, 0), 0)
  const short = (name: string) => name.split(' ').slice(-1)[0]

  return (
    <section className="pf-panel cv-panel cv-why" aria-labelledby="cv-why-title">
      <header className="pf-panel__head">
        <div>
          <h2 id="cv-why-title">Por qué lidera {short(leader.name)}</h2>
          <p>La ventaja de <b className={`is-${leaderSide}`}>{fmt.int(Math.abs(gap))} pts</b>, separada por de dónde sale cada punto</p>
        </div>
        <span className="cv-why__legend">
          <span><i className="is-a" />Ventaja de {short(data.player_a.name)}</span>
          <span><i className="is-b" />Ventaja de {short(data.player_b.name)}</span>
        </span>
      </header>

      <ul className="cv-why__rows">
        {sorted.map((row) => {
          const diff = row.a - row.b
          const side: Side = diff >= 0 ? 'a' : 'b'
          const width = (Math.abs(diff) / maxDiff) * 50
          return (
            <li key={row.key}>
              <span className="cv-why__label"><strong>{row.label}</strong><small>{row.hint}</small></span>
              <span className="cv-why__pair">
                <b className="is-a">{fmt.int(row.a)}</b>
                <small>vs</small>
                <b className="is-b">{fmt.int(row.b)}</b>
              </span>
              <span className="cv-why__track" aria-hidden="true">
                <i className={`is-${side}`} style={side === 'a' ? { right: '50%', width: `${width}%` } : { left: '50%', width: `${width}%` }} />
              </span>
              <b className={`cv-why__diff is-${side}`}>+{fmt.int(Math.abs(diff))}<small> para {short(side === 'a' ? data.player_a.name : data.player_b.name)}</small></b>
            </li>
          )
        })}
      </ul>
      <div className="cv-why__total">
        <span><i className="is-a" />{short(data.player_a.name)} saca ventaja en lo suyo: <b className="is-a">+{fmt.int(gainA)}</b></span>
        <span><i className="is-b" />{short(data.player_b.name)} saca ventaja en lo suyo: <b className="is-b">+{fmt.int(gainB)}</b></span>
        <span className="cv-why__net">Ventaja neta de {short(leader.name)}: <b className={`is-${leaderSide}`}>{fmt.int(Math.abs(gap))} pts</b></span>
      </div>
      <PlayDrivers data={data} minutesA={minutesA} minutesB={minutesB} />
    </section>
  )
}

/** Absolute composition: both bars share one scale, so their lengths compare like the totals. */
export function SourcesAbsolute({ data, extrasA, extrasB }: { data: CompareResponse; extrasA: Extras; extrasB: Extras }) {
  const rows = sourceRows(data, extrasA, extrasB).filter((row) => row.key !== 'other')
  const total = (side: Side) => rows.reduce((sum, row) => sum + Math.max(side === 'a' ? row.a : row.b, 0), 0)
  const max = Math.max(total('a'), total('b'), 1)
  const bar = (side: Side, player: PlayerDetail) => (
    <div className={`cv-src is-${side}`}>
      <span className="cv-src__name">{player.name}<b>{fmt.int(player.sfa_pts)} pts</b></span>
      <div className="cv-src__track">
        <div className="cv-src__stack" style={{ width: `${(total(side) / max) * 100}%` }}>
          {rows.map((row) => {
            const value = Math.max(side === 'a' ? row.a : row.b, 0)
            return value > 0 ? (
              <i key={row.key} className={`is-${row.key}`} style={{ flexGrow: value }} title={`${row.label}: ${fmt.int(value)} pts`}>
                {value / max >= 0.09 && <span>{fmt.int(value / 1000)}k</span>}
              </i>
            ) : null
          })}
        </div>
      </div>
    </div>
  )
  return (
    <section className="pf-panel cv-panel">
      <header className="pf-panel__head"><div><h2>De dónde salen sus puntos</h2><p>En puntos, en la misma escala: el largo de cada barra es su total</p></div></header>
      <div className="cv-srcs">
        {bar('a', data.player_a)}
        {bar('b', data.player_b)}
      </div>
      <ul className="cv-src__legend" aria-hidden="true">
        {rows.map((row) => <li key={row.key}><i className={`is-${row.key}`} />{row.label}</li>)}
      </ul>
    </section>
  )
}

/* ── Same calendar, two trends ──────────────────────────────────────────── */

const WINDOW = 5

function rolling(fixtures: PlayerFixture[]) {
  const ordered = [...fixtures].sort((x, y) => x.played_at.localeCompare(y.played_at))
  return ordered.map((fixture, index) => {
    const slice = ordered.slice(Math.max(0, index - WINDOW + 1), index + 1)
    return { fixture, t: new Date(fixture.played_at).getTime(), avg: slice.reduce((sum, item) => sum + item.sfa_pts, 0) / slice.length }
  })
}

export function TrendPanel({ data }: { data: CompareResponse }) {
  const [active, setActive] = useState<{ side: Side; index: number } | null>(null)
  const sa = rolling(data.player_a_analytics.fixtures)
  const sb = rolling(data.player_b_analytics.fixtures)
  const all = [...sa, ...sb]
  if (all.length < 2) return null
  const t0 = Math.min(...all.map((point) => point.t))
  const t1 = Math.max(...all.map((point) => point.t))
  const max = Math.max(...all.map((point) => point.fixture.sfa_pts), 1)
  const x = (t: number) => (t1 === t0 ? 50 : 2 + ((t - t0) / (t1 - t0)) * 96)
  const y = (value: number) => 8 + (1 - value / max) * 80
  const path = (series: typeof sa) => series.reduce((acc, point, index) => {
    const px = x(point.t)
    const py = y(point.avg)
    if (index === 0) return `M${px},${py}`
    const prev = series[index - 1]
    const cx = (x(prev.t) + px) / 2
    return `${acc} C${cx},${y(prev.avg)} ${cx},${py} ${px},${py}`
  }, '')
  const months = new Map<string, number>()
  for (const point of all.sort((p, q) => p.t - q.t)) {
    const key = point.fixture.played_at.slice(0, 7)
    if (!months.has(key)) months.set(key, point.t)
  }
  const monthFmt = new Intl.DateTimeFormat('es-ES', { month: 'short' })
  const ticks = [...months.values()].filter((t, index, list) => index === 0 || x(t) - x(list[index - 1]) >= 5)
  const current = active ? (active.side === 'a' ? sa : sb)[active.index] : null
  const name = active?.side === 'a' ? data.player_a.name : data.player_b.name

  return (
    <Panel title="Evolución en el mismo calendario" sub={`Tendencia de puntos SFA (media de sus últimos ${WINDOW} partidos), fecha a fecha`}>
      <div className="cv-trend" onPointerLeave={() => setActive(null)}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path className="cv-trend__line is-b" d={path(sb)} />
          <path className="cv-trend__line is-a" d={path(sa)} />
        </svg>
        {(['a', 'b'] as const).map((side) => (side === 'a' ? sa : sb).map((point, index) => (
          <span
            key={`${side}-${point.fixture.fixture_id}`}
            className={`cv-trend__dot is-${side}${active?.side === side && active.index === index ? ' is-active' : ''}`}
            style={{ left: `${x(point.t)}%`, top: `${y(point.fixture.sfa_pts)}%` }}
            onPointerEnter={() => setActive({ side, index })}
          />
        )))}
        {ticks.map((t) => (
          <span key={t} className="cv-trend__tick" style={{ left: `${x(t)}%` }}>{monthFmt.format(new Date(t)).replace('.', '')}</span>
        ))}
        {current && active && (
          <div className={`pf-tip cv-trend__tip${x(current.t) > 70 ? ' is-left' : ''}`} style={{ left: `${x(current.t)}%` }} role="status">
            <span className="pf-tip__head"><strong>{name}</strong></span>
            <small>{current.fixture.home_team} – {current.fixture.away_team} · {shortDate(current.fixture.played_at)}</small>
            <b>{fmt.int(current.fixture.sfa_pts)} <em>pts SFA</em></b>
          </div>
        )}
      </div>
      <p className="cv-trend__legend">
        <span><i className="is-a" />{data.player_a.name}</span>
        <span><i className="is-b" />{data.player_b.name}</span>
        <small>Los puntos son cada partido; la línea, su tendencia.</small>
      </p>
    </Panel>
  )
}

/* ── Best performances ──────────────────────────────────────────────────── */

function BestList({ player, fixtures, side, season }: { player: PlayerDetail; fixtures: PlayerFixture[]; side: Side; season: string }) {
  const best = [...fixtures].sort((x, y) => y.sfa_pts - x.sfa_pts).slice(0, 3)
  const team = (fixture: PlayerFixture) => fixture.player_team ?? player.team
  return (
    <div className={`cv-best is-${side}`}>
      <span className="cv-best__name">{player.name}</span>
      {best.length === 0 && <p className="cv-best__empty">Sin partidos puntuados</p>}
      <ol>
        {best.map((fixture) => {
          const home = fixture.home_team === team(fixture)
          const rival = home ? fixture.away_team : fixture.home_team
          const logo = home ? fixture.away_team_logo : fixture.home_team_logo
          const goals = (fixture.breakdown?.goal?.count ?? 0) + (fixture.breakdown?.goal_penalty?.count ?? 0)
          const assists = fixture.breakdown?.assist?.count ?? 0
          const href = fixture.fixture_external_id ? `/torneos/partido/${fixture.fixture_external_id}?season=${season}` : `/player/${player.id}`
          return (
            <li key={fixture.fixture_id}>
              <Link to={href}>
                {logo ? <img src={logo} alt="" width={22} height={22} loading="lazy" /> : <span className="cv-best__noimg" />}
                <span className="cv-best__what">
                  <strong>{home ? 'vs' : 'en'} {rival}</strong>
                  <small>{shortDate(fixture.played_at)} · {competitionLabel(fixture.competition)}{goals + assists > 0 && ` · ${goals ? `${goals}G` : ''}${goals && assists ? ' ' : ''}${assists ? `${assists}A` : ''}`}</small>
                </span>
                <b>{fmt.int(fixture.sfa_pts)}</b>
              </Link>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export function BestPanel({ data }: { data: CompareResponse }) {
  return (
    <Panel title="Sus mejores partidos" sub="Las actuaciones que más pesan en su total">
      <div className="cv-grid-2 cv-grid-2--flat">
        <BestList player={data.player_a} fixtures={data.player_a_analytics.fixtures} side="a" season={data.season} />
        <BestList player={data.player_b} fixtures={data.player_b_analytics.fixtures} side="b" season={data.season} />
      </div>
    </Panel>
  )
}


/* ── Style duel: remate / creación / con balón, the profile cards side by side ── */

function shortName(name: string) {
  return name.split(' ').slice(-1)[0]
}

function Funnel({ stats, side, name }: { stats: PlayerSeasonStats; side: Side; name: string }) {
  const max = Math.max(stats.shots_total, 1)
  return (
    <div className={`cv-funnel is-${side}`}>
      <span className="cv-funnel__name">{name}</span>
      <ul>
        <li style={{ '--w': 1 } as CSSProperties}><b>{stats.shots_total}</b> tiros</li>
        <li className="is-mid" style={{ '--w': stats.shots_on / max } as CSSProperties}><b>{stats.shots_on}</b> a puerta</li>
        <li className="is-top" style={{ '--w': Math.max(stats.goals / max, 0.22) } as CSSProperties}><b>{stats.goals}</b> goles</li>
      </ul>
      <small>{stats.goals > 0 ? `1 gol cada ${fmt.dec(stats.shots_total / stats.goals)} tiros · ${Math.round(stats.minutes / stats.goals)}'` : 'Sin goles'}</small>
    </div>
  )
}

/** Attempted vs completed dribbles: the gap between the two bars is the failure rate. */
function DribbleFunnel({ stats, side, name }: { stats: PlayerSeasonStats; side: Side; name: string }) {
  const tries = Math.max(stats.dribbles_attempts, stats.dribbles_won)
  const pct = tries ? Math.round((stats.dribbles_won / tries) * 100) : null
  return (
    <div className={`cv-funnel is-${side}`}>
      <span className="cv-funnel__name">{name}</span>
      <ul>
        <li style={{ '--w': 1 } as CSSProperties}><b>{tries}</b> intentados</li>
        <li className="is-top" style={{ '--w': Math.max(stats.dribbles_won / Math.max(tries, 1), 0.22) } as CSSProperties}><b>{stats.dribbles_won}</b> completados</li>
      </ul>
      <small>{pct != null ? `${pct} % de acierto · ${fmt.dec((stats.dribbles_won / stats.minutes) * 90)} por 90'` : 'Sin regates'}</small>
    </div>
  )
}

function Dial({ value, side, label }: { value: number; side: Side; label: string }) {
  return (
    <span className={`cv-dial is-${side}`} style={{ '--p': Math.min(Math.max(value, 0), 100) / 100 } as CSSProperties} aria-label={`${label}: ${Math.round(value)} %`}>
      <b>{Math.round(value)}%</b>
    </span>
  )
}

export function StyleDuel({ data }: { data: CompareResponse }) {
  const sa = data.player_a_analytics.stats
  const sb = data.player_b_analytics.stats
  if (!sa || !sb || sa.minutes === 0 || sb.minutes === 0) return null
  const nameA = shortName(data.player_a.name)
  const nameB = shortName(data.player_b.name)
  const p90 = (value: number, minutes: number) => (value / minutes) * 90
  const creation = [
    { label: 'Pases clave', a: p90(sa.passes_key, sa.minutes), b: p90(sb.passes_key, sb.minutes) },
    { label: 'Regates completados', a: p90(sa.dribbles_won, sa.minutes), b: p90(sb.dribbles_won, sb.minutes) },
    { label: 'Faltas recibidas', a: p90(sa.fouls_drawn, sa.minutes), b: p90(sb.fouls_drawn, sb.minutes) },
    { label: 'Asistencias', a: p90(sa.assists, sa.minutes), b: p90(sb.assists, sb.minutes) },
  ]
  const duelPct = (s: PlayerSeasonStats) => (s.duel_win_rate != null ? s.duel_win_rate * 100 : s.duels_total ? (s.duels_won / s.duels_total) * 100 : 0)

  return (
    <div className="cv-style">
      <article className="pf-panel cv-style__card">
        <span className="pf-eyebrow">Remate</span>
        <h3>¿Quién define mejor?</h3>
        <div className="cv-style__pair">
          <Funnel stats={sa} side="a" name={nameA} />
          <Funnel stats={sb} side="b" name={nameB} />
        </div>
        <small className="cv-style__note">Tiros y goles de todos sus partidos según la fuente, también los que SFA no puntúa.</small>
      </article>

      <article className="pf-panel cv-style__card">
        <span className="pf-eyebrow">Regate</span>
        <h3>¿Quién regatea mejor?</h3>
        <div className="cv-style__pair">
          <DribbleFunnel stats={sa} side="a" name={nameA} />
          <DribbleFunnel stats={sb} side="b" name={nameB} />
        </div>
        <small className="cv-style__note">Intentar mucho no es lo mismo que completar: la diferencia entre las dos barras son los regates fallados.</small>
      </article>

      <article className="pf-panel cv-style__card">
        <span className="pf-eyebrow">Creación · por 90'</span>
        <h3>¿Quién genera más?</h3>
        <ul className="cv-create">
          {creation.map((row) => {
            const max = Math.max(row.a, row.b, 0.01)
            return (
              <li key={row.label}>
                <span className="cv-create__label">{row.label}</span>
                <span className="cv-create__bars" aria-hidden="true">
                  <i className="is-a" style={{ width: `${(row.a / max) * 100}%` }} />
                  <i className="is-b" style={{ width: `${(row.b / max) * 100}%` }} />
                </span>
                <span className="cv-create__vals">
                  <b className={row.a >= row.b ? 'is-a' : undefined}>{fmt.dec(row.a)}</b>
                  <b className={row.b > row.a ? 'is-b' : undefined}>{fmt.dec(row.b)}</b>
                </span>
              </li>
            )
          })}
        </ul>
        <small className="cv-style__foot"><i className="is-a" />{nameA} <i className="is-b" />{nameB}</small>
      </article>

      <article className="pf-panel cv-style__card">
        <span className="pf-eyebrow">Con balón</span>
        <h3>¿Quién la cuida y la gana?</h3>
        <div className="cv-dials">
          <div>
            <span className="cv-dials__label">Pases buenos</span>
            <span className="cv-dials__row"><Dial value={sa.passes_accuracy_avg} side="a" label={`${nameA} pases buenos`} /><Dial value={sb.passes_accuracy_avg} side="b" label={`${nameB} pases buenos`} /></span>
            <small>{fmt.int(p90(sa.passes_total, sa.minutes))} vs {fmt.int(p90(sb.passes_total, sb.minutes))} pases por 90'</small>
          </div>
          <div>
            <span className="cv-dials__label">Duelos ganados</span>
            <span className="cv-dials__row"><Dial value={duelPct(sa)} side="a" label={`${nameA} duelos ganados`} /><Dial value={duelPct(sb)} side="b" label={`${nameB} duelos ganados`} /></span>
            <small>{sa.duels_won} vs {sb.duels_won} duelos ganados</small>
          </div>
        </div>
        <small className="cv-style__foot"><i className="is-a" />{nameA} <i className="is-b" />{nameB}</small>
      </article>
    </div>
  )
}

/* ── Detailed stats with tabs ───────────────────────────────────────────── */

export function DetailPanel({ groups, nameA, nameB }: { groups: Array<{ id: string; label: string; metrics: Metric[] }>; nameA: string; nameB: string }) {
  const [tab, setTab] = useState(groups[0]?.id)
  const current = groups.find((group) => group.id === tab) ?? groups[0]
  if (!current) return null
  return (
    <section className="pf-panel cv-panel">
      <header className="pf-panel__head">
        <div><h2>Estadísticas detalladas</h2><p>El dato bruto, para quien quiera bajar al detalle</p></div>
        <div className="tp-segment" role="group" aria-label="Categoría">
          {groups.map((group) => (
            <button type="button" key={group.id} className={group.id === current.id ? 'is-active' : undefined} aria-pressed={group.id === current.id} onClick={() => setTab(group.id)}>
              {group.label}
            </button>
          ))}
        </div>
      </header>
      <Butterfly metrics={current.metrics} nameA={nameA} nameB={nameB} />
    </section>
  )
}

export function sideStyle(): CSSProperties {
  return { '--cv-a': '#d4af55', '--cv-b': '#8fa3b8' } as CSSProperties
}
