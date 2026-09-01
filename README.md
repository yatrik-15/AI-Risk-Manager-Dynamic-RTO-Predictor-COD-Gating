# ⚡ Core Engineering Highlights

## 1. Non-Blocking Threadpool Offloading
CPU-intensive ML operations (such as CatBoost matrix transformations and SHAP tree-explainer evaluations) can block the standard Python async event loop, reducing API concurrency.
- **Implementation:** Offloaded synchronous ML routines to Starlette threadpools via `starlette.concurrency.run_in_threadpool`.
- **Result:** ML inference latency stays $<15\text{ms}$ while the FastAPI event loop processes concurrent I/O uninterrupted.

## 2. Multi-Vector Adversarial Defenses
Standard models fail against deliberate bot exploitation. This microservice implements two dedicated adversarial defense layers:
- **Temporal Fraud Sentinel (Distributed Proxy Defense):** Scammers bypass IP rate-limiting by routing requests through residential proxies. Our Redis velocity engine tracks rolling request counts across both `ip_address` and the physical destination `pincode` over a 15-minute window (`rate_limit:pincode:{pincode}`).
- **Adversarial Address Padding Defense:** Scammers pad incomplete addresses with repeated characters to bypass simple string-length heuristics (e.g., "near bus stand aaaaaaaaaa"). The engine applies regex checks for repetitive characters (`r'(.)\1{4,}'`) and checks unique token diversity (`len(set(words)) < 3`) before triggering model inference.

## 3. Fault-Tolerant, Fail-Open Architecture (The Graceful Degradation Bar)
Fintech systems must never lose a legitimate checkout due to an internal microservice timeout.
- **Redis Timeout Fallback:** Redis calls are wrapped in non-blocking try-except handlers. If the cache is unreachable, velocity counters silently default to 0, allowing the model to score based on address heuristics.
- **150ms Frontend Circuit Breaker:** If the risk API throws a 500 or network timeout, the checkout frontend automatically fails open, defaults to standard checkout, and asynchronously logs the event to `/api/v1/dashboard/failures`.

## 4. Razorpay-Compliant Dynamic Bounding
To prevent negative cart anomalies or API rejection from Razorpay:
Dynamic UPI incentives are bounded mathematically:
$$\text{Max Discount (paise)} = (\text{cart\_value} - 1) \times 100$$
Guarantees that the final order amount sent to `POST /v1/orders` is always strictly $\ge ₹1.00$.

## 5. Strict Type Safety & Pydantic V2 Validation
- Replaced bare dictionaries with explicit `typing.TypedDict` (`ModelFeatures`) across feature extraction pipelines.
- Strict input validation sanitizes currency symbols, commas, and malformed strings before payload ingestion.

# 📊 Evaluation & Economic Impact Matrix
Evaluated on a held-out test set of 2,000 synthetic Indian D2C transactions:

| Metric | Score | Estimated E-Commerce Baseline* |
| :--- | :--- | :--- |
| ROC-AUC | 0.7619 | ~0.6800 |
| F1-Score | 0.6760 | ~0.5400 |
| Precision | 0.7250 | — |
| Recall | 0.6330 | — |
| P95 Inference | 12.4 ms | 120 ms |
| Test Pass Rate | 14 / 14 | — |

*\*Baseline numbers are estimates based on standard logistic regression benchmarks.*

## Simulated Economic Impact (Synthetic Cost-Matrix)
> **Simulation Assumptions:** This does not represent actual Razorpay merchant economics. Our threshold is tuned against a hypothetical merchant unit economics model:
$$\text{Net Margin Protected} = (\text{True Positives} \times ₹200\text{ Shipping Saved}) - (\text{False Positives} \times ₹400\text{ Margin Lost})$$
- **Simulated Logistics Costs Saved:** $+₹1,24,200$
- **Simulated False-Positive Penalty:** $-₹18,400$
- **Simulated Net Profit Protected:** $+₹1,05,800$

# 🔌 API Specifications

### `POST /api/v1/evaluate-risk`
Evaluates checkout payload, enforces guardrails, and returns dynamic UI rules.

**Request Body (JSON)**
```json
{
  "cart_value": 1499.00,
  "shipping_address": "Flat 402, Sunshine Heights, MG Road, Bengaluru",
  "pincode": "560038",
  "customer_ip": "103.21.124.1",
  "device_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "category": "Electronics",
  "quantity": 1
}
```

**Response Body (200 OK - JSON)**
```json
{
  "risk_score": 0.14,
  "risk_tier": "LOW",
  "checkout_ui_rules": {
    "cod_supported": true,
    "discount_incentive_active": false,
    "discount_amount_paise": 0,
    "display_message": "Standard checkout active."
  },
  "audit_trail": {
    "top_risk_factors": ["address_completeness_high (SHAP: +0.42)", "low_velocity_pincode (SHAP: +0.15)", "critically_short_address (Rule)"]
  }
}
```

# 📂 Repository Structure

```plaintext
├── backend/
│   ├── app/
│   │   ├── config.py            # Environment configurations
│   │   ├── main.py              # FastAPI application entrypoint
│   │   ├── models/
│   │   │   ├── ml_model.py      # CatBoost wrapper & SHAP explainability
│   │   │   └── schemas.py       # Pydantic V2 data schemas
│   │   ├── routes/
│   │   │   ├── dashboard.py     # Metrics, audit ledger & failure logging
│   │   │   ├── orders.py        # Order endpoints
│   │   │   └── risk.py          # /evaluate-risk endpoint
│   │   ├── services/
│   │   │   ├── risk_engine.py   # Core risk evaluation logic
│   │   │   └── velocity.py      # Redis IP + Pincode rolling counters
│   │   └── utils/
│   │       ├── feature_eng.py   # TypedDict feature extraction & regex filters
│   │       └── razorpay_client.py # Razorpay API client & mock fallbacks
│   ├── ml/
│   │   ├── model_artifacts/     # Trained models & feature schemas
│   │   └── train.py             # Model training script
│   ├── tests/
│   │   └── test_api.py          # 14/14 Pytest integration test suite
│   ├── Dockerfile
│   └── requirements.txt         # Locked Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Checkout.jsx     # Buyer checkout with dynamic COD gating
│   │   │   └── Dashboard.jsx    # Merchant audit ledger & SHAP inspection
│   │   ├── services/
│   │   │   └── api.js           # API communication
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── docker-compose.yml           # Docker deployment configuration
├── enrich_dataset.py            # Script to enrich data
└── README.md
```

# 🚀 Quick Start Guide

### 1. Clone & Set Up Python Virtual Environment
```bash
git clone https://github.com/yatrik-15/AI-Risk-Manager-Dynamic-RTO-Predictor-COD-Gating.git
cd AI-Risk-Manager-Dynamic-RTO-Predictor-COD-Gating
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Run the Test Suite
Verify that all 14 integration and adversarial test cases pass:
```bash
python -m pytest backend/tests -v
```

### 3. Run the Evaluation Script
Inspect held-out test metrics and the economic cost matrix:
```bash
python evaluate.py
```

### 4. Launch Backend & Frontend Services

**Start Backend (FastAPI):**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Start Frontend (Vite):**
```bash
cd frontend
npm install
npm run dev
```

Access the Buyer Checkout UI at `http://localhost:5173` and the Merchant Dashboard at `http://localhost:5173/dashboard`.

# 🔮 Alignment with Razorpay Vulcan
This microservice is extensible to act as an Agentic Execution Layer. While running independently at the merchant edge using tabular gradient boosting, its architecture can be extended to ingest sequential foundation-level network embeddings from Razorpay Vulcan, allowing network-wide payment intelligence to directly drive localized, bounded merchant interventions.

# 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
