import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__brand">
          <Link to="/ranking" className="site-footer__logo-link" aria-label="SFA">
            <img src="/blanco.png" alt="SFA" className="site-footer__logo-img" />
          </Link>
          <p className="site-footer__tagline">Sistema de análisis de fútbol · Temporada 2024/25</p>
        </div>

        <nav className="site-footer__nav" aria-label="Pie de página">
          <Link to="/ranking" className="site-footer__nav-link">Ranking</Link>
          <Link to="/compare" className="site-footer__nav-link">Comparar</Link>
          <Link to="/metodologia" className="site-footer__nav-link">Metodología</Link>
        </nav>

        <p className="site-footer__legal">
          Datos: API-Football · Solo con fines analíticos y educativos
        </p>
      </div>
    </footer>
  )
}
