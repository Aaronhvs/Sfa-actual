import type { WcTeam } from '../types'

const WORLD_CUP_TEAM_NAMES_ES: Record<number, string> = {
  1: 'Bélgica',
  2: 'Francia',
  3: 'Croacia',
  5: 'Suecia',
  6: 'Brasil',
  7: 'Uruguay',
  8: 'Colombia',
  9: 'España',
  10: 'Inglaterra',
  11: 'Panamá',
  12: 'Japón',
  13: 'Senegal',
  15: 'Suiza',
  16: 'México',
  17: 'Corea del Sur',
  20: 'Australia',
  22: 'Irán',
  23: 'Arabia Saudita',
  25: 'Alemania',
  26: 'Argentina',
  27: 'Portugal',
  28: 'Túnez',
  31: 'Marruecos',
  32: 'Egipto',
  770: 'Chequia',
  775: 'Austria',
  777: 'Turquía',
  1090: 'Noruega',
  1108: 'Escocia',
  1113: 'Bosnia y Herzegovina',
  1118: 'Países Bajos',
  1501: 'Costa de Marfil',
  1504: 'Ghana',
  1508: 'República Democrática del Congo',
  1531: 'Sudáfrica',
  1532: 'Argelia',
  1533: 'Cabo Verde',
  1548: 'Jordania',
  1567: 'Irak',
  1568: 'Uzbekistán',
  1569: 'Catar',
  2380: 'Paraguay',
  2382: 'Ecuador',
  2384: 'Estados Unidos',
  2386: 'Haití',
  4673: 'Nueva Zelanda',
  5529: 'Canadá',
  5530: 'Curazao',
}

export function worldCupTeamName(team: WcTeam): string {
  if (team.external_id == null) return team.name
  return WORLD_CUP_TEAM_NAMES_ES[team.external_id] ?? team.name
}

const WORLD_CUP_IDENTITIES: Record<string, { name: string; code: string }> = {
  argentina: { name: 'Argentina', code: 'AR' },
  australia: { name: 'Australia', code: 'AU' },
  austria: { name: 'Austria', code: 'AT' },
  belgium: { name: 'Bélgica', code: 'BE' },
  brazil: { name: 'Brasil', code: 'BR' },
  canada: { name: 'Canadá', code: 'CA' },
  colombia: { name: 'Colombia', code: 'CO' },
  croatia: { name: 'Croacia', code: 'HR' },
  czechia: { name: 'Chequia', code: 'CZ' },
  ecuador: { name: 'Ecuador', code: 'EC' },
  egypt: { name: 'Egipto', code: 'EG' },
  england: { name: 'Inglaterra', code: 'GB' },
  france: { name: 'Francia', code: 'FR' },
  germany: { name: 'Alemania', code: 'DE' },
  ghana: { name: 'Ghana', code: 'GH' },
  haiti: { name: 'Haití', code: 'HT' },
  iran: { name: 'Irán', code: 'IR' },
  japan: { name: 'Japón', code: 'JP' },
  jordan: { name: 'Jordania', code: 'JO' },
  mexico: { name: 'México', code: 'MX' },
  morocco: { name: 'Marruecos', code: 'MA' },
  netherlands: { name: 'Países Bajos', code: 'NL' },
  norway: { name: 'Noruega', code: 'NO' },
  panama: { name: 'Panamá', code: 'PA' },
  paraguay: { name: 'Paraguay', code: 'PY' },
  portugal: { name: 'Portugal', code: 'PT' },
  qatar: { name: 'Catar', code: 'QA' },
  scotland: { name: 'Escocia', code: 'GB' },
  senegal: { name: 'Senegal', code: 'SN' },
  'south korea': { name: 'Corea del Sur', code: 'KR' },
  'korea republic': { name: 'Corea del Sur', code: 'KR' },
  spain: { name: 'España', code: 'ES' },
  switzerland: { name: 'Suiza', code: 'CH' },
  tunisia: { name: 'Túnez', code: 'TN' },
  uruguay: { name: 'Uruguay', code: 'UY' },
  usa: { name: 'Estados Unidos', code: 'US' },
  'united states': { name: 'Estados Unidos', code: 'US' },
  'bosnia & herzegovina': { name: 'Bosnia y Herzegovina', code: 'BA' },
  'bosnia and herzegovina': { name: 'Bosnia y Herzegovina', code: 'BA' },
  bosnia: { name: 'Bosnia y Herzegovina', code: 'BA' },
  curacao: { name: 'Curazao', code: 'CW' },
  curazao: { name: 'Curazao', code: 'CW' },
  'curaçao': { name: 'Curazao', code: 'CW' },
  'ivory coast': { name: 'Costa de Marfil', code: 'CI' },
  'new zealand': { name: 'Nueva Zelanda', code: 'NZ' },
  'nueva zelanda': { name: 'Nueva Zelanda', code: 'NZ' },
  'south africa': { name: 'SudÃ¡frica', code: 'ZA' },
  sudafrica: { name: 'SudÃ¡frica', code: 'ZA' },
  'sudáfrica': { name: 'SudÃ¡frica', code: 'ZA' },
}

function identityKey(teamName: string): string {
  return teamName.trim().toLowerCase()
}

function flagEmoji(code: string): string {
  return [...code.toUpperCase()]
    .map((character) => String.fromCodePoint(127397 + character.charCodeAt(0)))
    .join('')
}

export function worldCupTeamNameFromString(teamName: string): string {
  return WORLD_CUP_IDENTITIES[identityKey(teamName)]?.name ?? teamName
}

export function worldCupTeamFlag(teamName: string): string {
  const identity = WORLD_CUP_IDENTITIES[identityKey(teamName)]
  return identity ? flagEmoji(identity.code) : ''
}

export function worldCupTeamFlagUrl(teamName: string): string | null {
  const identity = WORLD_CUP_IDENTITIES[identityKey(teamName)]
  return identity ? `https://flagcdn.com/w80/${identity.code.toLowerCase()}.png` : null
}
