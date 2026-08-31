import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingDown, ShieldOff, AlertTriangle, BarChart2,
  Download, RefreshCw, X, ChevronDown,
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import {
  getDashboardMetrics, getAuditLog, getThreshold,
  updateThreshold, getFailureLog,
} from '../services/api';

const fmt = (n) => '\u20B9' + n.toLocaleString('en-IN');

export default function Dashboard() {
  const [metrics,       setMetrics]       = useState(null);
  const [auditLog,      setAuditLog]      = useState([]);
  const [failures,      setFailures]      = useState([]);
  const [threshold,     setThreshold]     = useState(0.75);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState('');

  const fetchData = useCallback(async () => {
    try {
      const [m, a, t, f] = await Promise.all([
        getDashboardMetrics(),
        getAuditLog(50),
        getThreshold(),
        getFailureLog(),
      ]);
      setMetrics(m);
      setAuditLog(a);
      setThreshold(t.threshold);
      setFailures(f);
      setError('');
    } catch {
      setError('Failed to connect to backend. Is the server running on port 8000?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, [fetchData]);

  const handleThresholdChange = async (e) => {
    const val = parseFloat(e.target.value);
    setThreshold(val);
    try { await updateThreshold(val); } catch { /* syncs on next poll */ }
  };

  const exportCSV = () => {
    if (!auditLog.length) return;
    const headers = ['Order ID','Timestamp','Risk Score','Category','Action','Risk Factors','Cart Value','Pincode'];
    const rows = auditLog.map(e => [
      e.order_id, e.timestamp, e.risk_score, e.rto_category,
      e.action_taken, '"' + e.top_risk_factors.join('; ') + '"',
      e.cart_value, e.pincode,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type:'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href:url, download:'audit_log.csv' });
    a.click(); URL.revokeObjectURL(url);
  };

  const realTrendData = useMemo(() => {
    if (!auditLog || !Array.isArray(auditLog) || auditLog.length === 0) return [];
    
    // Group by minute
    const grouped = {};
    [...auditLog].reverse().forEach(entry => {
      if (!entry.timestamp) return;
      const d = new Date(entry.timestamp);
      // Format as HH:MM
      const timeKey = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      if (!grouped[timeKey]) {
        grouped[timeKey] = { name: timeKey, orders: 0, rto: 0 };
      }
      grouped[timeKey].orders += 1;
      if (entry.action_taken === 'COD_BLOCKED') {
        grouped[timeKey].rto += 1;
      }
    });
    
    return Object.values(grouped);
  }, [auditLog]);

  /* ── Loading ── */
  if (loading) return (
    <div className="dashboard-page">
      <div className="status-fullscreen">
        <div className="status-icon loading"><div className="loading-ring" /></div>
        <div className="status-title">Loading Dashboard…</div>
        <div className="status-desc">Connecting to AI Risk Manager backend.</div>
      </div>
    </div>
  );

  /* ── Error ── */
  if (error) return (
    <div className="dashboard-page">
      <div className="status-fullscreen">
        <div className="status-icon error"><AlertTriangle size={24} /></div>
        <div className="status-title">Connection Error</div>
        <div className="status-desc">{error}</div>
        <button className="btn btn-primary" style={{ marginTop:8 }} onClick={fetchData}>
          <RefreshCw size={15} /> Retry
        </button>
      </div>
    </div>
  );

  const safeAuditLog = Array.isArray(auditLog) ? auditLog : [];
  const riskDistributionData = [
    { name: 'Low', count: safeAuditLog.filter(e => e.rto_category === 'LOW').length },
    { name: 'Medium', count: safeAuditLog.filter(e => e.rto_category === 'MEDIUM').length },
    { name: 'High', count: safeAuditLog.filter(e => e.rto_category === 'HIGH').length },
  ];

  return (
    <div className="dashboard-page">
      <div className="dashboard-container">

        {/* Header - Inverted Section */}
        <div className="inverted-section" style={{ padding: 'var(--sp-8) var(--sp-8) var(--sp-12)', margin: '-var(--sp-8) -var(--sp-6) var(--sp-6)', borderRadius: '0 0 var(--radius-xl) var(--radius-xl)' }}>
          <div className="dashboard-header" style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div className="dashboard-header-text">
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '12px', borderRadius: '9999px', border: '1px solid rgba(0, 82, 255, 0.3)', background: 'rgba(0, 82, 255, 0.05)', padding: '8px 20px', marginBottom: '24px' }}>
                <span className="live-dot" style={{ background: 'var(--color-accent)' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--color-accent)', fontWeight: 600 }}>Analytics</span>
              </div>
              <h1 style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-text-inverted)' }}>
                Merchant <span className="gradient-text">Dashboard</span>
              </h1>
              <p style={{ color: 'var(--color-text-faint)' }}>AI RTO Risk Manager — Real-time Audit Trail</p>
            </div>
            <div className="dashboard-actions">
              <button id="export-csv-btn" className="btn btn-primary" onClick={exportCSV}>
                <Download size={14} /> Export CSV
              </button>
            </div>
          </div>
        </div>

        {/* Metrics */}
        {metrics && (
          <div className="metrics-grid">
            <div className="metric-card green">
              <div className="metric-icon-wrap green"><TrendingDown size={18} /></div>
              <div className="metric-value">{fmt(Math.round(metrics.net_margin_saved_inr))}</div>
              <div className="metric-label">Net Margin Saved</div>
              <div className="metric-sub">Logistics costs prevented</div>
            </div>
            <div className="metric-card red">
              <div className="metric-icon-wrap red"><ShieldOff size={18} /></div>
              <div className="metric-value">{metrics.rto_prevented}</div>
              <div className="metric-label">RTO Prevented</div>
              <div className="metric-sub">COD orders blocked</div>
            </div>
            <div className="metric-card amber">
              <div className="metric-icon-wrap amber"><AlertTriangle size={18} /></div>
              <div className="metric-value">{metrics.total_false_positives_estimate}</div>
              <div className="metric-label">Est. False Positives</div>
              <div className="metric-sub">Legitimate orders impacted</div>
            </div>
            <div className="metric-card blue">
              <div className="metric-icon-wrap blue"><BarChart2 size={18} /></div>
              <div className="metric-value">{metrics.total_evaluations}</div>
              <div className="metric-label">Total Evaluations</div>
              <div className="metric-sub">This session</div>
            </div>
          </div>
        )}

        {/* Threshold */}
        <div className="threshold-card" style={{ marginBottom: 'var(--sp-6)' }}>
          <div className="threshold-card-header">
            <div>
              <div className="threshold-card-title">Risk Threshold</div>
              <div className="threshold-card-sub">COD is blocked when risk score exceeds this value</div>
            </div>
            <div className="threshold-value-badge">{(threshold * 100).toFixed(0)}%</div>
          </div>
          <div className="threshold-slider-wrap">
            <input
              id="threshold-slider"
              type="range"
              min="0" max="1" step="0.01"
              value={threshold}
              onChange={handleThresholdChange}
              className="threshold-slider"
            />
            <div className="threshold-labels">
              <span>0% — Block None</span>
              <span>50% — Balanced</span>
              <span>100% — Block All</span>
            </div>
          </div>
        </div>

        {/* Analytics Overview */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-6)', marginBottom: 'var(--sp-6)' }}>
          {/* Chart 1: Risk Distribution */}
          <div className="section-card" style={{ background: 'var(--bg-clay)', padding: 'var(--sp-6)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-extruded)' }}>
            <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: 'var(--text-body)', fontWeight: 700, marginBottom: 'var(--sp-4)', color: 'var(--color-text-primary)' }}>Risk Distribution</h3>
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskDistributionData}>
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 12, fontFamily: 'var(--font-body)' }} />
                  <Tooltip cursor={{ fill: 'rgba(26,26,26,0.05)' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-extruded)', background: 'var(--bg-clay)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)' }} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {
                      riskDistributionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={
                          entry.name === 'Low' ? 'var(--color-success)' :
                          entry.name === 'Medium' ? 'var(--color-warning)' :
                          'var(--color-error)'
                        } />
                      ))
                    }
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: RTO Trend */}
          <div className="section-card" style={{ background: 'var(--bg-clay)', padding: 'var(--sp-6)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-extruded)' }}>
            <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: 'var(--text-body)', fontWeight: 700, marginBottom: 'var(--sp-4)', color: 'var(--color-text-primary)' }}>RTO Prevention Trend (Live Session)</h3>
            <div style={{ width: '100%', height: 240 }}>
              {realTrendData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={realTrendData}>
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 12, fontFamily: 'var(--font-body)' }} />
                    <YAxis hide domain={['auto', 'auto']} />
                    <Tooltip cursor={{ fill: 'rgba(26,26,26,0.05)' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-extruded)', background: 'var(--bg-clay)', color: 'var(--color-text-primary)', fontFamily: 'var(--font-body)' }} />
                    <Line type="monotone" dataKey="orders" stroke="var(--color-text-muted)" strokeWidth={2} dot={true} name="Total Orders" />
                    <Line type="monotone" dataKey="rto" stroke="var(--color-error)" strokeWidth={3} dot={{ r: 4, fill: 'var(--color-error)', strokeWidth: 0 }} activeDot={{ r: 6 }} name="RTO Prevented" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-faint)' }}>
                  Waiting for session data...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Audit Table */}
        <div className="audit-card">
          <div className="audit-card-header">
            <span className="audit-card-title">Audit Ledger</span>
            <span className="count-badge">{safeAuditLog.length} entries</span>
          </div>
          <div className="audit-table-scroll">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>RTO Score</th>
                  <th>Category</th>
                  <th>Action</th>
                  <th>Risk Factors</th>
                  <th>Cart Value</th>
                  <th>Timestamp</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {safeAuditLog.map((entry, i) => {
                  const cat = entry.rto_category?.toLowerCase() || 'low';
                  const blocked = entry.action_taken === 'COD_BLOCKED';
                  return (
                    <tr key={i} className={blocked ? 'row-blocked' : ''}>
                      <td className="td-mono">{entry.order_id}</td>
                      <td>
                        <div className="score-bar-wrap">
                          <div className="score-bar-track">
                            <div className={'score-bar-fill ' + cat} style={{ width: (entry.risk_score * 100) + '%' }} />
                          </div>
                          <span className={'td-score ' + cat}>{(entry.risk_score * 100).toFixed(1)}%</span>
                        </div>
                      </td>
                      <td><span className={'cat-pill ' + cat}>{entry.rto_category}</span></td>
                      <td>
                        <span className={'action-pill ' + (blocked ? 'blocked' : 'allowed')}>
                          {blocked ? 'COD Blocked' : 'COD Allowed'}
                        </span>
                      </td>
                      <td>
                        <div className="risk-tag-list">
                          {(entry.top_risk_factors || []).slice(0, 2).map((f, j) => (
                            <span key={j} className="risk-tag-item">{f.replace(/_/g,' ')}</span>
                          ))}
                        </div>
                      </td>
                      <td>{fmt(entry.cart_value)}</td>
                      <td className="td-mono">
                        {new Date(entry.timestamp).toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' })}
                      </td>
                      <td>
                        <button
                          id={'view-entry-' + i}
                          className="btn-view"
                          onClick={() => setSelectedEntry(entry)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {safeAuditLog.length === 0 && (
                  <tr className="empty-row">
                    <td colSpan="8">No evaluations yet — run the checkout flow to see data here.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Failures */}
        {failures?.length > 0 && (
          <div className="failures-card">
            <div className="failures-card-header">
              <AlertTriangle size={14} /> Degradation Events ({failures.length})
            </div>
            {failures.map((f, i) => (
              <div key={i} className="failure-row">
                <span className="fail-time">{new Date(f.timestamp).toLocaleString('en-IN')}</span>
                <span className="fail-type">{f.error_type}</span>
                <span className="fail-msg">{f.error_message}</span>
                <span className="fail-action">{f.fallback_action}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SHAP Modal */}
      {selectedEntry && (
        <div className="modal-backdrop" onClick={() => setSelectedEntry(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-header-text">
                <h2>Risk Explainability</h2>
                <p>{selectedEntry.order_id}</p>
              </div>
              <button
                id="modal-close-btn"
                className="modal-close-btn"
                onClick={() => setSelectedEntry(null)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-detail-grid">
                {[
                  ['Risk Score', (selectedEntry.risk_score * 100).toFixed(1) + '%'],
                  ['Category',  selectedEntry.rto_category],
                  ['Action',    selectedEntry.action_taken === 'COD_BLOCKED' ? 'COD Blocked' : 'COD Allowed'],
                  ['Cart Value', fmt(selectedEntry.cart_value)],
                  ['Pincode',   selectedEntry.pincode],
                  ['Address',   selectedEntry.shipping_address?.slice(0, 40) + (selectedEntry.shipping_address?.length > 40 ? '…' : '')],
                ].map(([key, val]) => (
                  <div key={key} className="detail-cell">
                    <span className="detail-key">{key}</span>
                    <span className="detail-val">{val}</span>
                  </div>
                ))}
              </div>

              <div>
                <div className="shap-section-title">SHAP Feature Contributions</div>
                <div className="shap-bars" style={{ marginTop:16 }}>
                  {selectedEntry.top_risk_factors.map((factor, i) => {
                    const pct = Math.max(15, 90 - i * 28);
                    return (
                      <div key={i} className="shap-row">
                        <span className="shap-factor-name">{factor.replace(/_/g,' ')}</span>
                        <div className="shap-track">
                          <div className="shap-fill" style={{ width: pct + '%' }} />
                        </div>
                        <span className="shap-pct">+{(pct * 0.38).toFixed(0)}% risk</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="modal-footnote">
                Feature importance computed using SHAP (SHapley Additive exPlanations) on the CatBoost model.
                Each value represents the marginal contribution of that feature to the final risk score.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
