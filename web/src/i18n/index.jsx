import { createContext, useContext, useEffect, useState } from 'react'
import mk from './mk.json'
import en from './en.json'

const dictionaries = { mk, en }
const I18nContext = createContext(null)

function load(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* private mode: setting just isn't remembered */
  }
}

// "a.b.c" → dict.a.b.c, falling back to English, then to the key itself
function lookup(dict, key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), dict)
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => load('niva.lang', 'en'))

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = (next) => {
    setLangState(next)
    save('niva.lang', next)
  }
  // t('app.rot.option', { n: 2 }) gives "Option 2": {name} placeholders are filled from vars
  const t = (key, vars) => {
    const text = lookup(dictionaries[lang], key) ?? lookup(en, key) ?? key
    return vars ? String(text).replace(/\{(\w+)\}/g, (m, k) => String(vars[k] ?? m)) : text
  }

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)
export { load, save }
