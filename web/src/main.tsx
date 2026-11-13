import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

// The admin dashboard is code-split so it never adds weight to the user-facing studio.
const AdminApp = lazy(() => import('./admin/AdminApp').then((m) => ({ default: m.AdminApp })));
// Simran's WebView page (opened inside the RoxStar app) is code-split too, so the lab studio does not carry it.
const SimranWebViewPage = lazy(() =>
  import('./simran/SimranWebViewPage').then((m) => ({ default: m.SimranWebViewPage })),
);
const path = window.location.pathname.replace(/\/+$/, '');
const isAdminRoute = path.startsWith('/admin');
const isSimranRoute = path === '/simran';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isAdminRoute ? (
      <Suspense fallback={null}>
        <AdminApp />
      </Suspense>
    ) : isSimranRoute ? (
      <Suspense fallback={null}>
        <SimranWebViewPage />
      </Suspense>
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
