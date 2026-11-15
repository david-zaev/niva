// Draws the app icon (a yellow map pin on black) as PNG files, with no image library.
// Run once: node scripts/make-icons.mjs
import { deflateSync } from 'node:zlib'
import { writeFileSync, mkdirSync } from 'node:fs'

const INK = [20, 20, 20]
const YELLOW = [245, 196, 0]

function crc32(buf) {
  let c, crc = ~0
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    crc = (crc >>> 8) ^ c
  }
  return ~crc >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

// 1 inside the pin, 0 outside. Coordinates are 0..1 with the pin centred.
function inPin(x, y) {
  const cx = 0.5, cy = 0.42, r = 0.2
  const d = Math.hypot(x - cx, y - cy)
  if (d < 0.085) return false // the hole
  if (d < r) return true
  // the point: a triangle from the circle's lower flanks down to the tip
  const tipY = 0.8
  if (y > cy && y < tipY) {
    const half = r * 0.98 * (1 - (y - cy) / (tipY - cy))
    return Math.abs(x - cx) < half
  }
  return false
}

function png(size) {
  const ss = 4 // supersampling for smooth edges
  const raw = Buffer.alloc((size * 3 + 1) * size)
  for (let y = 0; y < size; y++) {
    raw[y * (size * 3 + 1)] = 0
    for (let x = 0; x < size; x++) {
      let hit = 0
      for (let sy = 0; sy < ss; sy++)
        for (let sx = 0; sx < ss; sx++)
          if (inPin((x + (sx + 0.5) / ss) / size, (y + (sy + 0.5) / ss) / size)) hit++
      const a = hit / (ss * ss)
      const o = y * (size * 3 + 1) + 1 + x * 3
      for (let i = 0; i < 3; i++) raw[o + i] = Math.round(INK[i] * (1 - a) + YELLOW[i] * a)
    }
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // RGB
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

mkdirSync('public', { recursive: true })
writeFileSync('public/icon-192.png', png(192))
writeFileSync('public/icon-512.png', png(512))
writeFileSync('public/apple-touch-icon.png', png(180))
writeFileSync(
  'public/icon.svg',
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="#141414"/><path fill="#F5C400" fill-rule="evenodd" d="M50 22c-11 0-20 9-20 20 0 14 20 38 20 38s20-24 20-38c0-11-9-20-20-20Zm0 11.500a8.500 8.500 0 1 0 0 17 8.500 8.500 0 1 0 0-17Z"/></svg>\n`,
)
console.log('icons written to public/')
