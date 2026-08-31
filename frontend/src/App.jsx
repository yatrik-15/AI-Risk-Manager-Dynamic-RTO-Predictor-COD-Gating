import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Checkout from './pages/Checkout';
import Dashboard from './pages/Dashboard';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        {/* ── Minimalist Modern Navigation ── */}
        <nav className="main-nav">
          <div className="nav-brand">
            <span className="nav-brand-name gradient-text" style={{ fontSize: '1.5rem', fontWeight: 800 }}>ShopIN</span>
          </div>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Checkout
            </NavLink>
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dashboard
            </NavLink>
          </div>
        </nav>

        {/* ── Routes ── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Checkout />} />
            <Route path="/dashboard" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
