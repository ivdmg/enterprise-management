import { lazy, Suspense } from 'react';
import '@fontsource-variable/manrope';
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from '@/context/ThemeContext'
import { AuthProvider } from '@/context/AuthContext'
import { ClientRoot } from '@/features/company/ClientRoot'
import './index.css'

const PlatformRoot = lazy(() => import('@/features/platform/PlatformRoot').then(module => ({ default: module.PlatformRoot })));
const platformPath = /^\/platform(?:\/|$)/.test(window.location.pathname);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        {platformPath ? (
          <Suspense fallback={<p role="status">Загружаем панель…</p>}><PlatformRoot /></Suspense>
        ) : <AuthProvider><ClientRoot /></AuthProvider>}
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
