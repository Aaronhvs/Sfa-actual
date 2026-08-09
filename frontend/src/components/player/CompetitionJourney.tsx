import type { PlayerCompetitionAchievement } from '../../types'
import { competitionLabel, phaseBadge, phaseLabel } from '../../utils/footballLabels'
import { seasonLabel } from '../../utils/season'
import { worldCupTeamNameFromString } from '../../utils/worldCupTeams'

interface Props {
  achievements: PlayerCompetitionAchievement[]
  historical: boolean
}

function formatBonus(points: number): string {
  return Math.round(points).toLocaleString('es-ES')
}

function achievementTone(phase: string, champion: boolean): string {
  if (champion) return 'champion'
  if (phase === 'runner_up' || phase === 'final') return 'finalist'
  if (phase === 'semi_final' || phase === 'quarter_final') return 'deep-run'
  return 'knockout'
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
                const tone = achievementTone(achievement.phase, champion)
                const competition = competitionLabel(achievement.competition_name)
                const phase = champion ? 'Campe\u00f3n' : phaseLabel(achievement.phase)
                const bonus = achievement.bonus_pts > 0
                  ? `+${formatBonus(achievement.bonus_pts)} pts SFA`
                  : 'Sin puntos adicionales'
                const teamName = competition === 'Mundial'
                  ? worldCupTeamNameFromString(achievement.team_name)
                  : achievement.team_name
                return (
                  <article
                    className={`competition-journey__item competition-journey__item--${tone}${champion ? ' competition-journey__item--champion' : ''}`}
                    key={achievement.achievement_id}
                    tabIndex={0}
                    aria-label={`${phase} de ${competition}. ${teamName}, ${seasonLabel(achievement.season)}. ${bonus}.`}
                    onFocus={(event) => event.currentTarget.scrollIntoView({ block: 'nearest', inline: 'center' })}
                  >
                    <span className="competition-journey__face competition-journey__face--summary" aria-hidden="true">
                      <span className="competition-journey__icon">
                        {champion ? <TrophyIcon /> : phaseBadge(achievement.phase)}
                      </span>
                      <span className="competition-journey__body">
                        <small>{phase}</small>
                        <strong>{competition}</strong>
                      </span>
                    </span>
                    <span className="competition-journey__face competition-journey__face--detail" aria-hidden="true">
                      <small>{teamName}</small>
                      <span>{seasonLabel(achievement.season)}</span>
                      <strong>{bonus}</strong>
                      <small>{champion ? 'por el t\u00edtulo' : 'por fase alcanzada'}</small>
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
