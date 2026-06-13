import type { Competition } from '../../types'

const POSITIONS: { value: string; label: string }[] = [
  { value: 'DEL', label: 'Delantero' },
  { value: 'EXT', label: 'Extremo' },
  { value: 'MCO', label: 'MC Ofensivo' },
  { value: 'MC',  label: 'Mediocampista' },
  { value: 'DC',  label: 'Def. Central' },
  { value: 'LAT', label: 'Lateral' },
]

const COMP_LOGO_URL: Record<number, string> = {
  10: 'https://media.api-sports.io/football/leagues/2.png',
  1: 'https://media.api-sports.io/football/leagues/140.png',
  3: 'https://media.api-sports.io/football/leagues/39.png',
  6: 'https://media.api-sports.io/football/leagues/78.png',
  7: 'https://media.api-sports.io/football/leagues/135.png',
  9: 'https://media.api-sports.io/football/leagues/61.png',
}

interface Props {
  position: string
  onPosition: (p: string) => void
  competition: number | undefined
  onCompetition: (id: number | undefined) => void
  competitions: Competition[]
  search: string
  onSearch: (s: string) => void
}

export default function FilterBar({
  position,
  onPosition,
  competition,
  onCompetition,
  competitions,
  search,
  onSearch,
}: Props) {
  return (
    <div className="filter-bar">
      <div className="filter-bar__group">
        <button
          className={`filter-btn${position === '' ? ' filter-btn--active' : ''}`}
          onClick={() => onPosition('')}
        >
          Todos
        </button>
        {POSITIONS.map((p) => (
          <button
            key={p.value}
            className={`filter-btn${position === p.value ? ' filter-btn--active' : ''}`}
            onClick={() => onPosition(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="filter-bar__group filter-bar__group--comp">
        <button
          className={`filter-btn filter-btn--comp${competition == null ? ' filter-btn--active' : ''}`}
          onClick={() => onCompetition(undefined)}
        >
          Global
        </button>
        {competitions.map((c) => {
          const logoUrl = COMP_LOGO_URL[c.id]
          return (
            <button
              key={c.id}
              className={`filter-btn filter-btn--comp filter-btn--logo${competition === c.id ? ' filter-btn--active' : ''}`}
              onClick={() => onCompetition(c.id)}
              title={c.name}
            >
              {logoUrl && (
                <img
                  src={logoUrl}
                  alt=""
                  className="filter-btn__logo"
                  onError={(e) => { e.currentTarget.style.display = 'none' }}
                />
              )}
              <span className="filter-btn__label">{c.name}</span>
            </button>
          )
        })}
      </div>

      <div className="filter-bar__search">
        <input
          type="text"
          placeholder="Buscar jugador o equipo..."
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="filter-search-input"
        />
        {search && (
          <button className="filter-search-clear" onClick={() => onSearch('')}>
            ×
          </button>
        )}
      </div>
    </div>
  )
}
