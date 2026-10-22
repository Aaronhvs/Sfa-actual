import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { PlayerEvent, PlayerFixture } from '../../types'
import { competitionLabel } from '../../utils/footballLabels'
import ProfileLeads from './ProfileLeads'
import { Venue, actionReasons, matchHref, rivalOf } from './ProfileView'

/* ── "Lo más destacado": two signature moments + a ledger of season records ── */

const pts = (value: number) => Math.round(value).toLocaleString('es-ES')
const shortDate = (iso: string) => new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(new Date(iso)).replace('.', '')
const goalsIn = (f: PlayerFixture) => (f.breakdown?.goal?.count ?? 0) + (f.breakdown?.goal_penalty?.count ?? 0)
const assistsIn = (f: PlayerFixture) => f.breakdown?.assist?.count ?? 0
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

type Moment = { kind: 'goal' | 'assist'; event: PlayerEvent; fixture: PlayerFixture }
type RecordRow = { key: string; value: number; display?: string; label: string; items: Array<{ fixture: PlayerFixture; extra: string }> }

function Crest({ src, name, size }: { src: string | null; name: string; size: number }) {
  return src
    ? <img className="pf-crest" src={src} alt="" title={name} width={size} height={size} loading="lazy" decoding="async" />
    : <span className="pf-crest pf-crest--fallback" style={{ width: size, height: size }} aria-hidden="true">{name.slice(0, 2).toUpperCase()}</span>
}

/** Scoreboard before and after the action: the goal (or the goal it set up) lands on the player's side. */
function Scoreline({ event, fixture, team }: { event: PlayerEvent; fixture: PlayerFixture; team: string }) {
  const own = fixture.player_team ?? team
  if (!event.score_before) return null
  const [home = 0, away = 0] = event.score_before.split(':').map(Number)
  const ownHome = event.home_team === own
  const after = ownHome ? [home + 1, away] : [home, away + 1]
  return (
    <span className="pf-mo__score" aria-label={`Marcador ${home}-${away}, después ${after[0]}-${after[1]}`}>
      <Crest src={fixture.home_team_logo} name={fixture.home_team} size={22} />
      <span className="pf-mo__before">{home}-{away}</span>
      <svg viewBox="0 0 16 10" width="14" height="10" aria-hidden="true"><path d="M1 5h12M9 1l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <b className={ownHome ? 'is-left' : 'is-right'}><span>{after[0]}</span>-<span>{after[1]}</span></b>
      <Crest src={fixture.away_team_logo} name={fixture.away_team} size={22} />
    </span>
  )
}

function MomentCard({ moment, team, season }: { moment: Moment; team: string; season: string }) {
  const { event, fixture, kind } = moment
  const rival = rivalOf(fixture, team)
  const href = matchHref(fixture, season)
  const reasons = actionReasons(event, fixture.player_team ?? team).filter((reason) => reason.up)
  const body = (
    <>
      <span className="pf-mo__kind">{kind === 'goal' ? 'Su gol más valioso' : 'Su asistencia más valiosa'}</span>
      <span className="pf-mo__minute" aria-label={`Minuto ${event.minute}`}>{event.minute}<small>'</small></span>
      <Scoreline event={event} fixture={fixture} team={team} />
      {reasons.length > 0 && (
        <span className="pf-mo__tags">{reasons.map((reason) => <em key={reason.text}>{reason.text}</em>)}</span>
      )}
      <span className="pf-mo__foot">
        <span className="pf-mo__where">
          <span className="pf-mo__rival"><Venue home={rival.home} />{rival.name}</span>
          <small>{competitionLabel(fixture.competition)} · {shortDate(fixture.played_at)}</small>
        </span>
        <b className="pf-mo__pts">+{pts(event.pts)}<em>pts</em></b>
      </span>
    </>
  )
  const className = `pf-mo pf-mo--${kind}`
  return href ? <Link to={href} className={className}>{body}</Link> : <article className={className}>{body}</article>
}

function bestOf(fixtures: PlayerFixture[], extra: (f: PlayerFixture) => string, label: string, key: string): RecordRow | null {
  if (fixtures.length === 0) return null
  const items = [...fixtures].sort((a, b) => b.sfa_pts - a.sfa_pts).map((fixture) => ({ fixture, extra: extra(fixture) }))
  return { key, value: fixtures.length, label, items }
}

function buildRecords(fixtures: PlayerFixture[]): RecordRow[] {
  const goalsLabel = (f: PlayerFixture) => plural(goalsIn(f), 'gol', 'goles')
  const rows: Array<RecordRow | null> = []

  const hatTricks = fixtures.filter((f) => goalsIn(f) >= 3)
  rows.push(bestOf(hatTricks, goalsLabel, hatTricks.length === 1 ? 'Hat-trick' : 'Hat-tricks', 'hat'))
  const braces = fixtures.filter((f) => goalsIn(f) === 2)
  rows.push(bestOf(braces, goalsLabel, braces.length === 1 ? 'Doblete' : 'Dobletes', 'brace'))
  rows.push(bestOf(
    fixtures.filter((f) => goalsIn(f) > 0 && assistsIn(f) > 0),
    (f) => `${goalsLabel(f)} y ${plural(assistsIn(f), 'asistencia', 'asistencias')}`,
    'Partidos marcando y asistiendo', 'both',
  ))
  rows.push(bestOf(
    fixtures.filter((f) => assistsIn(f) >= 2),
    (f) => plural(assistsIn(f), 'asistencia', 'asistencias'),
    'Partidos con 2 o más asistencias', 'assists',
  ))

  // Longest run of consecutive matches with a goal or an assist.
  const byDate = [...fixtures].sort((a, b) => a.played_at.localeCompare(b.played_at))
  let run: PlayerFixture[] = []
  let longest: PlayerFixture[] = []
  for (const f of byDate) {
    run = goalsIn(f) + assistsIn(f) > 0 ? [...run, f] : []
    if (run.length > longest.length) longest = run
  }
  if (longest.length >= 3) {
    rows.push({
      key: 'run',
      value: longest.length,
      label: 'Partidos seguidos marcando o asistiendo',
      items: [...longest].reverse().map((fixture) => ({
        fixture,
        extra: [goalsIn(fixture) && plural(goalsIn(fixture), 'gol', 'goles'), assistsIn(fixture) && plural(assistsIn(fixture), 'asist.', 'asist.')].filter(Boolean).join(' · '),
      })),
    })
  }

  const topDribbles = fixtures.reduce((best, f) => (f.dribbles_won > best.dribbles_won ? f : best), fixtures[0])
  if (topDribbles.dribbles_won >= 5) {
    rows.push({ key: 'dribbles', value: topDribbles.dribbles_won, label: 'Regates en un partido, su récord', items: [{ fixture: topDribbles, extra: `${topDribbles.dribbles_won} regates` }] })
  }

  const defence = (f: PlayerFixture) => f.tackles_won + f.interceptions + f.blocks
  const topDefence = fixtures.reduce((best, f) => (defence(f) > defence(best) ? f : best), fixtures[0])
  if (defence(topDefence) >= 7) {
    rows.push({ key: 'defence', value: defence(topDefence), label: 'Recuperaciones en un partido, su récord', items: [{ fixture: topDefence, extra: 'entradas, intercepciones y bloqueos' }] })
  }

  // Single-match peaks so every role gets a record, not only scorers.
  const peak = (key: string, label: string, value: (f: PlayerFixture) => number, min: number, unit: string) => {
    const top = fixtures.reduce((best, f) => (value(f) > value(best) ? f : best), fixtures[0])
    if (value(top) >= min) rows.push({ key, value: value(top), label, items: [{ fixture: top, extra: `${value(top)} ${unit}` }] })
  }
  const rated = fixtures.filter((f) => f.rating != null)
  const topRated = rated.reduce<PlayerFixture | null>((best, f) => (!best || (f.rating ?? 0) > (best.rating ?? 0) ? f : best), null)
  if (topRated?.rating != null && topRated.rating >= 7.5) {
    const note = topRated.rating.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
    rows.push({ key: 'rating', value: topRated.rating, display: note, label: 'Su mejor nota en un partido', items: [{ fixture: topRated, extra: `nota ${note}` }] })
  }
  peak('keypasses', 'Pases clave en un partido, su récord', (f) => f.passes_key, 3, 'pases clave')
  peak('duels', 'Duelos ganados en un partido, su récord', (f) => f.duels_won, 7, 'duelos')

  const penalties = fixtures.filter((f) => (f.breakdown?.penalty_won?.count ?? 0) > 0)
  const penaltyTotal = penalties.reduce((sum, f) => sum + (f.breakdown?.penalty_won?.count ?? 0), 0)
  if (penaltyTotal > 0) {
    rows.push({
      key: 'penalties', value: penaltyTotal, label: penaltyTotal === 1 ? 'Penal provocado' : 'Penales provocados',
      items: penalties.map((fixture) => ({ fixture, extra: plural(fixture.breakdown?.penalty_won?.count ?? 0, 'penal', 'penales') })),
    })
  }

  return rows.filter((row): row is RecordRow => row !== null).slice(0, 6)
}

function RecordLedger({ rows, team, season }: { rows: RecordRow[]; team: string; season: string }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <ol className="pf-rec">
      {rows.map((row) => {
        const lead = row.items[0]
        const rival = rivalOf(lead.fixture, team)
        const isOpen = open === row.key
        const expandable = row.items.length > 1
        const summary = (
          <>
            <b className="pf-rec__value">{row.display ?? row.value}</b>
            <span className="pf-rec__copy">
              <strong>{row.label}</strong>
              <small>{expandable ? 'El mejor: ' : ''}<Venue home={rival.home} />{rival.name} · {shortDate(lead.fixture.played_at)}</small>
            </span>
          </>
        )
        return (
          <li key={row.key} className={isOpen ? 'is-open' : undefined}>
            {expandable ? (
              <button type="button" className="pf-rec__row" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : row.key)}>
                {summary}
                <svg className="pf-rec__chev" viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
            ) : (
              (() => {
                const href = matchHref(lead.fixture, season)
                return href
                  ? <Link to={href} className="pf-rec__row">{summary}<span className="pf-rec__go" aria-hidden="true">→</span></Link>
                  : <div className="pf-rec__row">{summary}</div>
              })()
            )}
            {isOpen && (
              <ul className="pf-rec__list">
                {row.items.map(({ fixture, extra }) => {
                  const r = rivalOf(fixture, team)
                  const href = matchHref(fixture, season)
                  const line = (
                    <>
                      <span className="pf-rec__date">{shortDate(fixture.played_at)}</span>
                      <Crest src={r.logo} name={r.name} size={18} />
                      <span className="pf-rec__rival">{r.name}</span>
                      <span className="pf-rec__extra">{extra}</span>
                      <b>{pts(fixture.sfa_pts)}</b>
                    </>
                  )
                  return <li key={fixture.fixture_id}>{href ? <Link to={href}>{line}</Link> : <span>{line}</span>}</li>
                })}
              </ul>
            )}
          </li>
        )
      })}
    </ol>
  )
}

export default function ProfileMoments({ playerId, scope, fixtures, events, team, season }: {
  playerId: number
  scope: string
  fixtures: PlayerFixture[]
  events: PlayerEvent[]
  team: string
  season: string
}) {
  const { moments, records } = useMemo(() => {
    const byId = new Map(fixtures.map((f) => [f.fixture_id, f]))
    const top = (types: string[]) => events
      .filter((e) => types.includes(e.event_type) && e.pts > 0 && byId.has(e.fixture_id))
      .reduce<PlayerEvent | null>((best, e) => (!best || e.pts > best.pts ? e : best), null)
    const goal = top(['goal', 'goal_penalty'])
    const assist = top(['assist'])
    const list: Moment[] = []
    if (goal) list.push({ kind: 'goal', event: goal, fixture: byId.get(goal.fixture_id)! })
    if (assist) list.push({ kind: 'assist', event: assist, fixture: byId.get(assist.fixture_id)! })
    return { moments: list, records: fixtures.length ? buildRecords(fixtures) : [] }
  }, [fixtures, events])

  if (moments.length === 0 && records.length === 0) return null

  return (
    <div className={`pf-moments${moments.length === 0 || records.length === 0 ? ' is-single' : ''}`}>
      <div className="pf-moments__main">
        {moments.length > 0 && (
          <div className="pf-moments__cards">
            {moments.map((moment) => <MomentCard key={moment.kind} moment={moment} team={team} season={season} />)}
          </div>
        )}
        <ProfileLeads playerId={playerId} scope={scope} />
      </div>
      {records.length > 0 && (
        <section className="pf-moments__records" aria-label="Récords de la temporada">
          <h3>Récords de la temporada</h3>
          <RecordLedger rows={records} team={team} season={season} />
        </section>
      )}
    </div>
  )
}
