import { Link } from 'react-router-dom'

const SOCIAL_LINKS = [
  {
    label: 'Instagram',
    href: 'https://www.instagram.com/statsfootballaward/',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" className="social-icon__fill" />
      </svg>
    ),
  },
  {
    label: 'YouTube',
    href: 'https://www.youtube.com/@StatsFootballAward',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 8.1a3 3 0 0 0-2.1-2.1C17 5.5 12 5.5 12 5.5S7 5.5 5.1 6A3 3 0 0 0 3 8.1 31 31 0 0 0 2.5 12 31 31 0 0 0 3 15.9 3 3 0 0 0 5.1 18c1.9.5 6.9.5 6.9.5s5 0 6.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-3.9 31 31 0 0 0-.5-3.9Z" />
        <path d="m10 9 5 3-5 3Z" className="social-icon__fill" />
      </svg>
    ),
  },
  {
    label: 'TikTok',
    href: 'https://www.tiktok.com/@statsfootballaward',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 4v10.2a4.2 4.2 0 1 1-3.6-4.1v3a1.4 1.4 0 1 0 .8 1.3V4h2.8Z" />
        <path d="M14 4c.5 2.6 2 4 4.5 4.4v3A8 8 0 0 1 14 9.6Z" />
      </svg>
    ),
  },
  {
    label: 'X',
    href: 'https://x.com/StatsfootballAw',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 4h4.2l3.6 4.8L17 4h2l-5.3 6.2L20 20h-4.2l-4.1-5.5L7 20H5l5.8-6.9Z" />
      </svg>
    ),
  },
]

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__brand">
          <Link to="/ranking" className="site-footer__logo-link" aria-label="SFA">
            <img src="/blanco.png" alt="SFA" className="site-footer__logo-img" />
          </Link>
          <p className="site-footer__tagline">Estadísticas, contexto e impacto real en el fútbol.</p>
          <div className="site-footer__socials" aria-label="Redes sociales de SFA">
            {SOCIAL_LINKS.map((social) => (
              <a
                key={social.label}
                href={social.href}
                target="_blank"
                rel="noreferrer"
                className="site-footer__social-link"
                aria-label={`${social.label} de SFA`}
                title={social.label}
              >
                {social.icon}
              </a>
            ))}
          </div>
        </div>

        <nav className="site-footer__nav" aria-label="Pie de página">
          <Link to="/ranking" className="site-footer__nav-link">Ranking</Link>
          <Link to="/compare" className="site-footer__nav-link">Comparar</Link>
          <Link to="/metodologia" className="site-footer__nav-link">Metodología</Link>
          <Link to="/legal" className="site-footer__nav-link">Legal y privacidad</Link>
        </nav>

        <div className="site-footer__legal">
          <span>© {new Date().getFullYear()} Stats Football Award</span>
          <span>Datos deportivos provistos por fuentes externas.</span>
        </div>
      </div>
    </footer>
  )
}
