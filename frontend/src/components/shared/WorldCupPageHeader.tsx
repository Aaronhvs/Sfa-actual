type WorldCupPageHeaderProps = {
  variant?: 'worldCup' | 'standard'
  eyebrow?: string
  title?: string
  subtitle?: string
  showLogo?: boolean
  showFormula?: boolean
}

export default function WorldCupPageHeader({
  variant = 'worldCup',
  eyebrow = 'Edicion especial Mundial 2026',
  title = 'No todos los goles valen igual',
  subtitle,
  showLogo = true,
  showFormula = true,
}: WorldCupPageHeaderProps) {
  return (
    <header className={`wc-page-header wc-page-header--${variant}`}>
      <div className="wc-page-header__pattern" aria-hidden="true" />
      <div className="wc-page-header__gradient" aria-hidden="true" />
      <div className="wc-page-header__content">
        <div className="wc-page-header__copy">
          <span className="wc-page-header__eyebrow">{eyebrow}</span>
          <h1 className="wc-page-header__title">
            <span className="wc-page-header__title-main">{title}</span>
          </h1>
          {subtitle ? <p className="wc-page-header__subtitle">{subtitle}</p> : null}
          {showFormula ? (
            <div className="wc-page-header__formula" aria-label="Formula simple del ranking SFA">
              <span>Gol</span>
              <i>+</i>
              <span>Rival</span>
              <i>+</i>
              <span>Momento</span>
              <i>+</i>
              <span>Fase</span>
              <i>=</i>
              <strong>Puntos SFA</strong>
            </div>
          ) : null}
        </div>
        {showLogo ? (
          <img src="/logo_sfa_maestro.png" alt="" className="wc-page-header__mark" aria-hidden="true" />
        ) : null}
      </div>
    </header>
  )
}
