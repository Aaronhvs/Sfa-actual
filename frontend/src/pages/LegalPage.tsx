import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    number: '01',
    title: 'Objeto del sitio',
    content: (
      <>
        <p>
          Stats Football Award (“SFA”) es un proyecto informativo y analítico dedicado
          a presentar estadísticas, rankings y visualizaciones relacionadas con el
          fútbol. El contenido se ofrece con fines informativos, educativos y de
          entretenimiento.
        </p>
        <p>
          La información publicada no constituye asesoría profesional, deportiva,
          financiera ni de apuestas. El uso del sitio no crea una relación contractual
          entre SFA y sus visitantes.
        </p>
      </>
    ),
  },
  {
    number: '02',
    title: 'Datos deportivos y metodología',
    content: (
      <>
        <p>
          Parte de los datos deportivos proviene de API-Football y de otras fuentes
          externas identificadas dentro del proyecto. Los datos pueden contener
          retrasos, correcciones, omisiones o diferencias respecto de las fuentes
          oficiales.
        </p>
        <p>
          Los puntos y rankings SFA son resultados de una metodología propia. No
          representan una clasificación oficial y pueden cambiar cuando se actualicen
          datos, reglas o cálculos.
        </p>
      </>
    ),
  },
  {
    number: '03',
    title: 'Propiedad intelectual',
    content: (
      <>
        <p>
          El diseño, identidad visual, textos, metodología, código y elementos
          originales de SFA pertenecen a sus respectivos titulares. Las marcas,
          escudos, fotografías y nombres de competiciones, clubes, selecciones y
          jugadores pertenecen a sus propietarios correspondientes.
        </p>
        <p>
          No se permite reproducir, comercializar, extraer masivamente o reutilizar el
          contenido y las bases de datos de SFA sin autorización previa, salvo los usos
          permitidos por la legislación aplicable.
        </p>
      </>
    ),
  },
  {
    number: '04',
    title: 'Privacidad y datos personales',
    content: (
      <>
        <p>
          Actualmente SFA no ofrece registro de cuentas, comentarios, compras ni
          formularios para recopilar directamente nombres, correos electrónicos,
          teléfonos u otros datos identificatorios de sus visitantes.
        </p>
        <p>
          El servidor o proveedor de alojamiento puede generar registros técnicos
          básicos, como dirección IP, navegador, fecha de acceso y páginas solicitadas,
          para seguridad, diagnóstico y funcionamiento del servicio. Estos registros
          deben conservarse únicamente durante el tiempo necesario para esas
          finalidades.
        </p>
      </>
    ),
  },
  {
    number: '05',
    title: 'Cookies y almacenamiento local',
    content: (
      <>
        <p>
          SFA puede utilizar almacenamiento local estrictamente funcional para recordar
          preferencias de interfaz, por ejemplo, si un aviso ya fue cerrado. Esta
          información permanece en el dispositivo y no se utiliza para publicidad
          personalizada.
        </p>
        <p>
          Si en el futuro se incorporan herramientas de analítica, publicidad o cookies
          no esenciales, esta política será actualizada y se implementarán los
          mecanismos de información y consentimiento que correspondan.
        </p>
      </>
    ),
  },
  {
    number: '06',
    title: 'Servicios y enlaces externos',
    content: (
      <p>
        El sitio contiene imágenes, datos y enlaces proporcionados por terceros,
        incluidas plataformas sociales. El acceso a esos servicios se rige por sus
        propios términos y políticas. SFA no controla su disponibilidad, seguridad ni
        tratamiento de datos.
      </p>
    ),
  },
  {
    number: '07',
    title: 'Uso aceptable',
    content: (
      <p>
        El visitante se compromete a no interferir con el funcionamiento del sitio,
        intentar accesos no autorizados, ejecutar extracción automatizada abusiva,
        suplantar la identidad de SFA ni utilizar sus contenidos con fines ilícitos o
        engañosos.
      </p>
    ),
  },
  {
    number: '08',
    title: 'Limitación de responsabilidad',
    content: (
      <p>
        SFA procura mantener información correcta y disponible, pero no garantiza que
        el sitio funcione sin interrupciones ni que todos los datos sean completos,
        exactos o actuales. El uso de la información y las decisiones tomadas a partir
        de ella son responsabilidad del visitante.
      </p>
    ),
  },
  {
    number: '09',
    title: 'Legislación aplicable',
    content: (
      <>
        <p>
          Esta política se interpreta conforme a la legislación de la República de
          Chile, incluida la Ley N.º 19.628 sobre protección de la vida privada y sus
          modificaciones. También se considerará la Ley N.º 21.719 desde su entrada en
          vigencia.
        </p>
        <p>
          Las solicitudes relacionadas con privacidad o contenido pueden dirigirse a
          SFA mediante sus perfiles sociales oficiales enlazados al final de esta
          página.
        </p>
      </>
    ),
  },
  {
    number: '10',
    title: 'Cambios a esta política',
    content: (
      <p>
        SFA podrá actualizar este documento para reflejar cambios legales, técnicos o
        funcionales. La versión vigente y su fecha de actualización estarán siempre
        disponibles en esta página.
      </p>
    ),
  },
]

export default function LegalPage() {
  useEffect(() => {
    window.scrollTo(0, 0)
    document.body.classList.remove('mode-tournament')
  }, [])

  return (
    <div className="legal-page">
      <header className="legal-hero">
        <div className="legal-hero__grid" aria-hidden="true" />
        <div className="legal-hero__content">
          <Link to="/ranking" className="legal-back">
            <span aria-hidden="true">←</span>
            Volver a SFA
          </Link>
          <span className="legal-eyebrow">Transparencia y uso responsable</span>
          <h1>Legal <em>&amp;</em> privacidad</h1>
          <p>
            Condiciones generales de uso y tratamiento de información aplicables a
            Stats Football Award.
          </p>
          <div className="legal-hero__meta">
            <span>Jurisdicción · Chile</span>
            <span>Actualizado · 14 junio 2026</span>
          </div>
        </div>
      </header>

      <main className="legal-content">
        <aside className="legal-index">
          <span>Contenido</span>
          {SECTIONS.map((section) => (
            <a href={`#legal-${section.number}`} key={section.number}>
              <b>{section.number}</b>
              {section.title}
            </a>
          ))}
        </aside>

        <div className="legal-document">
          <div className="legal-notice">
            <strong>Nota importante</strong>
            <p>
              Este documento es una base informativa general para el estado actual del
              proyecto y no reemplaza una revisión jurídica profesional.
            </p>
          </div>

          {SECTIONS.map((section) => (
            <section
              className="legal-section"
              id={`legal-${section.number}`}
              key={section.number}
            >
              <span>{section.number}</span>
              <div>
                <h2>{section.title}</h2>
                {section.content}
              </div>
            </section>
          ))}

          <section className="legal-contact">
            <span className="legal-eyebrow">Canales oficiales</span>
            <h2>Contacto y redes</h2>
            <div>
              <a href="https://www.instagram.com/statsfootballaward/" target="_blank" rel="noreferrer">Instagram</a>
              <a href="https://www.youtube.com/@StatsFootballAward" target="_blank" rel="noreferrer">YouTube</a>
              <a href="https://www.tiktok.com/@statsfootballaward" target="_blank" rel="noreferrer">TikTok</a>
              <a href="https://x.com/StatsfootballAw" target="_blank" rel="noreferrer">X</a>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
