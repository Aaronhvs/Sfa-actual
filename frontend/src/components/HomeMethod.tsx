import { Link } from 'react-router-dom'
import { FootballIcon } from './shared/FootballVisuals'
import { ArrowIcon } from './tournaments/MatchUI'
import './HomeMethod.css'

const CRITERIA = [
  { icon: 'rival', title: 'Contra quién', text: 'Marcar al líder vale más que marcar al colista.' },
  { icon: 'moment', title: 'En qué momento', text: 'Un gol en el 89 con empate pesa más que el cuarto de una goleada.' },
  { icon: 'competition', title: 'En qué escenario', text: 'Una semifinal de Champions no es una jornada de liga.' },
] as const

export default function HomeMethod() {
  return (
    <section className="home-method" aria-labelledby="home-method-title">
      <header>
        <p className="tp-eyebrow">El criterio SFA</p>
        <h2 id="home-method-title">Tres preguntas detrás de cada punto</h2>
      </header>
      <ul>
        {CRITERIA.map(({ icon, title, text }) => (
          <li key={title}>
            <span className="home-method__icon"><FootballIcon kind={icon} /></span>
            <strong>{title}</strong>
            <span>{text}</span>
          </li>
        ))}
      </ul>
      <Link to="/metodologia" className="home-method__link">Leer la metodología <ArrowIcon /></Link>
    </section>
  )
}
