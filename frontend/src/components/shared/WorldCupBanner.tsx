import { useEffect, useState } from 'react'

interface Props {
  onViewWorldCup?: () => void
}

const DISMISS_KEY = 'sfa_wc2026_banner_v1'
const DISMISS_TTL = 86_400_000

function isDismissed(): boolean {
  try {
    const timestamp = localStorage.getItem(DISMISS_KEY)
    if (!timestamp) return false
    return Date.now() - Number(timestamp) < DISMISS_TTL
  } catch {
    return false
  }
}

export default function WorldCupBanner({ onViewWorldCup }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!isDismissed()) setVisible(true)
  }, [])

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()))
    } catch {
      // El aviso sigue siendo descartable aunque el almacenamiento no esté disponible.
    }
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="wc-banner" role="status" aria-live="polite">
      <div className="wc-banner__inner">
        <div className="wc-banner__left">
          <span className="wc-banner__eyebrow">Mundial 2026</span>
          <p className="wc-banner__text">
            Los puntos del torneo se sumarán a esta temporada al finalizar la competición.
          </p>
        </div>
        <div className="wc-banner__actions">
          {onViewWorldCup && (
            <button
              className="wc-banner__cta"
              onClick={onViewWorldCup}
              type="button"
            >
              Ver ranking del Mundial
            </button>
          )}
          <button
            className="wc-banner__dismiss"
            onClick={dismiss}
            type="button"
            aria-label="Cerrar aviso"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
              <path
                d="M1 1l10 10M11 1L1 11"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
