import { useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { queryClient, isAuthenticated } from './api/client';
import { useStore } from './store';
import { useCurrentUser } from './api/hooks';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Chart from './pages/Chart';
import Scanner from './pages/Scanner';
import Alerts from './pages/Alerts';
import Admin from './pages/Admin';
import Hotlist from './pages/Hotlist';
import Login from './pages/Login';

function RequireAuth({ children }: { children: JSX.Element }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return children;
}

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { data: user, isLoading } = useCurrentUser();
  if (isLoading) return null;
  if (!user?.is_superuser) {
    return (
      <div style={{ padding: 40 }}>
        <div
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: 32,
            maxWidth: 480,
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 10, color: 'var(--red)' }}>
            Access Denied
          </div>
          <p style={{ fontSize: 13, color: 'var(--text2)', margin: 0 }}>
            You do not have permission to access the Admin page. Please contact an administrator.
          </p>
        </div>
      </div>
    );
  }
  return children;
}

export default function App() {
  const { darkMode } = useStore();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/chart/:symbol" element={<Chart />} />
            <Route path="/scanner" element={<Scanner />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/hotlist" element={<Hotlist />} />
            <Route path="/admin" element={<RequireAdmin><Admin /></RequireAdmin>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
