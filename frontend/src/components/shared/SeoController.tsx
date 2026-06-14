import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const SITE_URL = 'https://statsfootballaward.com'
const DEFAULT_TITLE = 'Stats Football Award (SFA) | Ranking de jugadores de fútbol'
const DEFAULT_DESCRIPTION = 'Stats Football Award (SFA) es un ranking independiente de jugadores de fútbol que mide el impacto real de cada actuación según el rival, el momento y la competición.'

type SeoData = {
  title: string
  description: string
  canonicalPath: string
}

function getSeoData(pathname: string): SeoData {
  if (pathname.startsWith('/player/')) {
    return {
      title: 'Perfil y puntos SFA del jugador | Stats Football Award',
      description: 'Consulta estadísticas, actuaciones, puntos SFA y evolución de un jugador en Stats Football Award.',
      canonicalPath: pathname,
    }
  }

  if (pathname.startsWith('/mundial/partido/')) {
    return {
      title: 'Partido del Mundial 2026 | Alineaciones y puntos SFA',
      description: 'Consulta el resultado, las alineaciones, estadísticas y puntos SFA del partido del Mundial 2026.',
      canonicalPath: pathname,
    }
  }

  const pages: Record<string, SeoData> = {
    '/': {
      title: DEFAULT_TITLE,
      description: DEFAULT_DESCRIPTION,
      canonicalPath: '/ranking',
    },
    '/ranking': {
      title: DEFAULT_TITLE,
      description: DEFAULT_DESCRIPTION,
      canonicalPath: '/ranking',
    },
    '/mundial': {
      title: 'Mundial 2026 | Partidos, clasificación y ranking SFA',
      description: 'Sigue los partidos, la clasificación y el ranking independiente de jugadores del Mundial 2026.',
      canonicalPath: '/mundial',
    },
    '/compare': {
      title: 'Comparar jugadores de fútbol | Stats Football Award',
      description: 'Compara jugadores por estadísticas, rendimiento contextual e impacto real con el sistema SFA.',
      canonicalPath: '/compare',
    },
    '/teams': {
      title: 'Equipos de fútbol | Stats Football Award',
      description: 'Explora equipos y el rendimiento de sus jugadores en el ranking Stats Football Award.',
      canonicalPath: '/teams',
    },
    '/metodologia': {
      title: 'Cómo se calculan los puntos SFA | Metodología',
      description: 'Conoce cómo Stats Football Award valora goles, asistencias y acciones según su contexto, dificultad y trascendencia.',
      canonicalPath: '/metodologia',
    },
    '/legal': {
      title: 'Legal y privacidad | Stats Football Award',
      description: 'Consulta las bases legales, condiciones de uso y política de privacidad de Stats Football Award.',
      canonicalPath: '/legal',
    },
  }

  return pages[pathname] ?? pages['/ranking']
}

function setMeta(selector: string, attribute: string, value: string) {
  const element = document.head.querySelector<HTMLMetaElement>(selector)
  element?.setAttribute(attribute, value)
}

export default function SeoController() {
  const { pathname } = useLocation()

  useEffect(() => {
    const seo = getSeoData(pathname)
    const canonicalUrl = `${SITE_URL}${seo.canonicalPath}`

    document.title = seo.title
    setMeta('meta[name="description"]', 'content', seo.description)
    setMeta('meta[property="og:title"]', 'content', seo.title)
    setMeta('meta[property="og:description"]', 'content', seo.description)
    setMeta('meta[property="og:url"]', 'content', canonicalUrl)
    setMeta('meta[name="twitter:title"]', 'content', seo.title)
    setMeta('meta[name="twitter:description"]', 'content', seo.description)

    const canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    canonical?.setAttribute('href', canonicalUrl)
  }, [pathname])

  return null
}
