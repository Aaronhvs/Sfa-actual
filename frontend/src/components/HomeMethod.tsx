import { Link } from 'react-router-dom'
import { FootballIcon } from './shared/FootballVisuals'
import './HomeMethod.css'

export default function HomeMethod({ rankingUrl }: { rankingUrl: string }) {
  return <section className="sfa-method" aria-labelledby="sfa-method-title">
    <div className="sfa-method__intro">
      <p className="home-eyebrow">El criterio SFA</p>
      <h2 id="sfa-method-title">La misma acción.<br />Otro contexto.<br />Otro valor.</h2>
      <p>Un gol no ocurre en el vacío. SFA pondera el rendimiento según el <strong>rival</strong>, el <strong>momento del partido</strong> y la <strong>competición.</strong></p>
      <div className="sfa-method__actions">
        <Link to={rankingUrl} className="home-button">Ver ranking completo <span aria-hidden="true">↗</span></Link>
        <Link to="/metodologia" className="sfa-action-link">Explorar la metodología <span aria-hidden="true">↗</span></Link>
      </div>
    </div>
    <div className="sfa-method__criteria">
      <div><FootballIcon kind="rival" /><span><h3>Contra quién</h3><p>El nivel del rival forma parte de la evaluación.</p></span></div>
      <div><FootballIcon kind="moment" /><span><h3>En qué momento</h3><p>El minuto y el marcador sitúan el impacto de la acción.</p></span></div>
      <div><FootballIcon kind="competition" /><span><h3>En qué escenario</h3><p>El torneo y su fase intervienen en la ponderación.</p></span></div>
      <p className="sfa-method__note">Criterios propios. Consulta las reglas y sus ponderaciones.</p>
    </div>
  </section>
}
