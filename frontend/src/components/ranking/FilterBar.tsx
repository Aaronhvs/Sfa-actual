import type { Competition } from '../../types'
import RankingFilterSelect, { type RankingFilterOption } from './RankingFilterSelect'

const POSITIONS: RankingFilterOption[] = [
  { value: '', label: 'Todas las posiciones' },
  { value: 'DEL', label: 'Delantero' },
  { value: 'EXT', label: 'Extremo' },
  { value: 'MCO', label: 'MC Ofensivo' },
  { value: 'MC', label: 'Mediocampista' },
  { value: 'DC', label: 'Def. Central' },
  { value: 'LAT', label: 'Lateral' },
]

const PROFILES: RankingFilterOption[] = [
  { value: '', label: 'Todos los perfiles' },
  { value: 'Promesa', label: 'Promesas' },
  { value: 'Veterano', label: 'Veteranos' },
  { value: 'Goleador', label: 'Goleadores' },
  { value: 'Asistidor', label: 'Asistidores' },
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
  const competitionOptions: RankingFilterOption[] = [
    { value: '', label: 'Todas las competiciones' },
    ...competitions.map((item) => ({ value: String(item.id), label: item.name })),
  ]

  return (
    <div className="filter-bar" aria-label="Filtros del ranking">
      <RankingFilterSelect
        label="Posici&oacute;n"
        ariaLabel="Filtrar por posici&oacute;n"
        value={position}
        options={POSITIONS}
        onChange={onPosition}
      />

      <RankingFilterSelect
        label="Perfil"
        ariaLabel="Filtrar por promesa o veterano"
        value={bonusFilter}
        options={PROFILES}
        onChange={onBonusFilter}
      />

      <RankingFilterSelect
        label="Competici&oacute;n"
        ariaLabel="Filtrar por competici&oacute;n"
        value={competition === undefined ? '' : String(competition)}
        options={competitionOptions}
        onChange={(nextCompetition) => {
          onCompetition(nextCompetition ? Number(nextCompetition) : undefined)
        }}
      />

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
