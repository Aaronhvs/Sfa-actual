import assert from 'node:assert/strict'
import test from 'node:test'
import { buildMatchModel, findPlayer, shortName } from '../src/components/tournaments/match/matchModel.ts'

const player = (external_id, name) => ({ external_id, name, number: null, position: 'F', grid: null,
  player_id: null, sfa_points: null })
const raphinha = player(1496, 'Raphinha')

test('resolves the provider full name to Raphinha before partial name matches', () => {
  const candidates = [player(33, 'Raphael Guerreiro'), raphinha]
  assert.equal(findPlayer('Raphael Dias Belloli', candidates), raphinha)
  assert.equal(findPlayer('Rafael Dias Belloli', candidates), raphinha)
  assert.equal(findPlayer('  RAPHAEL   DIAS BELLOLI  ', candidates), raphinha)
})

test('the full-name alias only identifies the known provider player ID', () => {
  assert.equal(findPlayer('Raphael Dias Belloli', [player(999, 'Raphinha')]), null)
  assert.equal(findPlayer(null, [raphinha]), null)
  assert.equal(findPlayer('Kylian Mbappé', [raphinha]), null)
})

test('keeps existing matching for short names and accents', () => {
  const mbappe = player(278, 'Kylian Mbappé')
  const espart = player(568001, 'X. Espart')
  assert.equal(findPlayer('Kylian Mbappe', [raphinha, mbappe]), mbappe)
  assert.equal(findPlayer('Xavi Espart', [espart, raphinha]), espart)
})

test('Clasico goal and substitution both resolve to Raphinha in the lineup', () => {
  const home = { id: 529, external_id: 529, name: 'Barcelona' }
  const away = { id: 541, external_id: 541, name: 'Real Madrid' }
  const event = (minute, event_type, player_name, assist_name = null, team_external_id = 529) => ({
    minute, extra_minute: 0, event_type, player_name, assist_name, team_external_id,
  })
  const model = buildMatchModel({
    fixture: { home_team: home, away_team: away },
    lineups: [
      { team: home, start_xi: [raphinha, player(133609, 'Pedri')], substitutes: [player(7949, 'Gabriel Jesus')] },
      { team: away, start_xi: [player(278, 'Kylian Mbappé')], substitutes: [] },
    ],
    events: [event(41, 'goal', 'Kylian Mbappé', null, 541),
      event(61, 'goal', 'Raphael Dias Belloli', 'Pedri'),
      event(86, 'substitution', 'Raphael Dias Belloli', 'Gabriel Jesus'),
      event(87, 'goal', 'Kylian Mbappé', null, 541)],
  })
  const scorer = model.goals.find(goal => goal.side === 'home').scorer
  assert.equal(scorer.external_id, 1496)
  assert.equal(shortName(scorer.name), 'Raphinha')
  assert.equal(scorer.marks.goals, 1)
  assert.equal(scorer.marks.off, 86)
  assert.equal(model.players.find(p => p.name === 'Pedri').marks.assists, 1)
  assert.equal(model.players.find(p => p.name === 'Gabriel Jesus').marks.on, 86)
  assert.deepEqual(model.goals.map(goal => goal.score), [[0, 1], [1, 1], [1, 2]])
})
