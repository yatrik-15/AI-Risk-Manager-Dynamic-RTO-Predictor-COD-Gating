"""
enrich_dataset.py
─────────────────
Transforms the generic Kaggle e-commerce returns dataset into an
India-specific COD RTO risk dataset for the Razorpay Buildathon 2026.

Input:  ecommerce_returns_synthetic_data.csv  (10,000 rows)
Output: rto_risk_dataset.csv                  (10,000 rows, India-enriched)

Features injected:
  - Realistic Indian shipping addresses (with vague / short ones for risk)
  - Indian 6-digit pincodes (mapped to real city/state)
  - COD vs Prepaid payment split (COD ~55% — realistic for India)
  - IP addresses with velocity-abuse patterns
  - Device hashes with abuse-ring patterns
  - is_rto target variable with proper risk correlations
  - cart_value in INR (converted from USD-like prices)
"""

import pandas as pd
import numpy as np
import hashlib
import random
import os

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "ecommerce_returns_synthetic_data.csv")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "rto_risk_dataset.csv")

# ═══════════════════════════════════════════════════════════════════════════════
# 1.  INDIAN LOCATION DATA — Real pincodes, cities, states
# ═══════════════════════════════════════════════════════════════════════════════

# Pincode → (City, State, RTO base rate)
# RTO rates calibrated from public Indian e-commerce logistics reports
INDIAN_LOCATIONS = {
    # ── High-risk zones (Tier-3 cities, remote areas) ─────────────
    "110043": ("Vikaspuri, Delhi",       "Delhi",           0.35),
    "110085": ("Burari, Delhi",          "Delhi",           0.30),
    "400601": ("Thane",                  "Maharashtra",     0.25),
    "700156": ("Baruipur, South 24 Pgs", "West Bengal",     0.40),
    "700135": ("Garia, Kolkata",         "West Bengal",     0.35),
    "800020": ("Danapur, Patna",         "Bihar",           0.45),
    "800007": ("Bankipore, Patna",       "Bihar",           0.42),
    "826001": ("Dhanbad",                "Jharkhand",       0.38),
    "781001": ("Guwahati",               "Assam",           0.33),
    "795001": ("Imphal",                 "Manipur",         0.40),
    "796001": ("Aizawl",                 "Mizoram",         0.42),
    "231001": ("Mirzapur",               "Uttar Pradesh",   0.37),
    "273001": ("Gorakhpur",              "Uttar Pradesh",   0.36),
    "274001": ("Deoria",                 "Uttar Pradesh",   0.39),

    # ── Medium-risk zones (Tier-2 cities) ─────────────────────────
    "302001": ("Jaipur",                 "Rajasthan",       0.22),
    "380001": ("Ahmedabad",              "Gujarat",         0.18),
    "440001": ("Nagpur",                 "Maharashtra",     0.20),
    "500001": ("Hyderabad",              "Telangana",       0.15),
    "600001": ("Chennai",                "Tamil Nadu",      0.14),
    "641001": ("Coimbatore",             "Tamil Nadu",      0.16),
    "560001": ("Bangalore",              "Karnataka",       0.12),
    "411001": ("Pune",                   "Maharashtra",     0.14),
    "226001": ("Lucknow",                "Uttar Pradesh",   0.24),
    "452001": ("Indore",                 "Madhya Pradesh",  0.20),

    # ── Low-risk zones (Metro / Tier-1 cities) ────────────────────
    "110001": ("Connaught Place, Delhi",  "Delhi",          0.10),
    "400001": ("Fort, Mumbai",            "Maharashtra",    0.08),
    "560034": ("Koramangala, Bangalore",  "Karnataka",      0.07),
    "500034": ("Jubilee Hills, Hyderabad","Telangana",      0.09),
    "600006": ("Mylapore, Chennai",       "Tamil Nadu",     0.08),
    "411004": ("Koregaon Park, Pune",     "Maharashtra",    0.09),
    "380015": ("SG Highway, Ahmedabad",   "Gujarat",        0.10),
    "122001": ("Gurgaon",                 "Haryana",        0.11),
    "201301": ("Noida",                   "Uttar Pradesh",  0.12),
    "400051": ("Bandra, Mumbai",          "Maharashtra",    0.07),
}

PINCODES = list(INDIAN_LOCATIONS.keys())
HIGH_RISK_PINCODES = [p for p, v in INDIAN_LOCATIONS.items() if v[2] >= 0.30]
MED_RISK_PINCODES  = [p for p, v in INDIAN_LOCATIONS.items() if 0.15 <= v[2] < 0.30]
LOW_RISK_PINCODES  = [p for p, v in INDIAN_LOCATIONS.items() if v[2] < 0.15]

# ═══════════════════════════════════════════════════════════════════════════════
# 2.  ADDRESS TEMPLATES — Realistic Indian addresses with risk variation
# ═══════════════════════════════════════════════════════════════════════════════

# Good addresses (low risk — specific, detailed)
GOOD_ADDRESSES = [
    "Flat {flat}, {floor} Floor, {society} Apartments, Sector {sector}",
    "{house} {street} Street, {area} Colony, Near {landmark}",
    "House No. {house}, {area} Layout, {sector} Block, Behind {landmark}",
    "Plot No. {house}, Pocket {flat}, Sector {sector}, {area} Enclave",
    "B-{flat}/{house}, {society} Tower, {area} Phase {sector}",
    "{house}, {street} Road, {area} Nagar, Opposite {landmark}",
    "Door No. {house}-{flat}, {street} Cross, {area} Extension",
    "Villa {house}, {society} Greens, {area} Layout, Near {landmark}",
    "Apartment {flat}, Block {sector}, {society} Residency, {area} Main Road",
    "{house}/{flat}, {society} Complex, {street} Lane, {area} East",
]

# Vague / short addresses (high risk — incomplete, landmarks only)
VAGUE_ADDRESSES = [
    "Near bus stand",
    "Opp. temple",
    "Behind school",
    "Near market",
    "Beside petrol pump",
    "Near railway stn",
    "Nr hospital",
    "Main road",
    "Village road",
    "Near masjid",
    "Opp park",
    "Behind mall",
    "Nr station",
    "Near chowk",
    "Next to bank",
]

SOCIETIES = [
    "Sunrise", "Green Valley", "Palm Heights", "Lake View", "Royal",
    "Sapphire", "Diamond", "Silver Oak", "Golden", "Crystal",
    "Prestige", "Sobha", "DLF", "Godrej", "Lodha",
]

AREAS = [
    "Gandhi", "Nehru", "Ambedkar", "Rajiv", "Subhash",
    "Patel", "Shastri", "MG", "Tagore", "Ashoka",
    "Vasant", "Janakpuri", "Rohini", "Dwarka", "Malviya",
]

STREETS = [
    "MG", "Church", "Station", "Temple", "Market",
    "School", "Hospital", "Lake", "Park", "Ring",
]

LANDMARKS = [
    "SBI Bank", "HDFC ATM", "City Mall", "District Court",
    "Govt Hospital", "Central School", "Railway Station",
    "Bus Depot", "Police Station", "Post Office",
    "Reliance Fresh", "Big Bazaar", "D-Mart", "Apollo Pharmacy",
]


def generate_good_address():
    """Generate a detailed, specific Indian address (low RTO risk)."""
    template = random.choice(GOOD_ADDRESSES)
    return template.format(
        flat=random.randint(1, 2000),
        floor=random.choice(["Ground", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th"]),
        house=random.randint(1, 500),
        society=random.choice(SOCIETIES),
        sector=random.randint(1, 50),
        area=random.choice(AREAS),
        street=random.choice(STREETS),
        landmark=random.choice(LANDMARKS),
    )


def generate_vague_address():
    """Generate a vague/short Indian address (high RTO risk)."""
    return random.choice(VAGUE_ADDRESSES)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  IP & DEVICE ABUSE PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_ip_pool(n_unique=800):
    """Generate a pool of Indian IP addresses with some repeated (abuse)."""
    ips = []
    for _ in range(n_unique):
        # Common Indian ISP ranges
        prefix = random.choice(["49.36", "103.21", "117.200", "122.176",
                                 "157.49", "182.64", "223.226", "59.88",
                                 "106.51", "175.101", "14.139", "27.63"])
        ip = f"{prefix}.{random.randint(0,255)}.{random.randint(1,254)}"
        ips.append(ip)
    return ips


def generate_device_pool(n_unique=1200):
    """Generate device hashes. Some repeated = device farms."""
    devices = []
    for i in range(n_unique):
        raw = f"device_{i}_{random.randint(1000,9999)}"
        h = hashlib.md5(raw.encode()).hexdigest()[:12]
        devices.append(h)
    return devices


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  MAIN ENRICHMENT PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_dataset():
    print("=" * 60)
    print("  RTO Risk Dataset Enrichment Pipeline")
    print("  Razorpay Buildathon 2026 — Track 02")
    print("=" * 60)

    # ── Load ─────────────────────────────────────────────────────
    print(f"\n[LOAD] Loading: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    n = len(df)
    print(f"   Rows: {n:,}  |  Columns: {df.shape[1]}")

    # ── Generate IP & Device pools ───────────────────────────────
    ip_pool = generate_ip_pool(n_unique=800)
    device_pool = generate_device_pool(n_unique=1200)

    # ── Create output DataFrame ──────────────────────────────────
    out = pd.DataFrame()
    out["order_id"] = df["Order_ID"]
    out["user_id"] = df["User_ID"]
    out["order_date"] = df["Order_Date"]

    # ── Product category (keep original, map to Indian e-comm) ───
    category_map = {
        "Clothing": "Fashion",
        "Electronics": "Electronics",
        "Books": "Books",
        "Home": "Home & Kitchen",
        "Toys": "Toys & Games",
    }
    out["category"] = df["Product_Category"].map(category_map)

    # ── Cart value in INR (original is ~5-500 USD-like range) ────
    # Convert: multiply by ~83 (USD→INR) and add noise
    out["cart_value"] = (df["Product_Price"] * 83 + np.random.uniform(-200, 500, n)).round(0).astype(int)
    out["cart_value"] = out["cart_value"].clip(lower=99)  # min ₹99
    out["order_quantity"] = df["Order_Quantity"]

    # ── Payment method: COD vs Prepaid ───────────────────────────
    # Indian e-commerce: ~55% COD. Returns from original dataset
    # are more likely to be COD orders.
    was_returned = df["Return_Status"] == "Returned"
    payment = []
    for i in range(n):
        if was_returned.iloc[i]:
            # Returned orders → 70% chance they were COD
            payment.append("COD" if random.random() < 0.70 else
                           random.choice(["UPI", "Credit Card", "Debit Card", "Net Banking"]))
        else:
            # Not returned → 45% COD (still common in India)
            payment.append("COD" if random.random() < 0.45 else
                           random.choice(["UPI", "Credit Card", "Debit Card", "Net Banking"]))
    out["payment_method"] = payment

    # ── Assign pincodes with risk-correlated distribution ────────
    pincodes = []
    for i in range(n):
        if was_returned.iloc[i]:
            # Returned → more likely to come from high-risk pincodes
            r = random.random()
            if r < 0.45:
                pincodes.append(random.choice(HIGH_RISK_PINCODES))
            elif r < 0.80:
                pincodes.append(random.choice(MED_RISK_PINCODES))
            else:
                pincodes.append(random.choice(LOW_RISK_PINCODES))
        else:
            # Not returned → more likely from low-risk zones
            r = random.random()
            if r < 0.10:
                pincodes.append(random.choice(HIGH_RISK_PINCODES))
            elif r < 0.40:
                pincodes.append(random.choice(MED_RISK_PINCODES))
            else:
                pincodes.append(random.choice(LOW_RISK_PINCODES))
    out["pincode"] = pincodes
    out["city"] = out["pincode"].map(lambda p: INDIAN_LOCATIONS[p][0])
    out["state"] = out["pincode"].map(lambda p: INDIAN_LOCATIONS[p][1])

    # ── Shipping addresses with risk correlation ─────────────────
    addresses = []
    for i in range(n):
        if was_returned.iloc[i] and random.random() < 0.55:
            # Returned orders → 55% chance of vague address
            addresses.append(generate_vague_address())
        elif was_returned.iloc[i]:
            addresses.append(generate_good_address())
        else:
            # Not returned → only 10% chance of vague address
            if random.random() < 0.10:
                addresses.append(generate_vague_address())
            else:
                addresses.append(generate_good_address())
    out["shipping_address"] = addresses

    # ── Phone numbers (Indian 10-digit) ──────────────────────────
    phone_prefixes = ["98", "97", "96", "95", "94", "93", "91", "90",
                      "89", "88", "87", "86", "85", "84", "83", "82", "81", "80",
                      "79", "78", "77", "76", "75", "74", "73", "72", "71", "70"]
    out["phone"] = [random.choice(phone_prefixes) + str(random.randint(10000000, 99999999))
                    for _ in range(n)]

    # ── IP addresses with velocity/abuse patterns ────────────────
    # Some IPs are shared across many orders (abuse rings)
    abuse_ips = random.sample(ip_pool, 30)  # 30 IPs used heavily
    ips = []
    for i in range(n):
        if was_returned.iloc[i] and random.random() < 0.25:
            # 25% of returned orders come from abuse IPs
            ips.append(random.choice(abuse_ips))
        else:
            ips.append(random.choice(ip_pool))
    out["customer_ip"] = ips

    # ── Device hashes with device-farm patterns ──────────────────
    abuse_devices = random.sample(device_pool, 20)  # 20 devices used heavily
    devices = []
    for i in range(n):
        if was_returned.iloc[i] and random.random() < 0.20:
            # 20% of returned orders come from abuse devices
            devices.append(random.choice(abuse_devices))
        else:
            devices.append(random.choice(device_pool))
    out["device_hash"] = devices

    # ── Velocity features (simulated Redis sliding-window counts) ─
    # Strategy: abuse IPs/devices get high counts; normal get Poisson noise.
    # We simulate the 15-min and 60-min windows separately.
    #
    # ip_velocity_15m  — orders from same IP in last 15 minutes
    # ip_velocity_60m  — orders from same IP in last 60 minutes
    # device_velocity_15m — orders from same device in last 15 minutes
    #
    # This mirrors exactly what VelocityService.get_ip_velocity() / 
    # get_device_velocity() returns from Redis at inference time.

    abuse_ip_set    = set(abuse_ips)
    abuse_dev_set   = set(abuse_devices)

    ip_vel_15m  = []
    ip_vel_60m  = []
    dev_vel_15m = []

    for i in range(n):
        ip     = ips[i]
        device = devices[i]

        # ── IP velocity 15-min window ────────────────────────────
        if ip in abuse_ip_set:
            # Abuse IPs: 4–25 requests, skewed toward higher counts
            # Returned orders cluster heavier (same abuse ring, same session)
            base = random.randint(4, 25) if was_returned.iloc[i] else random.randint(2, 12)
        else:
            # Legitimate IPs: mostly 1, occasional 2-3 (family/shared wifi)
            base = max(1, int(np.random.exponential(0.7)))
        ip_vel_15m.append(base)

        # ── IP velocity 60-min window (always >= 15-min count) ───
        if ip in abuse_ip_set:
            # 60-min count is 2-4x the 15-min count
            multiplier = random.uniform(2.0, 4.5)
            ip_vel_60m.append(int(base * multiplier))
        else:
            # Small drift: 60-min ≈ 15-min + tiny extra
            ip_vel_60m.append(base + max(0, int(np.random.exponential(0.5))))

        # ── Device velocity 15-min window ────────────────────────
        if device in abuse_dev_set:
            dev_base = random.randint(3, 20) if was_returned.iloc[i] else random.randint(2, 10)
        else:
            dev_base = max(1, int(np.random.exponential(0.6)))
        dev_vel_15m.append(dev_base)

    out["ip_velocity_15m"]   = ip_vel_15m
    out["ip_velocity_60m"]   = ip_vel_60m
    out["device_velocity_15m"] = dev_vel_15m

    print(f"\n[FEAT] Velocity feature summary:")
    print(f"  Abuse IP orders  : {sum(1 for ip in ips if ip in abuse_ip_set):,}")
    print(f"  Abuse dev orders : {sum(1 for d in devices if d in abuse_dev_set):,}")
    print(f"  ip_vel_15m  mean : {np.mean(ip_vel_15m):.2f}  (abuse: {np.mean([v for v, ip in zip(ip_vel_15m, ips) if ip in abuse_ip_set]):.2f})")
    print(f"  dev_vel_15m mean : {np.mean(dev_vel_15m):.2f}  (abuse: {np.mean([v for v, d in zip(dev_vel_15m, devices) if d in abuse_dev_set]):.2f})")

    # ── User demographics ────────────────────────────────────────
    out["user_age"] = df["User_Age"]
    out["user_gender"] = df["User_Gender"]

    # ── Discount applied (in %) ──────────────────────────────────
    out["discount_pct"] = df["Discount_Applied"].round(1)

    # ── Shipping method ──────────────────────────────────────────
    shipping_map = {
        "Standard": "Standard (5-7 days)",
        "Express": "Express (2-3 days)",
        "Next-Day": "Next-Day Delivery",
    }
    out["shipping_method"] = df["Shipping_Method"].map(shipping_map)

    # ── TARGET VARIABLE: is_rto ──────────────────────────────────
    # Derived from Return_Status but with realistic Indian RTO logic:
    #   - Original "Returned" → base for RTO
    #   - But we add nuance: some "Returned" were legitimate returns
    #     (not RTO), and some "Not Returned" could be borderline
    is_rto = []
    for i in range(n):
        if was_returned.iloc[i]:
            # 85% of original returns → marked as RTO
            # 15% were legitimate returns (defective, wrong item) → not RTO
            reason = df["Return_Reason"].iloc[i]
            if reason in ["Defective", "Wrong item"] and random.random() < 0.40:
                is_rto.append(0)  # Legitimate return, not RTO
            else:
                is_rto.append(1)
        else:
            # 3% of "not returned" were actually failed deliveries (RTO)
            # that the original dataset didn't capture
            if random.random() < 0.03:
                is_rto.append(1)
            else:
                is_rto.append(0)
    out["is_rto"] = is_rto

    # ── Timestamp with realistic Indian timezone ─────────────────
    # Generate timestamps spread across 2024-2025
    base_dates = pd.to_datetime(df["Order_Date"])
    hours = np.random.choice(range(8, 24), n, p=[
        0.02, 0.03, 0.05, 0.07, 0.08, 0.08, 0.08, 0.08,  # 8-15
        0.08, 0.09, 0.10, 0.08, 0.06, 0.05, 0.03, 0.02    # 16-23
    ])
    minutes = np.random.randint(0, 60, n)
    seconds = np.random.randint(0, 60, n)
    out["timestamp"] = [
        f"{d.strftime('%Y-%m-%d')}T{h:02d}:{m:02d}:{s:02d}+05:30"
        for d, h, m, s in zip(base_dates, hours, minutes, seconds)
    ]

    # ── Reorder columns for cleanliness ──────────────────────────
    column_order = [
        "order_id", "user_id", "timestamp", "category", "cart_value",
        "order_quantity", "payment_method", "shipping_address", "pincode",
        "city", "state", "phone", "customer_ip", "device_hash",
        "user_age", "user_gender", "discount_pct", "shipping_method",
        "ip_velocity_15m", "ip_velocity_60m", "device_velocity_15m",
        "is_rto"
    ]
    out = out[column_order]

    # ── Save ─────────────────────────────────────────────────────
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[DONE] Enriched dataset saved to: {OUTPUT_FILE}")

    # ── Print summary stats ──────────────────────────────────────
    print("\n" + "─" * 60)
    print("  DATASET SUMMARY")
    print("─" * 60)
    print(f"  Total rows:            {len(out):,}")
    print(f"  Columns:               {len(out.columns)}")
    print(f"  Target (is_rto):")
    rto_counts = out["is_rto"].value_counts()
    print(f"    0 (Delivered OK):    {rto_counts.get(0, 0):,}  ({rto_counts.get(0,0)/n*100:.1f}%)")
    print(f"    1 (RTO):             {rto_counts.get(1, 0):,}  ({rto_counts.get(1,0)/n*100:.1f}%)")
    print(f"  Payment method split:")
    for method, count in out["payment_method"].value_counts().items():
        print(f"    {method:20s} {count:,}  ({count/n*100:.1f}%)")
    print(f"  Cart value (INR):      ₹{out['cart_value'].min():,} – ₹{out['cart_value'].max():,}  (mean: ₹{out['cart_value'].mean():,.0f})")
    print(f"  Vague addresses:       {(out['shipping_address'].str.len() < 20).sum():,} ({(out['shipping_address'].str.len() < 20).mean()*100:.1f}%)")

    # ── Risk correlation check ───────────────────────────────────
    print("\n" + "─" * 60)
    print("  RISK CORRELATION SANITY CHECK")
    print("─" * 60)

    cod_rto = out[out["payment_method"] == "COD"]["is_rto"].mean()
    prepaid_rto = out[out["payment_method"] != "COD"]["is_rto"].mean()
    print(f"  RTO rate (COD):        {cod_rto*100:.1f}%")
    print(f"  RTO rate (Prepaid):    {prepaid_rto*100:.1f}%")

    short_addr = out[out["shipping_address"].str.len() < 20]["is_rto"].mean()
    long_addr = out[out["shipping_address"].str.len() >= 20]["is_rto"].mean()
    print(f"  RTO rate (short addr): {short_addr*100:.1f}%")
    print(f"  RTO rate (long addr):  {long_addr*100:.1f}%")

    for risk_label, pin_list in [("High-risk", HIGH_RISK_PINCODES),
                                  ("Med-risk",  MED_RISK_PINCODES),
                                  ("Low-risk",  LOW_RISK_PINCODES)]:
        subset = out[out["pincode"].isin(pin_list)]
        if len(subset) > 0:
            print(f"  RTO rate ({risk_label} pins): {subset['is_rto'].mean()*100:.1f}%  (n={len(subset):,})")

    # ── Abuse pattern stats ──────────────────────────────────────
    ip_counts = out["customer_ip"].value_counts()
    high_vel_ips = ip_counts[ip_counts >= 10]
    print(f"\n  High-velocity IPs (≥10 orders): {len(high_vel_ips)}")
    if len(high_vel_ips) > 0:
        abuse_ip_orders = out[out["customer_ip"].isin(high_vel_ips.index)]
        print(f"    Orders from abuse IPs:   {len(abuse_ip_orders):,}")
        print(f"    RTO rate (abuse IPs):    {abuse_ip_orders['is_rto'].mean()*100:.1f}%")

    dev_counts = out["device_hash"].value_counts()
    high_vel_devs = dev_counts[dev_counts >= 8]
    print(f"  High-velocity devices (≥8 orders): {len(high_vel_devs)}")
    if len(high_vel_devs) > 0:
        abuse_dev_orders = out[out["device_hash"].isin(high_vel_devs.index)]
        print(f"    Orders from abuse devs:  {len(abuse_dev_orders):,}")
        print(f"    RTO rate (abuse devs):   {abuse_dev_orders['is_rto'].mean()*100:.1f}%")

    # -- Velocity vs RTO correlation ------------------------------
    print("\n" + "-" * 60)
    print("  VELOCITY FEATURE CORRELATION")
    print("-" * 60)
    for threshold, label in [(1, "1"), (3, "3"), (5, "5"), (10, "10")]:
        high_vel = out[out["ip_velocity_15m"] > threshold]
        if len(high_vel) > 0:
            print(f"  RTO rate (ip_vel_15m > {label:>2}): {high_vel['is_rto'].mean()*100:.1f}%  (n={len(high_vel):,})")
    for threshold, label in [(1, "1"), (3, "3"), (5, "5")]:
        high_vel = out[out["device_velocity_15m"] > threshold]
        if len(high_vel) > 0:
            print(f"  RTO rate (dev_vel_15m  > {label:>2}): {high_vel['is_rto'].mean()*100:.1f}%  (n={len(high_vel):,})")

    print("\n" + "=" * 60)
    print("  [OK] Dataset ready for CatBoost training!")
    print("=" * 60)


if __name__ == "__main__":
    enrich_dataset()
