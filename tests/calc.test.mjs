// The report's arithmetic (calc.js), run with `node --test tests/`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

createRequire(import.meta.url)('../skills/seo-tuning/report/calc.js')
const C = globalThis.ReportCalc

const res = (meta, page, ratings = {}) => ({
  scores: { meta: { score: meta, intentFit: 0.7, ratings }, page: { score: page, intentFit: 0.8, ratings } },
})
const kws = [{ term: 'a' }, { term: 'b' }, { term: 'c' }]

test('fidelity is metadata over whole page', () => {
  assert.equal(C.fidelity(res(3, 6)), 0.5)
  assert.equal(C.fidelity(res(3, 0)), null)
  assert.equal(C.fidelity(null), null)
})

test('coverage counts whole-page ratings of 0.5 or more', () => {
  const r = res(3, 6, { a: 0.5, b: 0.49, c: 1 })
  assert.equal(C.covered(r, kws), 2)
  assert.equal(C.ceiling(r, kws), 1.99)
})

test('trial rows read raw results and stored summaries alike', () => {
  const comparison = { scores: { meta: { before: 1, after: 2, delta: 1, verdict: 'up' } } }
  assert.deepEqual(C.trialRows({ result: { comparison } }), [{ metric: 'meta', before: 1, after: 2, delta: 1, verdict: 'up' }])
  assert.deepEqual(C.trialRows({ comparison }), C.trialRows({ result: { comparison } }))
  assert.equal(C.trialError({ result: { error: 'x' } }), 'x')
})

test('live series carries the last live result forward', () => {
  const a = res(1, 2), b = res(3, 4)
  assert.deepEqual(C.liveSeries([{ live: a }, {}, { live: b }, {}]), [a, a, b, b])
})
