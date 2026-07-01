type PositionGroup = 'FW' | 'MF' | 'DF'

interface Props {
  position: string
}

const POS_TO_GROUP: Record<string, PositionGroup> = {
  DEL: 'FW', EXT: 'FW',
  MC: 'MF',
  DC: 'DF', LAT: 'DF',
}

const GROUP_LABEL: Record<PositionGroup, string> = {
  FW: 'Delantero',
  MF: 'Centrocampista',
  DF: 'Defensa',
}

const ACTIONS: Array<{ name: string; pts: Record<PositionGroup, number>; note?: string }> = [
  { name: 'Gol',               pts: { FW: 500,  MF: 700,  DF: 850  } },
  { name: 'Asistencia',        pts: { FW: 500,  MF: 520,  DF: 640  } },
  { name: 'Penalti',           pts: { FW: 300,  MF: 380,  DF: 380  } },
  { name: 'Pre-asistencia',    pts: { FW: 250,  MF: 280,  DF: 320  } },
  { name: 'Penal ganado',      pts: { FW: 200,  MF: 180,  DF: 80   } },
  { name: 'Pase clave',        pts: { FW: 150,  MF: 260,  DF: 190  } },
  { name: 'Bloqueo',           pts: { FW: 150,  MF: 100,  DF: 130  } },
  { name: 'Interceptación',    pts: { FW: 90,   MF: 150,  DF: 200  } },
  { name: 'Entrada',           pts: { FW: 110,  MF: 110,  DF: 150  } },
  { name: 'Regate',            pts: { FW: 100,  MF: 100,  DF: 130  } },
  { name: 'Pases completados', pts: { FW: 0,    MF: 8,    DF: 2    }, note: 'por pase' },
  { name: 'Falta recibida',    pts: { FW: 50,   MF: 35,   DF: 20   } },
  { name: 'Duelo ganado',      pts: { FW: 30,   MF: 25,   DF: 25   } },
  { name: 'Regate sufrido',    pts: { FW: 0,    MF: -20,  DF: -50  } },
  { name: 'Falta cometida',    pts: { FW: -30,  MF: -20,  DF: -15  } },
  { name: 'Tarjeta amarilla',  pts: { FW: -150, MF: -150, DF: -150 } },
  { name: 'Tarjeta roja',      pts: { FW: -500, MF: -500, DF: -500 } },
]

export default function ActionValues({ position }: Props) {
  const group: PositionGroup = POS_TO_GROUP[position] ?? 'FW'
  const relevant = ACTIONS.filter((a) => a.pts[group] !== 0)
  const sorted = [...relevant].sort((a, b) => b.pts[group] - a.pts[group])
  const maxPts = Math.max(...sorted.map((a) => a.pts[group]))

  return (
    <>
      <p className="section-title">
        Valor de cada acción &middot;{' '}
        <span style={{ color: 'var(--gold)' }}>{GROUP_LABEL[group]}</span>
      </p>

      <div className="av-list">
        {sorted.map((a, i) => {
          const pts = a.pts[group]
          const isNegative = pts < 0
          const tier = isNegative ? 'neg' : i === 0 ? 'top' : i < 3 ? 'mid' : 'low'
          return (
            <div key={a.name} className={`av-item av-item--${tier}`}>
              <span className="av-item__name">
                {a.name}
                {a.note && <span className="av-item__note"> ({a.note})</span>}
              </span>
              <span className="av-item__pts">
                {pts > 0 ? '+' : ''}{pts.toLocaleString('es-ES')}
                <span className="av-item__pts-label"> pts</span>
              </span>
            </div>
          )
        })}
      </div>
    </>
  )
}
