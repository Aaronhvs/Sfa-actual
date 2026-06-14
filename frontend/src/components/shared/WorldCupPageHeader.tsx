interface Props {
  totalPlayers: number
}

export default function WorldCupPageHeader({ totalPlayers }: Props) {
  return (
    <header className="wc-page-header">
      <div className="wc-page-header__pattern" aria-hidden="true" />
      <div className="wc-page-header__gradient" aria-hidden="true" />
      <div className="wc-page-header__spectrum" aria-hidden="true" />
      <div className="wc-page-header__content">
        <div className="wc-page-header__copy">
          <span className="wc-page-header__eyebrow">SFA · Edición Global</span>
          <h1 className="wc-page-header__title">
            <span className="wc-page-header__title-main">Ranking Mundial</span>
            <span className="wc-page-header__title-year">2026</span>
          </h1>
          <p className="wc-page-header__subtitle">
            Clasificación SFA · {totalPlayers.toLocaleString('es-ES')} jugadores
          </p>
          <p className="wc-page-header__independent">
            Ranking independiente del torneo
          </p>
        </div>
        <div className="wc-page-header__stamp" aria-label="Edición 2026, 48 selecciones">
          <span>48</span>
          <strong>Selecciones</strong>
          <small>Edición 2026</small>
        </div>
      </div>
    </header>
  )
}
