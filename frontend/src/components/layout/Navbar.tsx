import { Link, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'

const LINKS = [
  { to: '/ranking', label: 'Ranking', wc: false },
  { to: '/mundial', label: 'Mundial 26', wc: true },
  { to: '/teams',   label: 'Equipos', wc: false },
  { to: '/compare', label: 'Comparar', wc: false },
  { to: '/metodologia', label: 'Metodología', wc: false },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const close = () => setMenuOpen(false)

  return (
    <>
      <nav className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
<div className="navbar__pill">
          <div className="navbar__nav">
            {LINKS.map(({ to, label, wc }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `navbar__link${wc ? ' navbar__link--wc' : ''}${isActive ? ' navbar__link--active' : ''}`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>

          <button
            className={`navbar__hamburger${menuOpen ? ' navbar__hamburger--open' : ''}`}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={menuOpen}
          >
            <span />
            <span />
          </button>
        </div>
      </nav>

      <div
        className={`navbar__overlay${menuOpen ? ' navbar__overlay--open' : ''}`}
        onClick={close}
      >
        <div className="navbar__drawer" onClick={(e) => e.stopPropagation()}>
          {LINKS.map(({ to, label, wc }, i) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `navbar__drawer-link${wc ? ' navbar__drawer-link--wc' : ''}${isActive ? ' navbar__drawer-link--active' : ''}`
              }
              onClick={close}
              style={menuOpen ? { animationDelay: `${i * 55}ms` } : undefined}
            >
              {label}
            </NavLink>
          ))}
        </div>
      </div>
    </>
  )
}
