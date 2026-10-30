import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchPlayer, fetchPlayerFixtures } from '../../api/client'
import type { PlayerFixture, RankedPlayer, SeasonItem } from '../../types'
import { getSeasonLabel, seasonItemValue } from '../../utils/season'
import PlayerPicker from './PlayerPicker'
import SeasonDropdown from '../shared/SeasonDropdown'
import { ChapterHead, DetailPanel, fmt, type Metric } from './CompareView'

/** Same player, two seasons, first N matches each. Earlier season = B (steel), later season = A (gold). */

const goalsOf = (f: PlayerFixture) => (f.breakdown?.goal?.count ?? 0) + (f.breakdown?.goal_penalty?.count ?? 0)
const assistsOf = (f: PlayerFixture) => (f.breakdown?.assist?.count ?? 0) + (f.breakdown?.corner_assist?.count ?? 0)
const byDate = (a: PlayerFixture, b: PlayerFixture) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime()
const sum = (list: PlayerFixture[], pick: (f: PlayerFixture) => number) => list.reduce((total, f) => total + pick(f), 0)
const per90 = (value: number, minutes: number) => (minutes > 0 ? (value / minutes) * 90 : null)
const last = (values: number[]) => (values.length ? values[values.length - 1] : undefined)
const pct = (num: number, den: number) => (den > 0 ? (num / den) * 100 : null)

function rivalOf(f: PlayerFixture) {
  const home = f.player_team === f.home_team
  return { name: home ? f.away_team : f.home_team, logo: home ? f.away_team_logo : f.home_team_logo, home }
}

function shortSeason(value: string, items: SeasonItem[]) {
  return getSeasonLabel(value, items).replace(/^Temporada\s+/i, '')
}

interface Totals {
  pts: number
  minutes: number
  goals: number
  assists: number
  shots: number
  shotsOn: number
  keyPasses: number
  passes: number
  passesOk: number
  dribbles: number
  duels: number
  defensive: number
  rating: number | null
  best: number | null
}

function totals(list: PlayerFixture[]): Totals {
  const rated = list.filter((f) => f.rating != null)
  return {
    pts: sum(list, (f) => f.sfa_pts),
    minutes: sum(list, (f) => f.minutes),
    goals: sum(list, goalsOf),
    assists: sum(list, assistsOf),
    shots: sum(list, (f) => f.shots_total),
    shotsOn: sum(list, (f) => f.shots_on),
    keyPasses: sum(list, (f) => f.passes_key),
    passes: sum(list, (f) => f.passes_total),
    passesOk: sum(list, (f) => f.passes_accurate),
    dribbles: sum(list, (f) => f.dribbles_won),
    duels: sum(list, (f) => f.duels_won),
    defensive: sum(list, (f) => f.tackles_won + f.interceptions + f.blocks),
    rating: rated.length ? sum(rated, (f) => f.rating ?? 0) / rated.length : null,
    best: list.length ? Math.max(...list.map((f) => f.sfa_pts)) : null,
  }
}

function groups(a: Totals, b: Totals) {
  const m = (label: string, x: number | null, y: number | null, format: (v: number) => string, hint?: string): Metric => ({ label, a: x, b: y, format, hint })
  return [
    { id: 'impact', label: 'Impacto', metrics: [
      m('Puntos SFA', a.pts, b.pts, fmt.int),
      m("Puntos SFA por 90'", per90(a.pts, a.minutes), per90(b.pts, b.minutes), fmt.int),
      m('Mejor partido', a.best, b.best, fmt.pts),
      m('Minutos', a.minutes, b.minutes, fmt.int),
      m('Nota media', a.rating, b.rating, fmt.two),
    ] },
    { id: 'attack', label: 'Ataque', metrics: [
      m('Goles', a.goals, b.goals, fmt.int, 'Goles puntuados por SFA'),
      m('Asistencias', a.assists, b.assists, fmt.int, 'Asistencias puntuadas por SFA'),
      m("Goles + asistencias por 90'", per90(a.goals + a.assists, a.minutes), per90(b.goals + b.assists, b.minutes), fmt.two),
      m('Remates', a.shots, b.shots, fmt.int),
      m('Remates a puerta', a.shotsOn, b.shotsOn, fmt.int),
      m('Conversión de gol', pct(a.goals, a.shots), pct(b.goals, b.shots), fmt.pct),
    ] },
    { id: 'creation', label: 'Creación', metrics: [
      m('Pases clave', a.keyPasses, b.keyPasses, fmt.int),
      m('Precisión de pase', pct(a.passesOk, a.passes), pct(b.passesOk, b.passes), fmt.pct),
      m('Regates completados', a.dribbles, b.dribbles, fmt.int),
      m("Regates completados por 90'", per90(a.dribbles, a.minutes), per90(b.dribbles, b.minutes), fmt.two),
    ] },
    { id: 'defense', label: 'Defensa', metrics: [
      m('Duelos ganados', a.duels, b.duels, fmt.int),
      m("Acciones defensivas por 90'", per90(a.defensive, a.minutes), per90(b.defensive, b.minutes), fmt.two, 'Entradas, intercepciones y bloqueos'),
    ] },
  ]
}

/* ── Cumulative pace chart: the core of the mode ─────────────────────────── */

function PaceChart({ now, before, labelNow, labelBefore }: { now: PlayerFixture[]; before: PlayerFixture[]; labelNow: string; labelBefore: string }) {
  const n = Math.max(now.length, before.length)
  const cumulative = (list: PlayerFixture[]) => list.reduce<number[]>((acc, f) => [...acc, (last(acc) ?? 0) + f.sfa_pts], [])
  const a = cumulative(now)
  const b = cumulative(before)
  const max = Math.max(1, ...a, ...b)
  // Draw at the real pixel width so dots and labels never stretch.
  const ref = useRef<HTMLElement>(null)
  const [W, setW] = useState(640)
  useEffect(() => {
    const node = ref.current
    if (!node || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(([entry]) => setW(Math.max(260, Math.round(entry.contentRect.width))))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  const H = W < 480 ? 200 : 260
  const pad = { l: 8, r: 8, t: 16, b: 26 }
  const x = (i: number) => pad.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - pad.l - pad.r))
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b)
  const path = (values: number[]) => values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const area = (values: number[]) => (values.length ? `${path(values)} L${x(values.length - 1).toFixed(1)},${y(0)} L${x(0)},${y(0)} Z` : '')
  const ticks = [0.5, 1].map((t) => max * t)
  return (
    <figure className="sc-chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`Puntos SFA acumulados: ${labelNow} ${fmt.int(last(a) ?? 0)}, ${labelBefore} ${fmt.int(last(b) ?? 0)}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="sc-chart__grid" x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} />
            <text className="sc-chart__tick" x={pad.l} y={y(t) - 6}>{fmt.int(t)}</text>
          </g>
        ))}
        <line className="sc-chart__base" x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} />
        <path className="sc-chart__area is-a" d={area(a)} />
        <path className="sc-chart__line is-b" d={path(b)} />
        <path className="sc-chart__line is-a" d={path(a)} />
        {b.length > 0 && <circle className="sc-chart__dot is-b" cx={x(b.length - 1)} cy={y(last(b) ?? 0)} r="4" />}
        {a.length > 0 && <circle className="sc-chart__dot is-a" cx={x(a.length - 1)} cy={y(last(a) ?? 0)} r="5" />}
        {Array.from({ length: n }, (_, i) => (
          <text key={i} className="sc-chart__tick" x={x(i)} y={H - 8} textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}>
            {n <= 12 || i % 2 === 0 || i === n - 1 ? i + 1 : ''}
          </text>
        ))}
      </svg>
      <figcaption>
        <span className="is-a">{labelNow}</span>
        <span className="is-b">{labelBefore}</span>
        <small>Puntos SFA acumulados, partido a partido</small>
      </figcaption>
    </figure>
  )
}

/* ── Match-by-match ledger ───────────────────────────────────────────────── */

function MatchCell({ fixture }: { fixture?: PlayerFixture }) {
  if (!fixture) return <div className="sc-ledger__cell is-empty">Sin partido</div>
  const rival = rivalOf(fixture)
  const g = goalsOf(fixture)
  const as = assistsOf(fixture)
  return (
    <div className="sc-ledger__cell">
      <span className="sc-ledger__crest">{rival.logo && <img src={rival.logo} alt="" loading="lazy" />}</span>
      <span className="sc-ledger__rival">
        <strong>{rival.home ? '' : '@ '}{rival.name}</strong>
        <small>{fixture.competition}{g + as > 0 && ` · ${[g && `${g} G`, as && `${as} A`].filter(Boolean).join(' ')}`}</small>
      </span>
      <b>{fmt.int(fixture.sfa_pts)}</b>
    </div>
  )
}

function Ledger({ now, before, labelNow, labelBefore }: { now: PlayerFixture[]; before: PlayerFixture[]; labelNow: string; labelBefore: string }) {
  const n = Math.max(now.length, before.length)
  return (
    <section className="pf-panel cv-panel sc-ledger">
      <header className="pf-panel__head"><div><h2>Partido a partido</h2><p>El mismo número de jornada en cada temporada</p></div></header>
      <div className="sc-ledger__names" aria-hidden="true"><span /><span className="is-a">{labelNow}</span><span className="is-b">{labelBefore}</span></div>
      <ol>
        {Array.from({ length: n }, (_, i) => {
          const pa = now[i]?.sfa_pts ?? null
          const pb = before[i]?.sfa_pts ?? null
          const win = pa != null && pb != null && pa !== pb ? (pa > pb ? 'a' : 'b') : null
          return (
            <li key={i} className={win ? `is-win-${win}` : undefined}>
              <span className="sc-ledger__n">{i + 1}</span>
              <MatchCell fixture={now[i]} />
              <MatchCell fixture={before[i]} />
            </li>
          )
        })}
      </ol>
    </section>
  )
}

/* ── Mode root ───────────────────────────────────────────────────────────── */

export interface SelfParams { player: number | null; now: string; before: string; n: number | null; comp: number | null }

export default function SelfCompare({ seasons, value, onChange }: { seasons: SeasonItem[]; value: SelfParams; onChange: (next: SelfParams) => void }) {
  const periods = useMemo(() => seasons.filter((s) => s.kind === 'award_period'), [seasons])
  const [picked, setPicked] = useState<RankedPlayer | null>(null)
  const [data, setData] = useState<{ now: PlayerFixture[]; before: PlayerFixture[] } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { player, now: scopeNow, before: scopeBefore } = value

  // Restore the picker from a shared link.
  useEffect(() => {
    if (!player || picked?.id === player) return
    fetchPlayer(player).then((p) => setPicked({ ...(p as unknown as RankedPlayer), rank: p.global_rank, goals: p.total_goals, assists: p.total_assists })).catch(() => undefined)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player])

  useEffect(() => {
    if (!player || !scopeNow || !scopeBefore) { setData(null); return undefined }
    let active = true
    setLoading(true)
    setError(null)
    Promise.all([fetchPlayerFixtures(player, undefined, scopeNow), fetchPlayerFixtures(player, undefined, scopeBefore)])
      .then(([a, b]) => {
        if (!active) return
        const played = (list: PlayerFixture[]) => list.filter((f) => f.minutes > 0).sort(byDate)
        setData({ now: played(a), before: played(b) })
      })
      .catch(() => { if (active) setError('No se pudieron cargar los partidos.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [player, scopeNow, scopeBefore])

  // Competitions present in both seasons, so a filter never compares against nothing.
  const competitions = useMemo(() => {
    if (!data) return []
    const ids = new Set(data.before.map((f) => f.competition_id))
    const seen = new Map<number, string>()
    for (const f of data.now) if (f.competition_id != null && ids.has(f.competition_id)) seen.set(f.competition_id, f.competition)
    return [...seen].map(([id, name]) => ({ id, name }))
  }, [data])

  const comp = competitions.some((c) => c.id === value.comp) ? value.comp : null
  const filtered = useMemo(() => {
    if (!data) return null
    const keep = (list: PlayerFixture[]) => (comp == null ? list : list.filter((f) => f.competition_id === comp))
    return { now: keep(data.now), before: keep(data.before) }
  }, [data, comp])

  const maxN = filtered ? Math.max(filtered.now.length, filtered.before.length) : 0
  const defaultN = filtered ? Math.min(filtered.now.length, filtered.before.length) || maxN : 0
  const n = Math.min(Math.max(value.n ?? defaultN, 1), Math.max(maxN, 1))
  const sliceNow = filtered?.now.slice(0, n) ?? []
  const sliceBefore = filtered?.before.slice(0, n) ?? []
  const tNow = useMemo(() => totals(sliceNow), [sliceNow])
  const tBefore = useMemo(() => totals(sliceBefore), [sliceBefore])

  const labelNow = shortSeason(scopeNow, seasons)
  const labelBefore = shortSeason(scopeBefore, seasons)
  const diff = tNow.pts - tBefore.pts
  const name = picked?.name ?? 'El jugador'
  const short = name.split(' ').slice(-1)[0]

  return (
    <>
      <section className="sc-pick" aria-label="Elegir jugador y temporadas">
        <div className="cv-pick__slot is-a sc-pick__player">
          <PlayerPicker label="Jugador" selected={picked} onSelect={(p) => { setPicked(p); onChange({ ...value, player: p.id, n: null, comp: null }) }} onClear={() => { setPicked(null); onChange({ ...value, player: null, n: null, comp: null }) }} scope={scopeNow} />
        </div>
        <div className="sc-pick__season is-a">
          <span className="sc-pick__label">Comparar</span>
          <SeasonDropdown items={periods} value={scopeNow} onChange={(s) => onChange({ ...value, now: s, n: null })} includeAll={false} />
        </div>
        <span className="sc-pick__vs" aria-hidden="true">vs</span>
        <div className="sc-pick__season is-b">
          <span className="sc-pick__label">Contra</span>
          <SeasonDropdown items={periods} value={scopeBefore} onChange={(s) => onChange({ ...value, before: s, n: null })} includeAll={false} />
        </div>
      </section>

      {loading && <div className="cv-loading" role="status"><span className="sr-only">Cargando partidos</span><div className="cv-skel cv-skel--hero" /></div>}
      {!loading && error && <div className="cv-state" role="alert">{error}</div>}

      {!loading && !error && !player && (
        <section className="cv-empty">
          <span className="cv-empty__vs" aria-hidden="true">1×2</span>
          <h2>Elige un jugador</h2>
          <p>Compara su arranque de temporada con el de otra: los mismos partidos, uno al lado del otro.</p>
        </section>
      )}

      {!loading && !error && filtered && player && scopeNow === scopeBefore && (
        <div className="cv-state">Elige dos temporadas distintas.</div>
      )}

      {!loading && !error && filtered && player && scopeNow !== scopeBefore && (
        <div className="cv-results">
          <section className="sc-hero">
            <div className="sc-hero__who">
              {picked?.photo_url && <img src={picked.photo_url} alt="" />}
              <div>
                <span className="pf-eyebrow">Primeros {n} partidos{comp != null ? ` · ${competitions.find((c) => c.id === comp)?.name}` : ''}</span>
                <h2>{name}</h2>
              </div>
            </div>
            <div className="sc-hero__score">
              <div className="is-a"><small>{labelNow}</small><b>{fmt.int(tNow.pts)}</b><span>{tNow.goals} G · {tNow.assists} A · {sliceNow.length} PJ</span></div>
              <div className="is-b"><small>{labelBefore}</small><b>{fmt.int(tBefore.pts)}</b><span>{tBefore.goals} G · {tBefore.assists} A · {sliceBefore.length} PJ</span></div>
            </div>
            <p className="sc-hero__verdict">
              {sliceNow.length === 0 || sliceBefore.length === 0
                ? 'Falta una de las dos temporadas en este filtro.'
                : diff === 0
                  ? `${short} va exactamente al mismo ritmo que en ${labelBefore}.`
                  : <>{short} va <strong className={diff > 0 ? 'is-a' : 'is-b'}>{fmt.int(Math.abs(diff))} pts {diff > 0 ? 'por encima' : 'por debajo'}</strong> de su arranque en {labelBefore}{tBefore.pts > 0 && ` (${diff > 0 ? '+' : '−'}${Math.round(Math.abs(diff) / tBefore.pts * 100)} %)`}.</>}
            </p>
          </section>

          <section className="sc-controls" aria-label="Periodo">
            <div className="sc-steps">
              <span className="sc-pick__label">Partidos</span>
              <div className="sc-steps__ctrl">
                <button type="button" onClick={() => onChange({ ...value, n: n - 1 })} disabled={n <= 1} aria-label="Un partido menos">−</button>
                <output aria-live="polite">{n}</output>
                <button type="button" onClick={() => onChange({ ...value, n: n + 1 })} disabled={n >= maxN} aria-label="Un partido más">+</button>
              </div>
              {n !== defaultN && <button type="button" className="sc-steps__reset" onClick={() => onChange({ ...value, n: null })}>Igualar ({defaultN})</button>}
            </div>
            {competitions.length > 1 && (
              <div className="tp-segment sc-comps" role="group" aria-label="Competición">
                <button type="button" className={comp == null ? 'is-active' : undefined} aria-pressed={comp == null} onClick={() => onChange({ ...value, comp: null, n: null })}>Todas</button>
                {competitions.map((c) => (
                  <button type="button" key={c.id} className={comp === c.id ? 'is-active' : undefined} aria-pressed={comp === c.id} onClick={() => onChange({ ...value, comp: c.id, n: null })}>{c.name}</button>
                ))}
              </div>
            )}
          </section>

          <ChapterHead index={1} title="El ritmo" text="Cómo se fueron sumando los puntos SFA en cada temporada, con el mismo número de partidos." />
          <PaceChart now={sliceNow} before={sliceBefore} labelNow={labelNow} labelBefore={labelBefore} />
          <Ledger now={sliceNow} before={sliceBefore} labelNow={labelNow} labelBefore={labelBefore} />

          <ChapterHead index={2} title="Los números brutos" text="Lo que hizo en esos partidos, sin contexto." />
          <DetailPanel groups={groups(tNow, tBefore)} nameA={labelNow} nameB={labelBefore} />
        </div>
      )}
    </>
  )
}
