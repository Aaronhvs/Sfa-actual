interface TeamColorRule {
  aliases: string[]
  color: string
}

const TEAM_COLOR_RULES: TeamColorRule[] = [
  { aliases: ['paris saint germain', 'paris sg', 'psg'], color: '#004170' },
  { aliases: ['olympique de marseille', 'marseille'], color: '#2FAEE0' },
  { aliases: ['olympique lyonnais', 'lyon'], color: '#1F5AA6' },
  { aliases: ['as monaco', 'monaco'], color: '#D71920' },
  { aliases: ['liverpool'], color: '#C8102E' },
  { aliases: ['arsenal'], color: '#D22630' },
  { aliases: ['manchester city'], color: '#6CABDD' },
  { aliases: ['manchester united'], color: '#DA291C' },
  { aliases: ['chelsea'], color: '#034694' },
  { aliases: ['tottenham'], color: '#D8DCE3' },
  { aliases: ['aston villa'], color: '#670E36' },
  { aliases: ['newcastle'], color: '#A7A9AC' },
  { aliases: ['barcelona'], color: '#A50044' },
  { aliases: ['real madrid'], color: '#D6B760' },
  { aliases: ['atletico madrid'], color: '#CB3524' },
  { aliases: ['athletic club', 'athletic bilbao'], color: '#EE2523' },
  { aliases: ['real sociedad'], color: '#2A6EBB' },
  { aliases: ['bayern munchen', 'bayern munich'], color: '#DC052D' },
  { aliases: ['borussia dortmund', 'dortmund'], color: '#FDE100' },
  { aliases: ['bayer leverkusen', 'leverkusen'], color: '#E32221' },
  { aliases: ['rb leipzig'], color: '#D00027' },
  { aliases: ['inter milan', 'internazionale', 'inter'], color: '#0057B8' },
  { aliases: ['ac milan', 'milan'], color: '#FB090B' },
  { aliases: ['juventus'], color: '#C8C8C8' },
  { aliases: ['napoli'], color: '#12A0D7' },
  { aliases: ['as roma', 'roma'], color: '#8E1F2F' },
  { aliases: ['atalanta'], color: '#1E71B8' },
  { aliases: ['benfica'], color: '#E83030' },
  { aliases: ['porto'], color: '#0050A4' },
  { aliases: ['sporting cp', 'sporting lisbon'], color: '#008F49' },
  { aliases: ['ajax'], color: '#D2122E' },
  { aliases: ['psv'], color: '#E31837' },
  { aliases: ['feyenoord'], color: '#D4101E' },
  { aliases: ['argentina'], color: '#6CACE4' },
  { aliases: ['spain', 'espana'], color: '#C60B1E' },
  { aliases: ['france', 'francia'], color: '#1D428A' },
  { aliases: ['morocco', 'marruecos'], color: '#C1272D' },
  { aliases: ['brazil', 'brasil'], color: '#F2C300' },
  { aliases: ['england', 'inglaterra'], color: '#D9DDE5' },
  { aliases: ['germany', 'alemania'], color: '#C6C6C6' },
  { aliases: ['portugal'], color: '#B51F2E' },
  { aliases: ['netherlands', 'paises bajos'], color: '#E56A1A' },
]

const FALLBACK_COLORS = [
  '#A96561',
  '#557F9E',
  '#5E8B78',
  '#9A7A48',
  '#766C9B',
  '#8D607E',
]

function normalizeTeamName(name: string) {
  return name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function canonicalTeamName(name: string) {
  return name
    .replace(/^(fc|cf|ac|sc)\s+/, '')
    .replace(/\s+(fc|cf|ac|sc)$/, '')
}

function fallbackColor(name: string) {
  let hash = 0
  for (const character of name) {
    hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0
  }
  return FALLBACK_COLORS[Math.abs(hash) % FALLBACK_COLORS.length]
}

export function teamBrandColor(name: string | null | undefined, emptyFallback: string) {
  if (!name) return emptyFallback
  const normalized = normalizeTeamName(name)
  const canonical = canonicalTeamName(normalized)
  const rule = TEAM_COLOR_RULES.find(({ aliases }) => (
    aliases.some((alias) => normalized === alias || canonical === alias)
  ))
  return rule?.color ?? fallbackColor(normalized)
}
