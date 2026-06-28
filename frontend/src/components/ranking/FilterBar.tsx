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
  bonusFilter: string
  onBonusFilter: (bonus: string) => void
  competition: number | undefined
  onCompetition: (id: number | undefined) => void
  competitions: Competition[]
  search: string
  onSearch: (search: string) => void
}

export default function FilterBar({
  position,
  onPosition,
  bonusFilter,
  onBonusFilter,
  competition,
  onCompetition,
  competitions,
  search,
  onSearch,
}: Props) {
  return (
    <div className="filter-bar" aria-label="Filtros del ranking">
      <label className="filter-select">
        <span className="filter-select__label">Posici&oacute;n</span>
        <select
          value={position}
          onChange={(event) => onPosition(event.target.value)}
          aria-label="Filtrar por posici&oacute;n"
        >
          <option value="">Todas las posiciones</option>
          {POSITIONS.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </label>

      <label className="filter-select">
        <span className="filter-select__label">Perfil</span>
        <select
          value={bonusFilter}
          onChange={(event) => onBonusFilter(event.target.value)}
          aria-label="Filtrar por promesa o veterano"
        >
          <option value="">Todos los perfiles</option>
          <option value="Promesa">Promesas</option>
          <option value="Veterano">Veteranos</option>
        </select>
      </label>

      <label className="filter-select">
        <span className="filter-select__label">Competici&oacute;n</span>
        <select
          value={competition ?? ''}
          onChange={(event) => {
            onCompetition(event.target.value ? Number(event.target.value) : undefined)
          }}
          aria-label="Filtrar por competici&oacute;n"
        >
          <option value="">Todas las competiciones</option>
          {competitions.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </label>

      <label className="filter-bar__search">
        <span className="sr-only">Buscar jugador o equipo</span>
        <svg className="filter-bar__search-icon" viewBox="0 0 16 16" fill="none" width="14" height="14" aria-hidden="true">
          <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
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
            aria-label="Limpiar b&uacute;squeda"
          >
            &times;
          </button>
        )}
      </label>
    </div>
  )
}
