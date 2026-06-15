import { Link, NavLink, useLocation } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'

const LINKS = [
  { to: '/ranking', label: 'Ranking', wc: false, soon: false },
  { to: '/mundial', label: 'Mundial 26', wc: true, soon: false },
  { to: '/teams', label: 'Equipos', wc: false, soon: false },
  { to: '/compare', label: 'Comparar', wc: false, soon: true },
  { to: '/metodologia', label: 'Metodología', wc: false },
]

export default function Navbar() {
  const location = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onScroll = () => {
      const nextScrolled = window.scrollY > 24
      setScrolled((current) => current === nextScrolled ? current : nextScrolled)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname, location.search])

  useEffect(() => {
    if (!menuOpen) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const focusable = drawerRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')
    focusable?.[0]?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setMenuOpen(false)
        menuButtonRef.current?.focus()
        return
      }

      if (event.key !== 'Tab' || !focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  const close = () => setMenuOpen(false)

  return (
    <>
      <nav className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
        <Link to="/ranking" className="navbar__logo-link" aria-label="SFA, ir al ranking">
          <img
            src="/logo.png"
            alt="SFA"
            className="navbar__logo-img"
          />
        </Link>
        <div className="navbar__pill">
          <div className="navbar__nav">
            {LINKS.map(({ to, label, wc, soon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `navbar__link${wc ? ' navbar__link--wc' : ''}${soon ? ' navbar__link--soon' : ''}${isActive ? ' navbar__link--active' : ''}`
                }
                title={soon ? 'En construcción' : undefined}
              >
                {label}
              </NavLink>
            ))}
          </div>

          <button
            ref={menuButtonRef}
            type="button"
            className={`navbar__hamburger${menuOpen ? ' navbar__hamburger--open' : ''}`}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
          >
            <span />
            <span />
          </button>
        </div>
      </nav>

      <div
        className={`navbar__overlay${menuOpen ? ' navbar__overlay--open' : ''}`}
        onClick={close}
        aria-hidden={!menuOpen}
      >
        <div
          ref={drawerRef}
          id="mobile-navigation"
          className="navbar__drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Navegación principal"
          onClick={(e) => e.stopPropagation()}
        >
          {LINKS.map(({ to, label, wc, soon }, i) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `navbar__drawer-link${wc ? ' navbar__drawer-link--wc' : ''}${soon ? ' navbar__drawer-link--soon' : ''}${isActive ? ' navbar__drawer-link--active' : ''}`
              }
              onClick={close}
              tabIndex={menuOpen ? 0 : -1}
              style={menuOpen ? { animationDelay: `${i * 55}ms` } : undefined}
            >
              <span>{label}</span>
              {soon && <small>En construcción</small>}
            </NavLink>
          ))}
        </div>
      </div>
    </>
  )
}
