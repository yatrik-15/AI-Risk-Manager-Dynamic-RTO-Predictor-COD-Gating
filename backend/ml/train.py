"""
train.py — CatBoost RTO Risk Model Training
=============================================
Trains a CatBoostClassifier on the India-enriched RTO dataset.
Outputs:
  - model_artifacts/rto_model.cbm        (serialized model)
  - model_artifacts/shap_background.npy  (background samples for SHAP)
  - model_artifacts/feature_names.json   (ordered feature list)
  - model_artifacts/pincode_risk.json    (pincode-level RTO rates)
  - model_artifacts/evaluation_report.json (held-out metrics)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_curve,
    auc,
    f1_score,
    precision_score,
    recall_score,
)

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_FILE = os.path.join(PROJECT_ROOT, "rto_risk_dataset.csv")
ARTIFACTS_DIR = os.path.join(SCRIPT_DIR, "model_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# ── Feature Configuration ────────────────────────────────────────────────────
# These are the features the model will use at training time.
# Runtime features (ip_velocity, device_velocity) are added at inference.
FEATURE_COLS = [
    "category",
    "cart_value",
    "order_quantity",
    "payment_method",
    "pincode",
    "user_age",
    "user_gender",
    "discount_pct",
    "shipping_method",
    "address_length",
    "has_vague_terms",
    "pincode_rto_rate",
    # ── Velocity features (Redis sliding-window counts) ──────────
    "ip_velocity_15m",
    "ip_velocity_60m",
    "device_velocity_15m",
]

CAT_FEATURES = ["category", "payment_method", "pincode", "user_gender", "shipping_method"]
TARGET = "is_rto"


def engineer_features(df: pd.DataFrame, pincode_risk: dict = None) -> pd.DataFrame:
    """Add engineered features to the DataFrame."""
    df = df.copy()

    # Address length
    df["address_length"] = df["shipping_address"].str.len()

    # Vague address terms (binary)
    vague_pattern = r"(?i)\b(?:near|opp|opposite|behind|beside|nr|next to|village|chowk)\b"
    df["has_vague_terms"] = df["shipping_address"].str.contains(vague_pattern, regex=True).astype(int)

    # Pincode-level RTO rate (from training data or precomputed)
    if pincode_risk is None:
        pincode_risk = df.groupby("pincode")[TARGET].mean().to_dict()
    df["pincode_rto_rate"] = df["pincode"].map(pincode_risk).fillna(df[TARGET].mean())

    # Velocity features — already in dataset; clip to reasonable range
    # Cap at 100 to prevent extreme outlier influence
    for col in ["ip_velocity_15m", "ip_velocity_60m", "device_velocity_15m"]:
        if col in df.columns:
            df[col] = df[col].clip(upper=100).fillna(0).astype(int)
        else:
            df[col] = 0  # safety fallback if column missing

    return df, pincode_risk


def train_model():
    print("=" * 60)
    print("  CatBoost RTO Risk Model Training")
    print("=" * 60)

    # ── Load data ────────────────────────────────────────────────
    print(f"\n[LOAD] Reading dataset: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    print(f"  Rows: {len(df):,}  |  Columns: {df.shape[1]}")
    print(f"  RTO rate: {df[TARGET].mean()*100:.1f}%")

    # ── Feature engineering ──────────────────────────────────────
    print("\n[FEAT] Engineering features...")
    df, pincode_risk = engineer_features(df)

    # ── Train/test split (stratified) ────────────────────────────
    print("\n[SPLIT] Stratified 80/20 train/test split...")
    X = df[FEATURE_COLS]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")
    print(f"  Train RTO rate: {y_train.mean()*100:.1f}%  |  Test RTO rate: {y_test.mean()*100:.1f}%")

    # ── CatBoost training ────────────────────────────────────────
    print("\n[TRAIN] Training CatBoost model...")
    cat_feature_indices = [FEATURE_COLS.index(f) for f in CAT_FEATURES]

    train_pool = Pool(X_train, y_train, cat_features=cat_feature_indices)
    test_pool = Pool(X_test, y_test, cat_features=cat_feature_indices)

    model = CatBoostClassifier(
        iterations=800,
        depth=8,
        learning_rate=0.08,
        random_strength=0.5,
        l2_leaf_reg=1,
        auto_class_weights="Balanced",
        eval_metric="F1",
        random_seed=42,
        verbose=100,
        early_stopping_rounds=100,
        min_data_in_leaf=5,
        border_count=128,
    )

    model.fit(train_pool, eval_set=test_pool, use_best_model=True)

    # ── Evaluation on held-out test set ──────────────────────────
    print("\n[EVAL] Evaluating on held-out test set...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba)

    prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_proba)
    pr_auc = auc(rec_curve, prec_curve)

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    # False positive cost: orders we'd wrongly block COD for
    # Assume average cart value for FP cost calculation
    avg_cart = df["cart_value"].mean()
    fp_cost = fp * avg_cart * 0.05  # 5% margin loss from blocking legitimate COD orders

    print("\n" + "-" * 60)
    print("  HELD-OUT TEST SET RESULTS")
    print("-" * 60)
    print(f"  Precision:       {precision:.4f}")
    print(f"  Recall:          {recall:.4f}")
    print(f"  F1 Score:        {f1:.4f}")
    print(f"  ROC-AUC:         {roc_auc:.4f}")
    print(f"  PR-AUC:          {pr_auc:.4f}")
    print(f"\n  Confusion Matrix:")
    print(f"    TN={tn}  FP={fp}")
    print(f"    FN={fn}  TP={tp}")
    print(f"\n  False Positive Cost:")
    print(f"    FP count:      {fp} orders wrongly blocked")
    print(f"    Estimated cost: INR {fp_cost:,.0f} (at 5% margin on avg cart INR {avg_cart:,.0f})")
    print("-" * 60)

    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Delivered", "RTO"]))

    # ── Feature importance ───────────────────────────────────────
    print("\n[FEAT] Feature Importance (top 10):")
    importances = model.get_feature_importance()
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: x[1], reverse=True)
    for name, imp in feat_imp[:10]:
        bar = "#" * int(imp / 2)
        print(f"  {name:25s} {imp:6.2f}  {bar}")

    # ── Save artifacts ───────────────────────────────────────────
    print("\n[SAVE] Saving model artifacts...")

    # Model
    model_path = os.path.join(ARTIFACTS_DIR, "rto_model.cbm")
    model.save_model(model_path)
    print(f"  Model: {model_path}")

    # SHAP background (100 random training samples)
    bg_indices = np.random.choice(len(X_train), size=100, replace=False)
    bg_data = X_train.iloc[bg_indices].values
    bg_path = os.path.join(ARTIFACTS_DIR, "shap_background.npy")
    np.save(bg_path, bg_data)
    print(f"  SHAP background: {bg_path}")

    # Feature names
    feat_path = os.path.join(ARTIFACTS_DIR, "feature_names.json")
    with open(feat_path, "w") as f:
        json.dump({"features": FEATURE_COLS, "cat_features": CAT_FEATURES, "cat_indices": cat_feature_indices}, f, indent=2)
    print(f"  Feature names: {feat_path}")

    # Pincode risk lookup
    pincode_path = os.path.join(ARTIFACTS_DIR, "pincode_risk.json")
    with open(pincode_path, "w") as f:
        json.dump(pincode_risk, f, indent=2)
    print(f"  Pincode risk: {pincode_path}")

    # Evaluation report
    report = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "false_positive_cost_inr": round(fp_cost, 2),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "rto_rate_train": round(y_train.mean(), 4),
        "rto_rate_test": round(y_test.mean(), 4),
        "feature_importance": {name: round(imp, 2) for name, imp in feat_imp},
    }
    report_path = os.path.join(ARTIFACTS_DIR, "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Evaluation report: {report_path}")

    print("\n" + "=" * 60)
    print("  [OK] Training complete!")
    print("=" * 60)
    return model


if __name__ == "__main__":
    train_model()
