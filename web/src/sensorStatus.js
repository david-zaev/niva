// The demo firmware sends every 5 seconds; allow six missed readings.
export const SENSOR_STALE_SECONDS = 30

export function sensorStatus(snapshot, now, failed = false) {
  const data = snapshot?.data
  const reading = data?.reading
  if (!reading) return { age: null, fresh: false }
  const elapsed = Math.max(0, (now - snapshot.receivedAt) / 1000)
  const serverAge = Number.isFinite(data.age_s) ? data.age_s + elapsed : null
  const measuredAt = Date.parse(reading.time)
  const timestampAge = Number.isFinite(measuredAt) ? Math.max(0, (now - measuredAt) / 1000) : null
  // Absolute time also protects against an old service worker replaying a cached response.
  const age = serverAge == null ? timestampAge : Math.max(serverAge, timestampAge ?? 0)
  return { age: age == null ? null : Math.floor(age),
    fresh: !failed && !reading.simulated && age != null && age < SENSOR_STALE_SECONDS }
}
