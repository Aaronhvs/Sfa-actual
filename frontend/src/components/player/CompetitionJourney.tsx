import type { PlayerCompetitionAchievement } from '../../types'
import { competitionLabel, phaseBadge, phaseLabel } from '../../utils/footballLabels'
import { seasonLabel } from '../../utils/season'

interface Props {
  achievements: PlayerCompetitionAchievement[]
  historical: boolean
}

function formatBonus(points: number): string {
  return Math.round(points).toLocaleString('es-ES')
}

function TrophyIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 3h8v3.5c0 3.3-1.8 5.5-4 5.5s-4-2.2-4-5.5V3Z" />
      <path d="M8 5H4v1.5C4 9 5.5 10.5 8 10.5M16 5h4v1.5c0 2.5-1.5 4-4 4M12 12v4M8.5 20h7M10 16h4v4h-4z" />
    </svg>
  )
}

export default function CompetitionJourney({ achievements, historical }: Props) {
  if (achievements.length === 0) return null

  const grouped = achievements.reduce<Record<string, PlayerCompetitionAchievement[]>>(
    (groups, achievement) => {
      ;(groups[achievement.season] ??= []).push(achievement)
      return groups
    },
    {},
  )

  return (
    <section className="competition-journey" aria-labelledby="competition-journey-title">
      <h2 id="competition-journey-title" className="competition-journey__title">
        Palmar&eacute;s y puntos por fase
      </h2>
      <div className="competition-journey__groups">
        {Object.entries(grouped).map(([season, items]) => (
          <div className="competition-journey__group" key={season}>
            {historical && (
              <p className="competition-journey__season">{seasonLabel(season)}</p>
            )}
            <div className="competition-journey__list">
              {items.map((achievement) => {
                const champion = achievement.title_count > 0
                return (
                  <article
                    className={`competition-journey__item${champion ? ' competition-journey__item--champion' : ''}`}
                    key={achievement.achievement_id}
                  >
                    <span className="competition-journey__icon">
                      {champion ? <TrophyIcon /> : phaseBadge(achievement.phase)}
                    </span>
                    <span className="competition-journey__body">
                      <strong>{competitionLabel(achievement.competition_name)}</strong>
                      <small>{achievement.team_name}</small>
                    </span>
                    <span className="competition-journey__result">
                      {champion ? (
                        <>
                          <strong>+{formatBonus(achievement.bonus_pts)}</strong>
                          <small>pts por el t&iacute;tulo</small>
                        </>
                      ) : (
                        <>
                          <strong>{phaseLabel(achievement.phase)}</strong>
                          <small>
                            {achievement.bonus_pts > 0
                              ? `+${formatBonus(achievement.bonus_pts)} pts por fase alcanzada`
                              : 'fase alcanzada'}
                          </small>
                        </>
                      )}
                    </span>
                  </article>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
