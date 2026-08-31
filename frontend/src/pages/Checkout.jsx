import { useState } from 'react';
import { evaluateRiskDemo, createOrder } from '../services/api';

const PRODUCTS = [
  { id: 1, name: 'Premium Wireless Earbuds', price: 2499, category: 'Electronics', img: '/earbuds.jpg' },
  { id: 2, name: 'Cotton Kurta Set', price: 1899, category: 'Fashion', img: '/kurta.jpg' },
  { id: 3, name: 'Smart Watch Pro', price: 4999, category: 'Electronics', img: '/smartwatch.jpg' },
];

export default function Checkout() {
  const [step, setStep] = useState('products');
  const [cart, setCart] = useState([{ ...PRODUCTS[0], qty: 1 }]);
  const [form, setForm] = useState({ name: '', address: '', pincode: '', phone: '', city: '' });
  const [riskResult, setRiskResult] = useState(null);
  const [isFallback, setIsFallback] = useState(false);
  const [error, setError] = useState('');
  const [payTab, setPayTab] = useState('upi');
  const [upiApp, setUpiApp] = useState('');
  const [paying, setPaying] = useState(false);
  const [payDone, setPayDone] = useState(false);
  const [coupon, setCoupon] = useState('');
  const [discount, setDiscount] = useState(0);

  const baseDiscount = discount;
  const upiDiscount = (riskResult?.checkout_ui_rules?.discount_incentive_active && payTab === 'upi')
    ? (riskResult.checkout_ui_rules.discount_amount_in_paise / 100)
    : 0;
  const codFee = (payTab === 'cod') ? 50 : 0;

  const totalDiscount = baseDiscount + upiDiscount;
  const subtotal = cart.reduce((s, c) => s + c.price * c.qty, 0);
  const total = Math.max(0, subtotal - totalDiscount + codFee);

  const toggleProduct = (p) => {
    const exists = cart.find(c => c.id === p.id);
    if (exists) setCart(cart.filter(c => c.id !== p.id));
    else setCart([...cart, { ...p, qty: 1 }]);
  };
  const updateQty = (id, delta) => {
    setCart(cart.map(c => c.id === id ? { ...c, qty: Math.max(1, c.qty + delta) } : c));
  };

  const handleForm = (e) => { setForm({ ...form, [e.target.name]: e.target.value }); setError(''); };

  const validate = () => {
    if (!form.name.trim()) return 'Please enter your name';
    if (!form.address.trim()) return 'Please enter shipping address';
    if (form.address.trim().length < 5) return 'Address is too short';
    if (!/^\d{6}$/.test(form.pincode)) return 'Pincode must be 6 digits';
    if (form.pincode[0] === '0') return 'Invalid Indian pincode';
    if (!/^\d{10}$/.test(form.phone)) return 'Phone must be 10 digits';
    return null;
  };

  const applyCoupon = () => {
    if (coupon.toUpperCase() === 'SAVE10') { setDiscount(Math.round(subtotal * 0.10)); }
    else if (coupon.toUpperCase() === 'FLAT50') { setDiscount(50); }
    else { setDiscount(0); }
  };

  const evaluateRisk = async () => {
    const err = validate();
    if (err) { setError(err); return; }
    setStep('loading');
    const payload = {
      cart_value: subtotal,
      shipping_address: form.address,
      pincode: form.pincode,
      customer_ip: '103.21.' + Math.floor(Math.random()*255) + '.' + Math.floor(Math.random()*255),
      device_hash: 'web_' + Math.random().toString(36).substring(2, 14),
      category: cart[0]?.category || 'Fashion',
      payment_method: 'COD',
      order_quantity: cart.reduce((s, c) => s + c.qty, 0),
    };
    const result = await evaluateRiskDemo(payload);
    setRiskResult(result);
    setIsFallback(!!result._fallback);
    setStep('payment');
  };

  const handlePay = async () => {
    setPaying(true);
    try {
      await createOrder(total, discount);
      setPayDone(true);
      setStep('success');
    } catch {
      setStep('payment');
    }
    setPaying(false);
  };

  const resetAll = () => {
    setStep('products');
    setCart([{ ...PRODUCTS[0], qty: 1 }]);
    setForm({ name: '', address: '', pincode: '', phone: '', city: '' });
    setRiskResult(null); setIsFallback(false); setError('');
    setPayTab('upi'); setUpiApp(''); setPaying(false);
    setPayDone(false); setCoupon(''); setDiscount(0);
  };

  const stepIdx = step === 'products' ? 0 : step === 'shipping' ? 1 : step === 'loading' ? 2 : step === 'payment' ? 2 : 3;

  return (
    <div className="checkout-page">
      {/* ── Checkout Header ── */}
      <div style={{ textAlign: 'center', padding: 'var(--sp-6) 0 var(--sp-10)' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '12px', borderRadius: '9999px', border: '1px solid rgba(0, 82, 255, 0.3)', background: 'rgba(0, 82, 255, 0.05)', padding: '8px 20px', marginBottom: '24px' }}>
          <span className="live-dot" style={{ background: 'var(--color-accent)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--color-accent)', fontWeight: 600 }}>Secure Checkout</span>
        </div>
        <h1 style={{ fontFamily: 'var(--font-heading)', fontSize: 'var(--text-h1)', color: 'var(--color-text-primary)' }}>
          Complete Your <span className="gradient-text">Purchase</span>
        </h1>
      </div>

      {/* ── Progress Stepper ── */}
      <div className="stepper-container">
        <div className="stepper-line" />
        <div className="stepper-line-filled" style={{ width: `${(Math.min(stepIdx, 2) / 2) * 100}%` }} />
        {['Cart', 'Shipping', 'Payment'].map((s, i) => {
          const status = i === stepIdx || (step === 'loading' && i === 2) ? 'current' : i < stepIdx ? 'completed' : 'upcoming';
          return (
            <div key={s} className={`stepper-step ${status}`}>
              <div className="stepper-circle">
                {status === 'completed' ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                ) : (
                  i + 1
                )}
              </div>
              <div className="stepper-label">{s}</div>
            </div>
          );
        })}
      </div>

      {step !== 'success' ? (
        <div className="checkout-layout">
          {/* ── Left Column ── */}
          <div className="checkout-main">
            {/* Step 1: Products */}
            {step === 'products' && (
              <div className="section-card">
                <div className="section-card-header">
                  <div className="section-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
                    Select Products
                  </div>
                </div>
                <div className="section-card-body">
                  <div className="product-grid">
                    {PRODUCTS.map(p => {
                      const inCart = cart.find(c => c.id === p.id);
                      return (
                        <div key={p.id} className={`product-card ${inCart ? 'selected' : ''}`} onClick={() => toggleProduct(p)} tabIndex={0}>
                          <img className="product-card-img" src={p.img} alt={p.name} />
                          <div className="product-card-name">{p.name}</div>
                          <div className="product-card-cat">{p.category}</div>
                          <div className="product-card-price">₹{p.price.toLocaleString()}</div>
                          {inCart && (
                            <div className="product-card-qty" onClick={e => e.stopPropagation()}>
                              <button className="qty-btn" onClick={() => updateQty(p.id, -1)}>−</button>
                              <span className="qty-value">{inCart.qty}</span>
                              <button className="qty-btn" onClick={() => updateQty(p.id, 1)}>+</button>
                            </div>
                          )}
                          {inCart && (
                            <div className="selected-check">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <button className="btn btn-primary btn-lg mt-6" onClick={() => cart.length > 0 && setStep('shipping')} disabled={cart.length === 0}>
                    <span className="btn-content">Continue to Shipping</span>
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Shipping */}
            {step === 'shipping' && (
              <div className="section-card">
                <div className="section-card-header">
                  <div className="section-card-title">
                    <div className="icon-well-deep" style={{ width: 36, height: 36 }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    </div>
                    Shipping Details
                  </div>
                </div>
                <div className="section-card-body">
                  <div className="form-grid">
                    <div className="form-field">
                      <label className="form-label">Full Name <span className="required">*</span></label>
                      <input className="form-input" name="name" placeholder="Rahul Sharma" value={form.name} onChange={handleForm} />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Shipping Address <span className="required">*</span></label>
                      <textarea className="form-input form-textarea" name="address" placeholder="Flat 201, 3rd Floor, Sunrise Apartments, Sector 12" value={form.address} onChange={handleForm} rows={3} />
                    </div>
                    <div className="form-row-2">
                      <div className="form-field">
                        <label className="form-label">Pincode <span className="required">*</span></label>
                        <input className="form-input" name="pincode" placeholder="560034" maxLength={6} value={form.pincode} onChange={handleForm} />
                      </div>
                      <div className="form-field">
                        <label className="form-label">Phone <span className="required">*</span></label>
                        <input className="form-input" name="phone" type="tel" placeholder="9876543210" maxLength={10} value={form.phone} onChange={handleForm} />
                      </div>
                    </div>
                    <div className="form-row-2">
                      <div className="form-field">
                        <label className="form-label">City</label>
                        <input className="form-input" name="city" placeholder="Bengaluru" value={form.city} onChange={handleForm} />
                      </div>
                      <div className="form-field">
                        <label className="form-label">State</label>
                        <select className="form-input form-select" name="state" onChange={handleForm} defaultValue="">
                          <option value="" disabled>Select State</option>
                          <option value="KA">Karnataka</option>
                          <option value="MH">Maharashtra</option>
                          <option value="DL">Delhi</option>
                        </select>
                      </div>
                    </div>
                  </div>
                  {error && (
                    <div className="alert-banner alert-error mt-4">
                      <span className="alert-icon error">⚠</span>
                      <div className="alert-content"><div className="alert-title">{error}</div></div>
                    </div>
                  )}
                  <div className="form-actions mt-6">
                    <button className="btn btn-secondary" onClick={() => setStep('products')}>← Back</button>
                    <button className="btn btn-primary" onClick={evaluateRisk}>
                      <span className="btn-content">Continue to Payment</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Loading */}
            {step === 'loading' && (
              <div className="section-card">
                <div className="loading-panel">
                  <div className="loading-ring" />
                  <div className="loading-title">Evaluating Risk…</div>
                  <div className="loading-sub">Our AI is analyzing your order for optimal payment options</div>
                  <div className="skeleton-stack">
                    <div className="skeleton-line w-full" />
                    <div className="skeleton-line w-3-4" />
                    <div className="skeleton-line w-1-2" />
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Payment */}
            {step === 'payment' && riskResult && (
              <div className="section-card">
                <div className="section-card-header">
                  <div className="section-card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
                    Payment
                  </div>
                </div>
                <div className="section-card-body">
                  {/* Fallback notice */}
                  {isFallback && (
                    <div className="fallback-strip">
                      ⚠ AI Risk Manager is temporarily unavailable. All payment methods are shown.
                    </div>
                  )}

                  {/* High Risk Alert */}
                  {riskResult.rto_probability_category === 'HIGH' && (
                    <div className="alert-banner alert-error mb-4">
                      <span className="alert-icon error">🚫</span>
                      <div className="alert-content">
                        <div className="alert-title">{riskResult.checkout_ui_rules.display_message}</div>
                        <div className="alert-tags">
                          {riskResult.audit_trail.top_risk_factors.map((f, i) => (
                            <span key={i} className="risk-chip">{f}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Medium Risk Incentive */}
                  {riskResult.rto_probability_category === 'MEDIUM' && (
                    <div className="alert-banner alert-warning mb-4">
                      <span className="alert-icon warning">💸</span>
                      <div className="alert-content">
                        <div className="alert-title">{riskResult.checkout_ui_rules.display_message}</div>
                      </div>
                    </div>
                  )}

                  {/* Risk Score Row */}
                  <div className="risk-score-row mb-6">
                    <div className="risk-score-label">
                      <div>
                        <div className={`risk-score-num ${riskResult.rto_probability_category.toLowerCase()}`}>
                          {(riskResult.risk_score * 100).toFixed(1)}%
                        </div>
                        <div className="risk-score-sub">RTO Risk</div>
                      </div>
                    </div>
                    <span className={`risk-category-badge ${riskResult.rto_probability_category.toLowerCase()}`}>
                      {riskResult.rto_probability_category}
                    </span>
                  </div>

                  {/* Payment Tab Bar */}
                  <div className="payment-tab-bar mb-4">
                    {[
                      { key: 'upi', label: '📱 UPI' },
                      { key: 'card', label: '💳 Card' },
                      { key: 'netbanking', label: '🏦 Netbanking' },
                      ...(riskResult.checkout_ui_rules.cod_supported ? [{ key: 'cod', label: '💵 COD' }] : [])
                    ].map(t => (
                      <button key={t.key} className={`payment-tab ${payTab === t.key ? 'active' : ''}`}
                        onClick={() => setPayTab(t.key)}>{t.label}</button>
                    ))}
                  </div>

                  {/* UPI Panel */}
                  {payTab === 'upi' && (
                    <div className="payment-panel">
                      <div className="upi-apps">
                        {['GPay', 'PhonePe', 'Paytm', 'BHIM'].map(app => (
                          <button key={app} className={`upi-app-btn ${upiApp === app ? 'selected' : ''}`} onClick={() => setUpiApp(app)}>
                            <div className="upi-app-icon-text">{app[0]}</div>
                            {app}
                          </button>
                        ))}
                      </div>
                      <div className="or-divider">or enter UPI ID</div>
                      <div className="form-field">
                        <input className="form-input" placeholder="yourname@upi" />
                      </div>
                    </div>
                  )}

                  {/* Card Panel */}
                  {payTab === 'card' && (
                    <div className="payment-panel">
                      <div className="card-field-group">
                        <div className="form-field card-number-wrapper">
                          <label className="form-label">Card Number</label>
                          <input className="form-input" placeholder="4111 1111 1111 1111" maxLength={19} />
                        </div>
                        <div className="card-row">
                          <div className="form-field">
                            <label className="form-label">Expiry</label>
                            <input className="form-input" placeholder="MM / YY" maxLength={7} />
                          </div>
                          <div className="form-field">
                            <label className="form-label">CVV</label>
                            <input className="form-input" placeholder="•••" maxLength={4} type="password" />
                          </div>
                        </div>
                        <div className="form-field">
                          <label className="form-label">Cardholder Name</label>
                          <input className="form-input" placeholder="RAHUL SHARMA" />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Netbanking Panel */}
                  {payTab === 'netbanking' && (
                    <div className="payment-panel">
                      <div className="form-field">
                        <label className="form-label">Select your bank</label>
                        <select className="form-input form-select">
                          <option>State Bank of India</option>
                          <option>HDFC Bank</option>
                          <option>ICICI Bank</option>
                          <option>Axis Bank</option>
                          <option>Kotak Mahindra Bank</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* COD Panel */}
                  {payTab === 'cod' && riskResult.checkout_ui_rules.cod_supported && (
                    <div className="payment-panel">
                      <div className="alert-banner alert-info">
                        <span className="alert-icon info">💵</span>
                        <div className="alert-content">
                          <div className="alert-title">Cash on Delivery</div>
                          <div className="alert-desc">Pay ₹{total.toLocaleString()} when the order arrives at your doorstep.</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* COD Blocked */}
                  {!riskResult.checkout_ui_rules.cod_supported && (
                    <div className="payment-option-row disabled-cod mt-4">
                      <div className="payment-option-left">
                        <div className="payment-option-icon">🚫</div>
                        <div>
                          <div className="payment-option-name">Cash on Delivery</div>
                          <div className="payment-option-sub">Unavailable for this address</div>
                        </div>
                      </div>
                      <span className="cod-blocked-label">Blocked</span>
                    </div>
                  )}

                  {/* Pay Button */}
                  <button className={`btn btn-primary pay-now-btn ${paying ? 'loading' : ''}`} onClick={handlePay} disabled={paying || (payTab === 'upi' && !upiApp)}>
                    <span className="btn-hover-layer" />
                    <span className="btn-content" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {paying ? (
                        <><span className="btn-spinner" /> Processing…</>
                      ) : (
                        <>
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                          Pay ₹{total.toLocaleString()}
                          {riskResult.checkout_ui_rules.discount_incentive_active && payTab === 'upi' && (
                            <span style={{fontSize:'0.75rem',opacity:0.8}}> (Save ₹{(riskResult.checkout_ui_rules.discount_amount_in_paise / 100).toFixed(0)})</span>
                          )}
                        </>
                      )}
                    </span>
                  </button>
                  <div className="processing-note">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                    Secured by Razorpay &bull; 256-bit encryption
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── Right Column: Order Summary ── */}
          <aside className="checkout-sidebar">
            <div className="order-sidebar order-sidebar-receipt">
              <div className="order-sidebar-header">Order Summary</div>
              {cart.map(c => (
                <div key={c.id} className="order-sidebar-item">
                  <div className="icon-well-deep" style={{ width: 56, height: 56, padding: 4 }}>
                    <img className="order-sidebar-item-img" src={c.img} alt={c.name} style={{ boxShadow: 'none' }} />
                  </div>
                  <div className="order-sidebar-item-info">
                    <div className="order-sidebar-item-name">{c.name}</div>
                    <div className="order-sidebar-item-meta">{c.category} × {c.qty}</div>
                  </div>
                  <div className="order-sidebar-item-price">₹{(c.price * c.qty).toLocaleString()}</div>
                </div>
              ))}

              {/* Coupon */}
              <div className="coupon-row">
                <input className="coupon-input" placeholder="Coupon code" value={coupon} onChange={e => setCoupon(e.target.value)} />
                <button className="btn-secondary-accent" onClick={applyCoupon} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="btn-content">Apply</span>
                </button>
              </div>

              {/* Breakdown */}
              <div className="order-breakdown">
                <div className="breakdown-row"><span className="label">Subtotal</span><span className="value">₹{subtotal.toLocaleString()}</span></div>
                
                {baseDiscount > 0 && <div className="breakdown-row"><span className="label">Coupon Discount</span><span className="value discount">−₹{baseDiscount.toLocaleString()}</span></div>}
                
                {upiDiscount > 0 && <div className="breakdown-row"><span className="label">UPI Offer</span><span className="value discount">−₹{upiDiscount.toLocaleString()}</span></div>}
                
                {codFee > 0 ? (
                  <div className="breakdown-row"><span className="label">COD Fee</span><span className="value">₹{codFee.toLocaleString()}</span></div>
                ) : (
                  <div className="breakdown-row"><span className="label">Shipping</span><span className="value" style={{color:'var(--color-success)'}}>Free</span></div>
                )}
              </div>
              <div className="breakdown-total">
                <span className="label" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-text-primary)' }}>Total Payable</span>
                <span className="value" style={{ color: 'var(--color-accent)', fontFamily: 'var(--font-heading)' }}>₹{total.toLocaleString()}</span>
              </div>

              {/* Trust */}
              <div className="trust-strip" style={{ background: 'transparent', boxShadow: 'none', borderTop: '1px solid rgba(26,26,26,0.1)' }}>
                <div className="trust-badge" style={{ background: 'transparent', boxShadow: 'none' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                  SECURE CHECKOUT
                </div>
                <div style={{ width: 1, height: 12, background: 'rgba(26,26,26,0.2)' }} />
                <div className="trust-badge" style={{ background: 'transparent', boxShadow: 'none' }}>
                  RAZORPAY VERIFIED
                </div>
              </div>
            </div>
          </aside>
        </div>
      ) : (
        /* ── Success Screen ── */
        <div className="result-screen">
          <div className="result-icon-ring success float-ambient">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <div className="result-title">Payment Successful!</div>
          <div className="result-sub">Your order has been placed. You will receive a confirmation shortly.</div>
          <div className="result-meta">
            <div className="result-meta-row"><span className="key">Amount Paid</span><span className="val">₹{total.toLocaleString()}</span></div>
            <div className="result-meta-row"><span className="key">Method</span><span className="val">{payTab.toUpperCase()}</span></div>
            <div className="result-meta-row"><span className="key">Shipping</span><span className="val">{form.address}</span></div>
            <div className="result-meta-row"><span className="key">Pincode</span><span className="val">{form.pincode}</span></div>
          </div>
          <div className="result-actions">
            <button className="btn btn-secondary w-full" onClick={resetAll}>New Order</button>
            <button className="btn btn-primary w-full" onClick={() => window.location.href = '/dashboard'}>
              <span className="btn-content">View Dashboard</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
