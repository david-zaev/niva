import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource-variable/inter'
import '@fontsource-variable/host-grotesk'
import '@fontsource-variable/geist-mono'
import '../../brand/niva-theme.css'
import './index.css'
import { I18nProvider } from './i18n/index.jsx'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <I18nProvider>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <App />
      </BrowserRouter>
    </I18nProvider>
  </StrictMode>,
)
