import { lazy, Suspense } from 'react';
import '@fontsource-variable/manrope';
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from '@/context/ThemeContext'
import { AuthProvider } from '@/context/AuthContext'
import { ClientRoot } from '@/features/company/ClientRoot'
import { showcaseMode } from '@/api/mode';
import './index.css'

if (showcaseMode) {
  window.addEventListener('vite:preloadError', event => {
    const key = 'showcase-asset-reload';
    const previous = Number(sessionStorage.getItem(key) || 0);
    if (Date.now() - previous < 30_000) return;
    event.preventDefault();
    sessionStorage.setItem(key, String(Date.now()));
    window.location.reload();
  });
}

const PlatformRoot = import.meta.env.MODE === 'showcase' ? null : lazy(() => import('@/features/platform/PlatformRoot').then(module => ({ default: module.PlatformRoot })));
const platformPath = !showcaseMode && /^\/platform(?:\/|$)/.test(window.location.pathname);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        {platformPath && PlatformRoot ? (
          <Suspense fallback={<p role="status">Загружаем панель…</p>}><PlatformRoot /></Suspense>
        ) : <AuthProvider><ClientRoot /></AuthProvider>}
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
