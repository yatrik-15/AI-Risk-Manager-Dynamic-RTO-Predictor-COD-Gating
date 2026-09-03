/**
 * API Service Layer
 * Handles all communication with the FastAPI backend.
 * Implements 150ms timeout with graceful fallback for risk evaluation.
 */

const API_BASE = '/api/v1';

/**
 * Evaluate RTO risk for a checkout request.
 * Implements a strict 150ms timeout.
 */
export async function evaluateRisk(payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 150);

  try {
    const res = await fetch(`${API_BASE}/evaluate-risk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return await res.json();

  } catch (err) {
    clearTimeout(timeout);
    console.warn('[FALLBACK] Risk evaluation failed:', err.message);

    // Log the failure to dashboard asynchronously
    logFailure(err.message).catch(() => {});

    // Allow all payment methods
    return {
      risk_score: 0,
      rto_probability_category: 'UNKNOWN',
      checkout_ui_rules: {
        cod_supported: true,
        discount_incentive_active: false,
        discount_amount_in_paise: 0,
        display_message: null,
      },
      audit_trail: { top_risk_factors: ['ai_degraded'] },
      _fallback: true,
    };
  }
}

/**
 * Evaluate risk WITHOUT the strict 150ms timeout (for demo purposes).
 * In production, use evaluateRisk() with the timeout.
 */
export async function evaluateRiskDemo(payload) {
  try {
    const res = await fetch(`${API_BASE}/evaluate-risk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return await res.json();

  } catch (err) {
    console.warn('[FALLBACK] Risk evaluation failed:', err.message);
    logFailure(err.message).catch(() => {});

    return {
      risk_score: 0,
      rto_probability_category: 'UNKNOWN',
      checkout_ui_rules: {
        cod_supported: true,
        discount_incentive_active: false,
        discount_amount_in_paise: 0,
        display_message: null,
      },
      audit_trail: { top_risk_factors: ['ai_degraded'] },
      _fallback: true,
    };
  }
}

/** Create a Razorpay order */
export async function createOrder(cartValue, discount = 0) {
  const res = await fetch(`${API_BASE}/create-order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cart_value: cartValue, discount_applied: discount }),
  });
  if (!res.ok) throw new Error(`Order creation failed: ${res.status}`);
  return res.json();
}

/** Get dashboard metrics */
export async function getDashboardMetrics() {
  const res = await fetch(`${API_BASE}/dashboard/metrics`);
  if (!res.ok) throw new Error(`Failed to fetch metrics`);
  return res.json();
}

/** Get audit log */
export async function getAuditLog(limit = 50, offset = 0) {
  const res = await fetch(`${API_BASE}/dashboard/audit-log?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Failed to fetch audit log`);
  return res.json();
}

/** Get current threshold */
export async function getThreshold() {
  const res = await fetch(`${API_BASE}/dashboard/threshold`);
  if (!res.ok) throw new Error(`Failed to fetch threshold`);
  return res.json();
}

/** Update risk threshold */
export async function updateThreshold(threshold) {
  const res = await fetch(`${API_BASE}/dashboard/threshold`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ threshold }),
  });
  if (!res.ok) throw new Error(`Failed to update threshold`);
  return res.json();
}

/** Get failure log */
export async function getFailureLog() {
  // Attempt to sync any offline failures before fetching
  await syncOfflineFailures();
  
  const res = await fetch(`${API_BASE}/dashboard/failures`);
  if (!res.ok) throw new Error(`Failed to fetch failures`);
  return res.json();
}

async function syncOfflineFailures() {
  const offlineLogs = JSON.parse(localStorage.getItem('offline_failures') || '[]');
  if (offlineLogs.length === 0) return;

  try {
    for (const payload of offlineLogs) {
      await fetch(`${API_BASE}/dashboard/failures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }
    localStorage.removeItem('offline_failures');
  } catch {
    // Still offline, keep in queue
  }
}

/** Log a frontend failure event to the dashboard */
async function logFailure(message) {
  const payload = {
    error_type: 'FRONTEND_TIMEOUT',
    error_message: message,
    fallback_action: 'COD_ALLOWED_DEFAULT',
  };

  try {
    await fetch(`${API_BASE}/dashboard/failures`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    // Queue offline for later sync
    const offlineLogs = JSON.parse(localStorage.getItem('offline_failures') || '[]');
    offlineLogs.push(payload);
    localStorage.setItem('offline_failures', JSON.stringify(offlineLogs));
  }
}
