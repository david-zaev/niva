// Install prompt: Android/PC Chrome fire `beforeinstallprompt` once, early, so catch it at start-up.
let deferred = null
const listeners = new Set()
const notify = () => listeners.forEach((fn) => fn(!!deferred))

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferred = e
    notify()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    notify()
  })
}

export const canInstall = () => !!deferred
export function onInstallable(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
export async function install() {
  if (!deferred) return false
  deferred.prompt()
  const { outcome } = await deferred.userChoice
  deferred = null
  notify()
  return outcome === 'accepted'
}
export const isInstalled = () =>
  window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
export const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
