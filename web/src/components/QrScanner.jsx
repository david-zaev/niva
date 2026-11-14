import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/index.jsx'

export const canScan = typeof window !== 'undefined' && 'BarcodeDetector' in window && !!navigator.mediaDevices?.getUserMedia

// Reads the sensor's QR sticker (a /pair?d=…&c=… link) with the phone camera. Phones without BarcodeDetector
// (iPhone) open the same link from their own camera app, or the farmer types the code.
export default function QrScanner({ onCode, onClose }) {
  const { t } = useI18n()
  const video = useRef(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let stream
    let timer
    let stopped = false
    const detector = new window.BarcodeDetector({ formats: ['qr_code'] })
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        if (stopped) return s.getTracks().forEach((tr) => tr.stop())
        stream = s
        video.current.srcObject = s
        return video.current.play()
      })
      .then(() => {
        timer = setInterval(async () => {
          try {
            const [code] = await detector.detect(video.current)
            if (!code) return
            const url = new URL(code.rawValue, location.href)
            const d = url.searchParams.get('d')
            const c = url.searchParams.get('c')
            if (d && c) onCode(d, c)
          } catch { /* not a Niva link: keep looking */ }
        }, 400)
      })
      .catch(() => setError(true))
    return () => {
      stopped = true
      clearInterval(timer)
      stream?.getTracks().forEach((tr) => tr.stop())
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="qr">
      {error ? <p className="muted">{t('more.cameraError')}</p> : <video ref={video} playsInline muted />}
      <button type="button" className="btn btn-ghost" onClick={onClose}>{t('more.cancel')}</button>
    </div>
  )
}
