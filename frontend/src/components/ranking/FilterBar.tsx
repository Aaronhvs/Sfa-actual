import type { Competition } from '../../types'

const POSITIONS: { value: string; label: string }[] = [
  { value: 'DEL', label: 'Delantero' },
  { value: 'EXT', label: 'Extremo' },
  { value: 'MCO', label: 'MC Ofensivo' },
  { value: 'MC', label: 'Mediocampista' },
  { value: 'DC', label: 'Def. Central' },
  { value: 'LAT', label: 'Lateral' },
]

interface Props {
  position: string
  onPosition: (position: string) => void
  competition: number | undefined
  onCompetition: (id: number | undefined) => void
  competitions: Competition[]
  search: string
  onSearch: (search: string) => void
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
    <div className="filter-bar" aria-label="Filtros del ranking">
      <label className="filter-select">
        <span className="filter-select__label">Posición</span>
        <select
          value={position}
          onChange={(event) => onPosition(event.target.value)}
          aria-label="Filtrar por posición"
        >
          <option value="">Todas las posiciones</option>
          {POSITIONS.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </label>

      <label className="filter-select">
        <span className="filter-select__label">Competición</span>
        <select
          value={competition ?? ''}
          onChange={(event) => {
            onCompetition(event.target.value ? Number(event.target.value) : undefined)
          }}
          aria-label="Filtrar por competición"
        >
          <option value="">Todas las competiciones</option>
          {competitions.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </label>

      <label className="filter-bar__search">
        <span className="sr-only">Buscar jugador o equipo</span>
        <input
          type="search"
          placeholder="Buscar jugador o equipo..."
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          className="filter-search-input"
        />
        {search && (
          <button
            type="button"
            className="filter-search-clear"
            onClick={() => onSearch('')}
            aria-label="Limpiar búsqueda"
          >
            ×
          </button>
        )}
      </label>
    </div>
  )
}
