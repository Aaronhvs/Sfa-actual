const TEAM_ALIAS_GROUPS: string[][] = [
  ['argentina'],
  ['australia'],
  ['austria'],
  ['belgium', 'belgica', 'belgique'],
  ['brazil', 'brasil'],
  ['canada'],
  ['colombia'],
  ['croatia', 'croacia'],
  ['czechia', 'chequia', 'czech republic', 'republica checa'],
  ['ecuador'],
  ['egypt', 'egipto'],
  ['england', 'inglaterra'],
  ['france', 'francia'],
  ['germany', 'alemania', 'deutschland'],
  ['ghana'],
  ['haiti'],
  ['iran'],
  ['japan', 'japon'],
  ['jordan', 'jordania'],
  ['mexico'],
  ['morocco', 'marruecos'],
  ['netherlands', 'paises bajos', 'holanda', 'holland'],
  ['new zealand', 'nueva zelanda'],
  ['norway', 'noruega'],
  ['panama'],
  ['paraguay'],
  ['portugal'],
  ['qatar', 'catar'],
  ['scotland', 'escocia'],
  ['senegal'],
  ['south africa', 'sudafrica'],
  ['south korea', 'corea del sur', 'korea republic', 'republica de corea'],
  ['spain', 'espana'],
  ['switzerland', 'suiza'],
  ['tunisia', 'tunez'],
  ['turkey', 'turquia', 'turkiye'],
  ['united states', 'estados unidos', 'usa', 'eeuu', 'ee.uu.'],
  ['uruguay'],
  ['uzbekistan'],
  ['ivory coast', 'costa de marfil', "cote d'ivoire"],
  ['dr congo', 'rd congo', 'republica democratica del congo', 'congo dr'],
  ['bosnia and herzegovina', 'bosnia y herzegovina', 'bosnia & herzegovina', 'bosnia'],
  ['curacao', 'curazao'],
  ['paris saint germain', 'paris saint-germain', 'psg'],
  ['bayern munchen', 'bayern munich'],
  ['inter', 'internazionale', 'inter milan'],
  ['atletico madrid', 'atleti'],
  ['manchester city', 'man city'],
  ['manchester united', 'man united', 'man utd'],
  ['tottenham', 'tottenham hotspur', 'spurs'],
]

export function normalizeSearchText(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function teamAliasTerms(value: string): string[] {
  const normalized = normalizeSearchText(value)
  const terms = new Set<string>([value])

  if (!normalized) return []

  for (const group of TEAM_ALIAS_GROUPS) {
    const normalizedGroup = group.map(normalizeSearchText)
    if (normalizedGroup.some((alias) => alias.includes(normalized) || normalized.includes(alias))) {
      group.forEach((alias) => terms.add(alias))
    }
  }

  return [...terms].filter((term) => normalizeSearchText(term).length > 0)
}

export function teamMatchesSearch(teamName: string, query: string): boolean {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) return true

  return teamAliasTerms(teamName).some((term) =>
    normalizeSearchText(term).includes(normalizedQuery)
  )
}

export function playerOrTeamMatchesSearch(playerName: string, teamName: string, query: string): boolean {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) return true

  return (
    normalizeSearchText(playerName).includes(normalizedQuery)
    || teamMatchesSearch(teamName, query)
  )
}
