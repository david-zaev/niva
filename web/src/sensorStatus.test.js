import test from 'node:test'
import assert from 'node:assert/strict'
import { sensorStatus } from './sensorStatus.js'

const receivedAt = Date.parse('2026-11-15T12:00:00Z')
const snapshot = (age = 0, simulated = false) => ({
  receivedAt,
  data: { age_s: age, reading: { time: new Date(receivedAt - age * 1000).toISOString(), simulated } },
})

test('disconnect expires the last reading without another API response', () => {
  const saved = snapshot(5)
  assert.deepEqual(sensorStatus(saved, receivedAt + 24000), { age: 29, fresh: true })
  assert.deepEqual(sensorStatus(saved, receivedAt + 25000), { age: 30, fresh: false })
  assert.deepEqual(sensorStatus(saved, receivedAt + 120000), { age: 125, fresh: false })
})

test('API failure removes live status immediately but retains the reading age', () => {
  assert.deepEqual(sensorStatus(snapshot(), receivedAt + 1000, true), { age: 1, fresh: false })
})

test('reconnection with a new reading restores live status', () => {
  assert.equal(sensorStatus(snapshot(), receivedAt + 60000).fresh, false)
  const reconnected = snapshot()
  reconnected.receivedAt += 60000
  reconnected.data.reading.time = new Date(reconnected.receivedAt).toISOString()
  assert.equal(sensorStatus(reconnected, reconnected.receivedAt).fresh, true)
})

test('replayed cached responses cannot reset the age of old readings', () => {
  const cached = snapshot()
  cached.receivedAt += 60000
  assert.deepEqual(sensorStatus(cached, cached.receivedAt), { age: 60, fresh: false })
})

test('simulated and missing readings are never live', () => {
  assert.equal(sensorStatus(snapshot(0, true), receivedAt).fresh, false)
  assert.deepEqual(sensorStatus(null, receivedAt), { age: null, fresh: false })
  assert.deepEqual(sensorStatus({ data: {}, receivedAt }, receivedAt), { age: null, fresh: false })
})

test('unknown age is not live; a valid timestamp can supply the age', () => {
  const unknown = snapshot()
  unknown.data.age_s = null
  unknown.data.reading.time = 'invalid'
  assert.deepEqual(sensorStatus(unknown, receivedAt), { age: null, fresh: false })
  unknown.data.reading.time = new Date(receivedAt - 31000).toISOString()
  assert.deepEqual(sensorStatus(unknown, receivedAt), { age: 31, fresh: false })
})

test('server age prevents a slow client clock from marking stale data live', () => {
  const saved = snapshot(40)
  saved.data.reading.time = new Date(receivedAt + 60000).toISOString()
  assert.deepEqual(sensorStatus(saved, receivedAt), { age: 40, fresh: false })
})
