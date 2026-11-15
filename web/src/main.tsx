import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

// The admin dashboard is code-split so it never adds weight to the user-facing studio.
const AdminApp = lazy(() => import('./admin/AdminApp').then((m) => ({ default: m.AdminApp })));
// Simran's WebView page (opened inside the RoxStar app)
const SimranWebViewPage = lazy(() =>
  import('./simran/SimranWebViewPage').then((m) => ({ default: m.SimranWebViewPage })),
);
// End-to-end RoxStar mobile user onboarding journey simulator
const RoxStarUserFlowSimulator = lazy(() =>
  import('./workflow/RoxStarUserFlowSimulator').then((m) => ({ default: m.RoxStarUserFlowSimulator })),
);

const path = window.location.pathname.replace(/\/+$/, '');
const isAdminRoute = path.startsWith('/admin');
const isStudioRoute = path === '/studio';
const isSimulatorRoute = path === '/simulator';
const isSimranRoute = path === '' || path === '/simran';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isAdminRoute ? (
      <Suspense fallback={null}>
        <AdminApp />
      </Suspense>
    ) : isSimulatorRoute ? (
      <Suspense fallback={null}>
        <RoxStarUserFlowSimulator />
      </Suspense>
    ) : isStudioRoute ? (
      <App />
    ) : (
      <Suspense fallback={null}>
        <SimranWebViewPage />
      </Suspense>
    )}
  </React.StrictMode>,
);
