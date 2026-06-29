import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import type {
  WcFixture,
  WcFixturesResponse,
  WcStanding,
  WcStandingsResponse,
  WcTeamSFARankingItem,
} from '../types'
import { fetchWcFixtures, fetchWcLive, fetchWcStandings, fetchWcTeamSFARanking } from '../api/client'
import { worldCupTeamName, worldCupStageLabel } from '../utils/worldCupTeams'

type MundialView = 'matches' | 'standings' | 'bracket' | 'teams'
type MatchTone = 'live' | 'result' | 'upcoming'

const FINISHED_STATUSES = new Set(['FT', 'AET', 'PEN'])
const KNOCKOUT_MARKERS = [
  'round of 32',
  'round of 16',
  'last 16',
  'quarter',
  'semi',
  'final',
  '3rd place',
]

const TEAM_LOGO = (externalId: number | null) =>
  externalId ? `https://media.api-sports.io/football/teams/${externalId}.png` : null

const TEAM_CODES_BY_EXTERNAL_ID: Record<number, string> = {
  1: 'BEL',
  2: 'FRA',
  3: 'CRO',
  5: 'SWE',
  6: 'BRA',
  7: 'URU',
  8: 'COL',
  9: 'ESP',
  10: 'ENG',
  11: 'PAN',
  12: 'JPN',
  13: 'SEN',
  15: 'SUI',
  16: 'MEX',
  17: 'KOR',
  20: 'AUS',
  22: 'IRN',
  23: 'KSA',
  25: 'GER',
  26: 'ARG',
  27: 'POR',
  28: 'TUN',
  31: 'MAR',
  32: 'EGY',
  770: 'CZE',
  775: 'AUT',
  777: 'TUR',
  1090: 'NOR',
  1108: 'SCO',
  1113: 'BIH',
  1118: 'NED',
  1501: 'CIV',
  1504: 'GHA',
  1508: 'COD',
  1531: 'RSA',
  1532: 'ALG',
  1533: 'CPV',
  1548: 'JOR',
  1567: 'IRQ',
  1568: 'UZB',
  1569: 'QAT',
  2380: 'PAR',
  2382: 'ECU',
  2384: 'USA',
  2386: 'HAI',
  4673: 'NZL',
  5529: 'CAN',
  5530: 'CUW',
}

const ROUND32_BRACKET_ORDER: Array<[string, string]> = [
  ['GER', 'PAR'],
  ['FRA', 'SWE'],
  ['RSA', 'CAN'],
  ['NED', 'MAR'],
  ['POR', 'CRO'],
  ['ESP', 'AUT'],
  ['USA', 'BIH'],
  ['BEL', 'SEN'],
  ['BRA', 'JPN'],
  ['CIV', 'NOR'],
  ['MEX', 'ECU'],
  ['ENG', 'COD'],
  ['ARG', 'CPV'],
  ['AUS', 'EGY'],
  ['SUI', 'ALG'],
  ['COL', 'GHA'],
]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function dateKey(iso: string): string {
  const date = new Date(iso)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function compactDateLabel(key: string): string {
  return new Date(`${key}T12:00:00`).toLocaleDateString('es-ES', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function uniqueDateOptions(fixtures: WcFixture[], direction: 'asc' | 'desc') {
  const keys = Array.from(new Set(fixtures.map((fixture) => dateKey(fixture.played_at))))
  return keys
    .sort((a, b) => direction === 'asc' ? a.localeCompare(b) : b.localeCompare(a))
    .map((key) => ({ key, label: compactDateLabel(key) }))
}

function isKnockout(fixture: WcFixture): boolean {
  const stage = fixture.stage.toLowerCase()
  return KNOCKOUT_MARKERS.some((marker) => stage.includes(marker))
}

function teamCode(team: WcFixture['home_team'] | null, fallback = 'TBD'): string {
  if (!team) return fallback
  if (team.external_id != null && TEAM_CODES_BY_EXTERNAL_ID[team.external_id]) {
    return TEAM_CODES_BY_EXTERNAL_ID[team.external_id]
  }
  return worldCupTeamName(team).normalize('NFD').replace(/[\u0300-\u036f]/g, '').slice(0, 3).toUpperCase()
}

function round32OrderIndex(fixture: WcFixture): number {
  const home = teamCode(fixture.home_team)
  const away = teamCode(fixture.away_team)
  const direct = ROUND32_BRACKET_ORDER.findIndex(([a, b]) => a === home && b === away)
  if (direct >= 0) return direct
  const reverse = ROUND32_BRACKET_ORDER.findIndex(([a, b]) => a === away && b === home)
  return reverse >= 0 ? reverse : ROUND32_BRACKET_ORDER.length
}

function TeamLogo({ team, className }: {
  team: WcFixture['home_team']
  className: string
}) {
  const logo = TEAM_LOGO(team.external_id)
  const displayName = worldCupTeamName(team)
  if (!logo) return <span className={`${className} wm-team-fallback`}>{displayName.slice(0, 2)}</span>

  return (
    <img
      src={logo}
      alt=""
      className={className}
      loading="lazy"
      onError={(event) => {
        event.currentTarget.style.visibility = 'hidden'
      }}
    />
  )
}

function FixtureCard({ fixture, compact = false }: {
  fixture: WcFixture
  compact?: boolean
}) {
  const finished = FINISHED_STATUSES.has(fixture.status)
  const hasScore = fixture.home_goals != null && fixture.away_goals != null

  return (
    <Link
      to={`/mundial/partido/${fixture.external_id}`}
      className={[
        'wm-match',
        fixture.is_live ? 'wm-match--live' : '',
        finished ? 'wm-match--finished' : '',
        compact ? 'wm-match--compact' : '',
      ].filter(Boolean).join(' ')}
      aria-label={`Ver ${worldCupTeamName(fixture.home_team)} contra ${worldCupTeamName(fixture.away_team)}`}
    >
      <div className="wm-match__stage">{worldCupStageLabel(fixture.stage)}</div>

      <div className="wm-match__teams">
        <div className="wm-match__team">
          <TeamLogo team={fixture.home_team} className="wm-match__logo" />
          <span>{worldCupTeamName(fixture.home_team)}</span>
        </div>

        <div className="wm-match__score" aria-label={
          hasScore
            ? `${fixture.home_goals} a ${fixture.away_goals}`
            : `${formatDate(fixture.played_at)} a las ${formatTime(fixture.played_at)}`
        }>
          {fixture.is_live ? (
            <>
              <strong>{fixture.home_goals ?? 0} - {fixture.away_goals ?? 0}</strong>
              <small className="wm-match__live">
                <i aria-hidden="true" />
                {fixture.status === 'HT' ? 'Descanso' : `${fixture.elapsed ?? ''}' En vivo`}
              </small>
            </>
          ) : finished && hasScore ? (
            <>
              <strong>{fixture.home_goals} - {fixture.away_goals}</strong>
              <small>Final</small>
            </>
          ) : (
            <>
              <strong>{formatTime(fixture.played_at)}</strong>
              <small>{formatDate(fixture.played_at)}</small>
            </>
          )}
        </div>

        <div className="wm-match__team wm-match__team--away">
          <TeamLogo team={fixture.away_team} className="wm-match__logo" />
          <span>{worldCupTeamName(fixture.away_team)}</span>
        </div>
      </div>
    </Link>
  )
}

function bracketStageFixtures(fixtures: WcFixture[], stage: 'round32' | 'round16' | 'quarter' | 'semi' | 'final' | 'third', size: number) {
  const matches = fixtures
    .filter((fixture) => {
      const normalizedStage = fixture.stage.toLowerCase()
      if (stage === 'round32') return normalizedStage.includes('round of 32')
      if (stage === 'round16') return normalizedStage.includes('round of 16') || normalizedStage.includes('last 16')
      if (stage === 'quarter') return normalizedStage.includes('quarter')
      if (stage === 'semi') return normalizedStage.includes('semi')
      if (stage === 'third') return normalizedStage.includes('3rd') || normalizedStage.includes('third')
      return normalizedStage.includes('final') && !normalizedStage.includes('3rd') && !normalizedStage.includes('third') && !normalizedStage.includes('semi')
    })
    .sort((a, b) => {
      if (stage === 'round32') {
        const byBracket = round32OrderIndex(a) - round32OrderIndex(b)
        if (byBracket !== 0) return byBracket
      }
      return new Date(a.played_at).getTime() - new Date(b.played_at).getTime()
    })

  return Array.from({ length: size }, (_, index) => matches[index] ?? null)
}

function bracketWinnerSide(fixture: WcFixture | null): 'home' | 'away' | null {
  if (!fixture || !FINISHED_STATUSES.has(fixture.status)) return null
  if (fixture.home_winner === true) return 'home'
  if (fixture.away_winner === true) return 'away'
  if (fixture.home_goals == null || fixture.away_goals == null) return null
  if (fixture.home_goals > fixture.away_goals) return 'home'
  if (fixture.away_goals > fixture.home_goals) return 'away'
  return null
}

function bracketWinnerTeam(fixture: WcFixture | null): WcFixture['home_team'] | null {
  const winnerSide = bracketWinnerSide(fixture)
  if (winnerSide === 'home') return fixture?.home_team ?? null
  if (winnerSide === 'away') return fixture?.away_team ?? null
  return null
}

function BracketTeam({
  team,
  fallback,
  outcome,
}: {
  team: WcFixture['home_team'] | null
  fallback: string
  outcome?: 'winner' | 'loser' | null
}) {
  const className = [
    'wm-bracket-team',
    outcome === 'winner' ? 'wm-bracket-team--winner' : '',
    outcome === 'loser' ? 'wm-bracket-team--loser' : '',
  ].filter(Boolean).join(' ')

  if (!team) {
    return (
      <span className={className}>
        <span className="wm-bracket-team__crest" aria-hidden="true" />
        <strong>{fallback}</strong>
      </span>
    )
  }

  return (
    <span className={className}>
      <TeamLogo team={team} className="wm-bracket-team__logo" />
      <strong>{teamCode(team, fallback)}</strong>
    </span>
  )
}

function BracketNode({
  fixture,
  homeFallback = 'TBD',
  awayFallback = 'TBD',
  homeTeam,
  awayTeam,
  dateFallback,
  side,
  nodeId,
}: {
  fixture: WcFixture | null
  homeFallback?: string
  awayFallback?: string
  homeTeam?: WcFixture['home_team'] | null
  awayTeam?: WcFixture['away_team'] | null
  dateFallback: string
  side: 'left' | 'right' | 'center'
  nodeId?: string
}) {
  const date = fixture ? formatDate(fixture.played_at).replace('.', '') : dateFallback
  const winnerSide = bracketWinnerSide(fixture)
  const displayHomeTeam = homeTeam ?? fixture?.home_team ?? null
  const displayAwayTeam = awayTeam ?? fixture?.away_team ?? null
  const hasScore = fixture?.home_goals != null && fixture.away_goals != null
  const content = (
    <>
      <div className="wm-bracket-node__teams">
        <BracketTeam
          team={displayHomeTeam}
          fallback={homeFallback}
          outcome={winnerSide === 'home' ? 'winner' : winnerSide === 'away' ? 'loser' : null}
        />
        <BracketTeam
          team={displayAwayTeam}
          fallback={awayFallback}
          outcome={winnerSide === 'away' ? 'winner' : winnerSide === 'home' ? 'loser' : null}
        />
      </div>
      {hasScore && (
        <span className="wm-bracket-node__score">
          {fixture.home_goals} - {fixture.away_goals}
        </span>
      )}
      <span className="wm-bracket-node__date">{date}</span>
    </>
  )

  const className = [
    'wm-bracket-node',
    `wm-bracket-node--${side}`,
    fixture?.is_live ? 'wm-bracket-node--live' : '',
    winnerSide ? 'wm-bracket-node--decided' : '',
  ].filter(Boolean).join(' ')

  if (!fixture) {
    return <div className={className} data-bracket-node={nodeId}>{content}</div>
  }

  return (
    <Link to={`/mundial/partido/${fixture.external_id}`} className={className} data-bracket-node={nodeId}>
      {content}
    </Link>
  )
}

type BracketConnection = {
  from: string[]
  to: string
  side: 'left' | 'right' | 'down'
  tone?: 'default' | 'bronze'
}

function BracketLines({
  boardRef,
  connections,
  variant,
}: {
  boardRef: RefObject<HTMLElement>
  connections: BracketConnection[]
  variant: 'desktop' | 'mobile'
}) {
  const [paths, setPaths] = useState<Array<{ d: string; tone: BracketConnection['tone'] }>>([])
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const board = boardRef.current
    if (!board) return undefined

    const measure = () => {
      const boardRect = board.getBoundingClientRect()
      setSize({ width: boardRect.width, height: boardRect.height })
      const nodeRect = (id: string) => {
        const node = board.querySelector<HTMLElement>(`[data-bracket-node="${id}"]`)
        if (!node) return null
        const rect = node.getBoundingClientRect()
        return {
          left: rect.left - boardRect.left,
          right: rect.right - boardRect.left,
          top: rect.top - boardRect.top,
          bottom: rect.bottom - boardRect.top,
          cx: rect.left - boardRect.left + rect.width / 2,
          cy: rect.top - boardRect.top + rect.height / 2,
        }
      }

      const nextPaths = connections.flatMap((connection) => {
        const target = nodeRect(connection.to)
        const sources = connection.from.map(nodeRect).filter(Boolean)
        if (!target || sources.length === 0) return []

        if (connection.side === 'down') {
          const targetY = target.top
          const sourceY = Math.max(...sources.map((source) => source!.bottom))
          const railY = sourceY + (targetY - sourceY) / 2
          const xValues = sources.map((source) => source!.cx)

          if (sources.length === 1) {
            const source = sources[0]!
            const d = `M ${source.cx} ${source.bottom} V ${railY} H ${target.cx} V ${targetY}`
            return [{ d, tone: connection.tone }]
          }

          const minX = Math.min(...xValues)
          const maxX = Math.max(...xValues)
          const sourceSegments = sources.map((source) => `M ${source!.cx} ${source!.bottom} V ${railY}`).join(' ')
          const d = `${sourceSegments} M ${minX} ${railY} H ${maxX} M ${target.cx} ${railY} V ${targetY}`
          return [{ d, tone: connection.tone }]
        }

        const targetX = connection.side === 'left' ? target.left : target.right
        const sourceX = connection.side === 'left'
          ? Math.max(...sources.map((source) => source!.right))
          : Math.min(...sources.map((source) => source!.left))
        const railX = sourceX + (targetX - sourceX) / 2
        const yValues = sources.map((source) => source!.cy)

        if (sources.length === 1) {
          const source = sources[0]!
          const startX = connection.side === 'left' ? source.right : source.left
          const d = `M ${startX} ${source.cy} H ${railX} V ${target.cy} H ${targetX}`
          return [{ d, tone: connection.tone }]
        }

        const minY = Math.min(...yValues)
        const maxY = Math.max(...yValues)
        const sourceSegments = sources.map((source) => {
          const startX = connection.side === 'left' ? source!.right : source!.left
          return `M ${startX} ${source!.cy} H ${railX}`
        }).join(' ')
        const d = `${sourceSegments} M ${railX} ${minY} V ${maxY} M ${railX} ${target.cy} H ${targetX}`
        return [{ d, tone: connection.tone }]
      })

      setPaths(nextPaths)
    }

    measure()
    const resizeObserver = new ResizeObserver(measure)
    resizeObserver.observe(board)
    board.querySelectorAll('[data-bracket-node]').forEach((node) => resizeObserver.observe(node))
    window.addEventListener('resize', measure)

    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [boardRef, connections])

  return (
    <svg
      className={`wm-bracket-lines wm-bracket-lines--${variant}`}
      viewBox={`0 0 ${Math.max(size.width, 1)} ${Math.max(size.height, 1)}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {paths.map((path, index) => (
        <path
          key={`${path.d}-${index}`}
          className={path.tone === 'bronze' ? 'wm-bracket-lines__bronze' : undefined}
          d={path.d}
        />
      ))}
    </svg>
  )
}

function WorldCupBracketDesktop({ fixtures }: { fixtures: WcFixture[] }) {
  const boardRef = useRef<HTMLDivElement>(null)
  const round32 = bracketStageFixtures(fixtures, 'round32', 16)
  const round16 = bracketStageFixtures(fixtures, 'round16', 8)
  const quarters = bracketStageFixtures(fixtures, 'quarter', 4)
  const semis = bracketStageFixtures(fixtures, 'semi', 2)
  const final = bracketStageFixtures(fixtures, 'final', 1)[0]
  const thirdPlace = bracketStageFixtures(fixtures, 'third', 1)[0]
  const round16Teams = Array.from({ length: 8 }, (_, index) => ({
    home: bracketWinnerTeam(round32[index * 2]),
    away: bracketWinnerTeam(round32[index * 2 + 1]),
  }))
  const quarterTeams = Array.from({ length: 4 }, (_, index) => ({
    home: bracketWinnerTeam(round16[index * 2]),
    away: bracketWinnerTeam(round16[index * 2 + 1]),
  }))
  const semiTeams = Array.from({ length: 2 }, (_, index) => ({
    home: bracketWinnerTeam(quarters[index * 2]),
    away: bracketWinnerTeam(quarters[index * 2 + 1]),
  }))
  const finalTeams = {
    home: bracketWinnerTeam(semis[0]),
    away: bracketWinnerTeam(semis[1]),
  }
  const connections = useMemo<BracketConnection[]>(() => [
    { from: ['l32-0', 'l32-1'], to: 'l16-0', side: 'left' },
    { from: ['l32-2', 'l32-3'], to: 'l16-1', side: 'left' },
    { from: ['l32-4', 'l32-5'], to: 'l16-2', side: 'left' },
    { from: ['l32-6', 'l32-7'], to: 'l16-3', side: 'left' },
    { from: ['l16-0', 'l16-1'], to: 'lq-0', side: 'left' },
    { from: ['l16-2', 'l16-3'], to: 'lq-1', side: 'left' },
    { from: ['lq-0', 'lq-1'], to: 'ls-0', side: 'left' },
    { from: ['ls-0'], to: 'final', side: 'left' },
    { from: ['ls-0'], to: 'bronze', side: 'left', tone: 'bronze' },
    { from: ['r32-0', 'r32-1'], to: 'r16-0', side: 'right' },
    { from: ['r32-2', 'r32-3'], to: 'r16-1', side: 'right' },
    { from: ['r32-4', 'r32-5'], to: 'r16-2', side: 'right' },
    { from: ['r32-6', 'r32-7'], to: 'r16-3', side: 'right' },
    { from: ['r16-0', 'r16-1'], to: 'rq-0', side: 'right' },
    { from: ['r16-2', 'r16-3'], to: 'rq-1', side: 'right' },
    { from: ['rq-0', 'rq-1'], to: 'rs-0', side: 'right' },
    { from: ['rs-0'], to: 'final', side: 'right' },
    { from: ['rs-0'], to: 'bronze', side: 'right', tone: 'bronze' },
  ], [])

  return (
    <section className="wm-bracket-desktop" aria-label="Cuadro final del Mundial">
      <header className="wm-bracket-desktop__header">
        <span>Fase eliminatoria</span>
        <h2>Camino al campeon</h2>
      </header>

      <div className="wm-bracket-board" ref={boardRef}>
        <BracketLines boardRef={boardRef} connections={connections} variant="desktop" />
        <div className="wm-bracket-column wm-bracket-column--edge wm-bracket-column--left">
          {round32.slice(0, 8).map((fixture, index) => (
            <BracketNode fixture={fixture} dateFallback="Por definir" side="left" nodeId={`l32-${index}`} key={`l32-${index}`} />
          ))}
        </div>
        <div className="wm-bracket-column wm-bracket-column--mid wm-bracket-column--left">
          {round16.slice(0, 4).map((fixture, index) => (
            <BracketNode
              fixture={fixture}
              homeTeam={round16Teams[index].home}
              awayTeam={round16Teams[index].away}
              dateFallback="Por definir"
              side="left"
              nodeId={`l16-${index}`}
              key={`l16-${index}`}
            />
          ))}
        </div>
        <div className="wm-bracket-column wm-bracket-column--late wm-bracket-column--left">
          {quarters.slice(0, 2).map((fixture, index) => (
            <BracketNode
              fixture={fixture}
              homeTeam={quarterTeams[index].home}
              awayTeam={quarterTeams[index].away}
              homeFallback={`EF${index * 2 + 1}`}
              awayFallback={`EF${index * 2 + 2}`}
              dateFallback="Por definir"
              side="left"
              nodeId={`lq-${index}`}
              key={`lq-${index}`}
            />
          ))}
        </div>
        <div className="wm-bracket-column wm-bracket-column--semi wm-bracket-column--left">
          <BracketNode
            fixture={semis[0]}
            homeTeam={semiTeams[0].home}
            awayTeam={semiTeams[0].away}
            homeFallback="WQ1"
            awayFallback="WQ2"
            dateFallback="Por definir"
            side="left"
            nodeId="ls-0"
          />
        </div>

        <div className="wm-bracket-center">
          <div className="wm-bracket-trophy" aria-hidden="true">
            <svg viewBox="0 0 64 64" role="img">
              <path d="M19 8h26v11c0 10-5 17-13 19-8-2-13-9-13-19V8Z" fill="none" stroke="currentColor" strokeWidth="4" />
              <path d="M20 14H9v5c0 7 5 12 12 12M44 14h11v5c0 7-5 12-12 12" fill="none" stroke="currentColor" strokeWidth="4" />
              <path d="M32 38v10M22 56h20M26 48h12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </div>
          <span className="wm-bracket-center__label">Campeon</span>
          <BracketNode
            fixture={final}
            homeTeam={finalTeams.home}
            awayTeam={finalTeams.away}
            homeFallback="WS1"
            awayFallback="WS2"
            dateFallback="Final"
            side="center"
            nodeId="final"
          />
          <BracketNode fixture={thirdPlace} homeFallback="LS1" awayFallback="LS2" dateFallback="Bronce" side="center" nodeId="bronze" />
        </div>

        <div className="wm-bracket-column wm-bracket-column--semi wm-bracket-column--right">
          <BracketNode
            fixture={semis[1]}
            homeTeam={semiTeams[1].home}
            awayTeam={semiTeams[1].away}
            homeFallback="WQ3"
            awayFallback="WQ4"
            dateFallback="Por definir"
            side="right"
            nodeId="rs-0"
          />
        </div>
        <div className="wm-bracket-column wm-bracket-column--late wm-bracket-column--right">
          {quarters.slice(2, 4).map((fixture, index) => (
            <BracketNode
              fixture={fixture}
              homeTeam={quarterTeams[index + 2].home}
              awayTeam={quarterTeams[index + 2].away}
              homeFallback={`EF${index * 2 + 5}`}
              awayFallback={`EF${index * 2 + 6}`}
              dateFallback="Por definir"
              side="right"
              nodeId={`rq-${index}`}
              key={`rq-${index}`}
            />
          ))}
        </div>
        <div className="wm-bracket-column wm-bracket-column--mid wm-bracket-column--right">
          {round16.slice(4, 8).map((fixture, index) => (
            <BracketNode
              fixture={fixture}
              homeTeam={round16Teams[index + 4].home}
              awayTeam={round16Teams[index + 4].away}
              dateFallback="Por definir"
              side="right"
              nodeId={`r16-${index}`}
              key={`r16-${index}`}
            />
          ))}
        </div>
        <div className="wm-bracket-column wm-bracket-column--edge wm-bracket-column--right">
          {round32.slice(8, 16).map((fixture, index) => (
            <BracketNode fixture={fixture} dateFallback="Por definir" side="right" nodeId={`r32-${index}`} key={`r32-${index}`} />
          ))}
        </div>
      </div>
    </section>
  )
}

function WorldCupBracketMobile({ fixtures }: { fixtures: WcFixture[] }) {
  const boardRef = useRef<HTMLElement>(null)
  const round32 = bracketStageFixtures(fixtures, 'round32', 16)
  const round16 = bracketStageFixtures(fixtures, 'round16', 8)
  const quarters = bracketStageFixtures(fixtures, 'quarter', 4)
  const semis = bracketStageFixtures(fixtures, 'semi', 2)
  const final = bracketStageFixtures(fixtures, 'final', 1)[0]
  const thirdPlace = bracketStageFixtures(fixtures, 'third', 1)[0]
  const round16Teams = Array.from({ length: 8 }, (_, index) => ({
    home: bracketWinnerTeam(round32[index * 2]),
    away: bracketWinnerTeam(round32[index * 2 + 1]),
  }))
  const quarterTeams = Array.from({ length: 4 }, (_, index) => ({
    home: bracketWinnerTeam(round16[index * 2]),
    away: bracketWinnerTeam(round16[index * 2 + 1]),
  }))
  const semiTeams = Array.from({ length: 2 }, (_, index) => ({
    home: bracketWinnerTeam(quarters[index * 2]),
    away: bracketWinnerTeam(quarters[index * 2 + 1]),
  }))
  const finalTeams = {
    home: bracketWinnerTeam(semis[0]),
    away: bracketWinnerTeam(semis[1]),
  }
  const connections = useMemo<BracketConnection[]>(() => [
    { from: ['m32-0', 'm32-1'], to: 'm16-0', side: 'down' },
    { from: ['m32-2', 'm32-3'], to: 'm16-1', side: 'down' },
    { from: ['m32-4', 'm32-5'], to: 'm16-2', side: 'down' },
    { from: ['m32-6', 'm32-7'], to: 'm16-3', side: 'down' },
    { from: ['m16-0', 'm16-1'], to: 'mq-0', side: 'down' },
    { from: ['m16-2', 'm16-3'], to: 'mq-2', side: 'down' },
    { from: ['mq-0', 'mq-2'], to: 'ms-0', side: 'down' },
    { from: ['ms-0'], to: 'mfinal', side: 'down' },
    { from: ['mfinal'], to: 'ms-1', side: 'down' },
    { from: ['ms-1'], to: 'mq-1', side: 'down' },
    { from: ['ms-1'], to: 'mq-3', side: 'down' },
    { from: ['mq-1'], to: 'm16-4', side: 'down' },
    { from: ['mq-1'], to: 'm16-5', side: 'down' },
    { from: ['mq-3'], to: 'm16-6', side: 'down' },
    { from: ['mq-3'], to: 'm16-7', side: 'down' },
    { from: ['m16-4'], to: 'm32-8', side: 'down' },
    { from: ['m16-4'], to: 'm32-9', side: 'down' },
    { from: ['m16-5'], to: 'm32-10', side: 'down' },
    { from: ['m16-5'], to: 'm32-11', side: 'down' },
    { from: ['m16-6'], to: 'm32-12', side: 'down' },
    { from: ['m16-6'], to: 'm32-13', side: 'down' },
    { from: ['m16-7'], to: 'm32-14', side: 'down' },
    { from: ['m16-7'], to: 'm32-15', side: 'down' },
  ], [])

  return (
    <section className="wm-bracket-mobile" aria-label="Cuadro final del Mundial" ref={boardRef}>
      <BracketLines boardRef={boardRef} connections={connections} variant="mobile" />

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four wm-bracket-mobile__row--seed">
        {round32.slice(0, 4).map((fixture, index) => (
          <BracketNode fixture={fixture} dateFallback="Por definir" side="center" nodeId={`m32-${index}`} key={`m32-a-${index}`} />
        ))}
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four wm-bracket-mobile__row--seed">
        {round32.slice(4, 8).map((fixture, index) => (
          <BracketNode fixture={fixture} dateFallback="Por definir" side="center" nodeId={`m32-${index + 4}`} key={`m32-b-${index}`} />
        ))}
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four">
        {round16.slice(0, 4).map((fixture, index) => (
          <BracketNode
            fixture={fixture}
            homeTeam={round16Teams[index].home}
            awayTeam={round16Teams[index].away}
            dateFallback="Por definir"
            side="center"
            nodeId={`m16-${index}`}
            key={`m16-top-${index}`}
          />
        ))}
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--two">
        <BracketNode
          fixture={quarters[0]}
          homeTeam={quarterTeams[0].home}
          awayTeam={quarterTeams[0].away}
          homeFallback="EF1"
          awayFallback="EF2"
          dateFallback="Por definir"
          side="center"
          nodeId="mq-0"
        />
        <BracketNode
          fixture={quarters[2]}
          homeTeam={quarterTeams[2].home}
          awayTeam={quarterTeams[2].away}
          homeFallback="EF5"
          awayFallback="EF6"
          dateFallback="Por definir"
          side="center"
          nodeId="mq-2"
        />
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--one">
        <BracketNode
          fixture={semis[0]}
          homeTeam={semiTeams[0].home}
          awayTeam={semiTeams[0].away}
          homeFallback="WQ1"
          awayFallback="WQ2"
          dateFallback="Por definir"
          side="center"
          nodeId="ms-0"
        />
      </div>

      <div className="wm-bracket-mobile__final-zone">
        <div className="wm-bracket-mobile__bronze">
          <BracketNode fixture={thirdPlace} homeFallback="LS1" awayFallback="LS2" dateFallback="Bronce" side="center" />
          <span className="wm-bracket-mobile__bronze-label">Final de bronce</span>
        </div>
        <div className="wm-bracket-mobile__winner">
          <div className="wm-bracket-trophy" aria-hidden="true">
            <svg viewBox="0 0 64 64" role="img">
              <path d="M19 8h26v11c0 10-5 17-13 19-8-2-13-9-13-19V8Z" fill="none" stroke="currentColor" strokeWidth="4" />
              <path d="M20 14H9v5c0 7 5 12 12 12M44 14h11v5c0 7-5 12-12 12" fill="none" stroke="currentColor" strokeWidth="4" />
              <path d="M32 38v10M22 56h20M26 48h12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </div>
          <span className="wm-bracket-center__label">Campeon</span>
        </div>
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--one">
        <BracketNode
          fixture={final}
          homeTeam={finalTeams.home}
          awayTeam={finalTeams.away}
          homeFallback="WS1"
          awayFallback="WS2"
          dateFallback="Final"
          side="center"
          nodeId="mfinal"
        />
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--one">
        <BracketNode
          fixture={semis[1]}
          homeTeam={semiTeams[1].home}
          awayTeam={semiTeams[1].away}
          homeFallback="WQ3"
          awayFallback="WQ4"
          dateFallback="Por definir"
          side="center"
          nodeId="ms-1"
        />
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--two">
        <BracketNode
          fixture={quarters[1]}
          homeTeam={quarterTeams[1].home}
          awayTeam={quarterTeams[1].away}
          homeFallback="EF3"
          awayFallback="EF4"
          dateFallback="Por definir"
          side="center"
          nodeId="mq-1"
        />
        <BracketNode
          fixture={quarters[3]}
          homeTeam={quarterTeams[3].home}
          awayTeam={quarterTeams[3].away}
          homeFallback="EF7"
          awayFallback="EF8"
          dateFallback="Por definir"
          side="center"
          nodeId="mq-3"
        />
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four">
        {round16.slice(4, 8).map((fixture, index) => (
          <BracketNode
            fixture={fixture}
            homeTeam={round16Teams[index + 4].home}
            awayTeam={round16Teams[index + 4].away}
            dateFallback="Por definir"
            side="center"
            nodeId={`m16-${index + 4}`}
            key={`m16-bottom-${index}`}
          />
        ))}
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four wm-bracket-mobile__row--seed">
        {round32.slice(8, 12).map((fixture, index) => (
          <BracketNode fixture={fixture} dateFallback="Por definir" side="center" nodeId={`m32-${index + 8}`} key={`m32-c-${index}`} />
        ))}
      </div>

      <div className="wm-bracket-mobile__row wm-bracket-mobile__row--four wm-bracket-mobile__row--seed">
        {round32.slice(12, 16).map((fixture, index) => (
          <BracketNode fixture={fixture} dateFallback="Por definir" side="center" nodeId={`m32-${index + 12}`} key={`m32-d-${index}`} />
        ))}
      </div>
    </section>
  )
}

function DateRail({
  label,
  dates,
  value,
  onChange,
}: {
  label: string
  dates: Array<{ key: string; label: string }>
  value: string
  onChange: (key: string) => void
}) {
  if (dates.length === 0) return null

  return (
    <div className="wm-date-rail" aria-label={label}>
      {dates.map((date) => (
        <button
          type="button"
          key={date.key}
          className={`wm-date-rail__button${date.key === value ? ' wm-date-rail__button--active' : ''}`}
          onClick={() => onChange(date.key)}
          aria-pressed={date.key === value}
        >
          {date.label}
        </button>
      ))}
    </div>
  )
}

function ScorePill({ fixture, tone }: { fixture: WcFixture; tone: MatchTone }) {
  const finished = FINISHED_STATUSES.has(fixture.status)
  const hasScore = fixture.home_goals != null && fixture.away_goals != null
  const homeName = worldCupTeamName(fixture.home_team)
  const awayName = worldCupTeamName(fixture.away_team)
  const statusLabel = tone === 'live'
    ? fixture.status === 'HT' ? 'Descanso' : `${fixture.elapsed ?? ''}'`
    : finished
      ? 'Final'
      : formatTime(fixture.played_at)

  return (
    <Link
      to={`/mundial/partido/${fixture.external_id}`}
      className={`wm-score-pill wm-score-pill--${tone}`}
      aria-label={`Ver ${homeName} contra ${awayName}`}
    >
      <span className="wm-score-pill__stage">
        {worldCupStageLabel(fixture.stage)}
      </span>
      <span className="wm-score-pill__line">
        <span className="wm-score-pill__team">
          <TeamLogo team={fixture.home_team} className="wm-score-pill__flag" />
          <strong>{homeName}</strong>
        </span>
        <span className="wm-score-pill__score">
          {hasScore ? `${fixture.home_goals} - ${fixture.away_goals}` : 'vs'}
        </span>
        <span className="wm-score-pill__team wm-score-pill__team--away">
          <TeamLogo team={fixture.away_team} className="wm-score-pill__flag" />
          <strong>{awayName}</strong>
        </span>
      </span>
      <span className="wm-score-pill__meta">
        <i aria-hidden="true" />
        {statusLabel}
      </span>
    </Link>
  )
}

function SpotlightMatch({ fixture }: { fixture: WcFixture }) {
  const tone: MatchTone = fixture.is_live
    ? 'live'
    : FINISHED_STATUSES.has(fixture.status)
      ? 'result'
      : 'upcoming'
  const title = tone === 'live' ? 'Partido en vivo' : tone === 'result' ? 'Último resultado' : 'Próximo partido'

  return (
    <section className={`wm-now-strip wm-now-strip--${tone}`} aria-label={title}>
      <div className="wm-now-strip__label">
        <i aria-hidden="true" />
        <span>{title}</span>
      </div>
      <ScorePill fixture={fixture} tone={tone} />
    </section>
  )
}

function StandingsGroup({ group, rows }: { group: string; rows: WcStanding[] }) {
  return (
    <section className="wm-group">
      <header className="wm-group__header">
        <span>{group.replace('Group', 'Grupo')}</span>
        <small>Pts</small>
      </header>
      <div className="wm-group__labels" aria-hidden="true">
        <span>Pos. Selección</span>
        <span>PJ</span>
        <span>DG</span>
        <span>Pts</span>
      </div>
      {rows.map((row) => (
        <Link
          to={row.team.external_id != null ? `/mundial/seleccion/${row.team.external_id}` : '#'}
          className="wm-standing-row wm-standing-row--link"
          key={row.team.external_id}
        >
          <span className="wm-standing-row__position">{row.position}</span>
          <TeamLogo team={row.team} className="wm-standing-row__logo" />
          <strong>{worldCupTeamName(row.team)}</strong>
          <span>{row.played}</span>
          <span>{row.goal_difference > 0 ? '+' : ''}{row.goal_difference}</span>
          <b>{row.points}</b>
        </Link>
      ))}
    </section>
  )
}

function TeamSFARankingView({ teams }: { teams: WcTeamSFARankingItem[] }) {
  if (teams.length === 0) {
    return <div className="wm-teams-empty">No hay datos de selecciones disponibles todavía.</div>
  }
  return (
    <div className="wm-teams-ranking">
      <div className="wm-teams-ranking__header" aria-hidden="true">
        <span>Pos.</span>
        <span>Selección</span>
        <span>Goles</span>
        <span>Jugadores</span>
        <span>Pts SFA</span>
      </div>
      {teams.map((team) => {
        const fakeTeam = { name: team.team_name, external_id: team.team_external_id }
        const displayName = worldCupTeamName(fakeTeam as WcFixture['home_team'])
        const logo = `https://media.api-sports.io/football/teams/${team.team_external_id}.png`
        return (
          <Link
            key={team.team_external_id}
            to={`/mundial/seleccion/${team.team_external_id}`}
            className={`wm-teams-ranking__row${team.rank <= 3 ? ` wm-teams-ranking__row--top${team.rank}` : ''}`}
          >
            <span className="wm-teams-ranking__rank">{team.rank}</span>
            <span className="wm-teams-ranking__team">
              <img
                src={logo}
                alt=""
                className="wm-teams-ranking__logo"
                loading="lazy"
                onError={(e) => { e.currentTarget.style.visibility = 'hidden' }}
              />
              <span>{displayName}</span>
            </span>
            <span className="wm-teams-ranking__goals">{team.total_goals}</span>
            <span className="wm-teams-ranking__players">{team.player_count}</span>
            <span className="wm-teams-ranking__pts">
              {team.total_sfa_pts.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
              <small>pts</small>
            </span>
          </Link>
        )
      })}
    </div>
  )
}

export default function MundialPage() {
  const navigate = useNavigate()
  const [fixturesData, setFixturesData] = useState<WcFixturesResponse | null>(null)
  const [standingsData, setStandingsData] = useState<WcStandingsResponse | null>(null)
  const [teamsRanking, setTeamsRanking] = useState<WcTeamSFARankingItem[]>([])
  const [view, setView] = useState<MundialView>('matches')
  const [resultDate, setResultDate] = useState<string | null>(null)
  const [upcomingDate, setUpcomingDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.body.classList.add('mode-tournament')
    return () => document.body.classList.remove('mode-tournament')
  }, [])

  useEffect(() => {
    Promise.all([fetchWcFixtures(), fetchWcStandings()])
      .then(([fixtures, standings]) => {
        setFixturesData(fixtures)
        setStandingsData(standings)
      })
      .catch((requestError) => setError(requestError.message ?? 'Error al cargar el Mundial'))
      .finally(() => setLoading(false))

    fetchWcTeamSFARanking()
      .then((teamsData) => setTeamsRanking(teamsData.rankings))
      .catch(() => setTeamsRanking([]))
  }, [])

  useEffect(() => {
    function refreshLive() {
      fetchWcFixtures(true)
        .then(setFixturesData)
        .catch(() => {})
    }

    const timer = setInterval(refreshLive, 120_000)
    return () => clearInterval(timer)
  }, [])

  const fixtures = fixturesData?.fixtures ?? []
  const live = fixtures.filter((fixture) => fixture.is_live)
  const allResults = fixtures
    .filter((fixture) => FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(b.played_at).getTime() - new Date(a.played_at).getTime())
  const allUpcoming = fixtures
    .filter((fixture) => !fixture.is_live && !FINISHED_STATUSES.has(fixture.status))
    .sort((a, b) => new Date(a.played_at).getTime() - new Date(b.played_at).getTime())
  const resultDates = uniqueDateOptions(allResults, 'desc')
  const upcomingDates = uniqueDateOptions(allUpcoming, 'asc')
  const selectedResultDate = resultDate ?? resultDates[0]?.key ?? ''
  const selectedUpcomingDate = upcomingDate ?? upcomingDates[0]?.key ?? ''
  const results = allResults
    .filter((fixture) => dateKey(fixture.played_at) === selectedResultDate)
    .slice(0, 10)
  const upcoming = allUpcoming
    .filter((fixture) => dateKey(fixture.played_at) === selectedUpcomingDate)
    .slice(0, 10)
  const spotlightFixture = live[0] ?? allUpcoming[0] ?? allResults[0] ?? null
  const knockoutFixtures = fixtures.filter(isKnockout)

  const standingsByGroup = useMemo(() => {
    const groups = new Map<string, WcStanding[]>()
    for (const standing of standingsData?.standings ?? []) {
      const group = groups.get(standing.group) ?? []
      group.push(standing)
      groups.set(standing.group, group)
    }
    for (const rows of groups.values()) rows.sort((a, b) => a.position - b.position)
    return groups
  }, [standingsData])

  function goBack() {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1)
      return
    }
    navigate('/ranking?season=2026')
  }

  return (
    <div className="mundial-page">
      <header className="wm-hero">
        <div className="wm-hero__pattern" aria-hidden="true" />
        <div className="wm-hero__content">
          <div>
            <button type="button" className="wm-hero__back" onClick={goBack}>
              <span aria-hidden="true">←</span>
              Volver
            </button>
            <span className="wm-hero__eyebrow">Stats Football Award · Edición Mundial</span>
            <h1><span>Mundial</span> <strong>2026</strong></h1>
            <p className="wm-hero__description">
              Sigue los partidos, la clasificación y el camino hacia la final.
              SFA mide qué jugadores generan mayor impacto real durante el torneo.
            </p>
            <div className="wm-hero__actions">
              <Link to="/ranking" className="wm-hero__ranking-link">
                Ver ranking de jugadores
                <span aria-hidden="true">→</span>
              </Link>
              <span>Ranking independiente · Todos comienzan en cero</span>
            </div>
          </div>
        </div>
      </header>

      <nav className="wm-tabs" aria-label="Secciones del Mundial">
        {([
          ['matches', 'Partidos'],
          ['standings', 'Grupos'],
          ['bracket', 'Cruces'],
          ['teams', 'Selecciones'],
        ] as const).map(([id, label]) => (
          <button
            type="button"
            key={id}
            className={`wm-tab${view === id ? ' wm-tab--active' : ''}`}
            onClick={() => setView(id)}
            aria-pressed={view === id}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="wm-dashboard">
        {loading && (
          <div className="wm-dashboard__loading">
            {Array.from({ length: 6 }).map((_, index) => (
              <div className="skeleton wm-match-skeleton" key={index} />
            ))}
          </div>
        )}

        {!loading && error && <div className="empty-state">{error}</div>}

        {!loading && !error && view === 'matches' && (
          <>
            {live.length > 1 ? (
              <div className="wm-multi-live">
                {live.map((fixture) => (
                  <SpotlightMatch fixture={fixture} key={fixture.id} />
                ))}
              </div>
            ) : spotlightFixture ? (
              <SpotlightMatch fixture={spotlightFixture} />
            ) : null}

            <div className="wm-scoreboard-layout">
              <section className="wm-section wm-scoreboard-panel">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Marcadores</span>
                    <h2>Resultados</h2>
                  </div>
                </header>
                <DateRail
                  label="Elegir fecha de resultados"
                  dates={resultDates}
                  value={selectedResultDate}
                  onChange={setResultDate}
                />
                {results.length > 0 ? (
                  <div className="wm-score-stack">
                    {results.map((fixture) => (
                      <ScorePill fixture={fixture} tone="result" key={fixture.id} />
                    ))}
                  </div>
                ) : (
                  <div className="wm-score-empty">No hay resultados para esta fecha.</div>
                )}
              </section>

              <section className="wm-section wm-scoreboard-panel">
                <header className="wm-section__header">
                  <div>
                    <span className="wm-section__eyebrow">Calendario</span>
                    <h2>Próximos partidos</h2>
                  </div>
                </header>
                <DateRail
                  label="Elegir fecha de próximos partidos"
                  dates={upcomingDates}
                  value={selectedUpcomingDate}
                  onChange={setUpcomingDate}
                />
                {upcoming.length > 0 ? (
                  <div className="wm-score-stack">
                    {upcoming.map((fixture) => (
                      <ScorePill fixture={fixture} tone="upcoming" key={fixture.id} />
                    ))}
                  </div>
                ) : (
                  <div className="wm-score-empty">No hay partidos programados para esta fecha.</div>
                )}
              </section>
            </div>
          </>
        )}

        {!loading && !error && view === 'standings' && (
          <div className="wm-groups">
            {Array.from(standingsByGroup.entries()).map(([group, rows]) => (
              <StandingsGroup group={group} rows={rows} key={group} />
            ))}
          </div>
        )}

        {!loading && !error && view === 'teams' && (
          <section className="wm-section">
            <header className="wm-section__header">
              <div>
                <span className="wm-section__eyebrow">Stats Football Award</span>
                <h2>Ranking por selección</h2>
              </div>
            </header>
            <TeamSFARankingView teams={teamsRanking} />
          </section>
        )}

        {!loading && !error && view === 'bracket' && (
          knockoutFixtures.length > 0 ? (
            <div className="wm-bracket-view">
              <WorldCupBracketDesktop fixtures={knockoutFixtures} />
              <WorldCupBracketMobile fixtures={knockoutFixtures} />
              <div className="wm-bracket wm-bracket-list">
                {knockoutFixtures.map((fixture) => (
                  <FixtureCard fixture={fixture} key={fixture.id} />
                ))}
              </div>
            </div>
          ) : (
            <div className="wm-bracket-empty">
              <span>Fase eliminatoria</span>
              <h2>Los cruces todavía no están definidos</h2>
              <p>
                El cuadro aparecerá aquí cuando se publiquen los clasificados y los
                partidos de dieciseisavos.
              </p>
            </div>
          )
        )}
      </main>
    </div>
  )
}
