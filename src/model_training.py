import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb


def prepare_features(df):
    """
    Encode categorical features and prepare final feature matrix
    for XGBoost congestion prediction.

    Returns X (features), y (target), feature_names
    """
    df = df.copy()

    cat_cols = ['weather', 'road_type', 'zone', 'day_of_week']
    le       = LabelEncoder()

    for col in cat_cols:
        df[col] = le.fit_transform(df[col].astype(str))

    feature_cols = [
        'hour', 'vehicle_count', 'avg_speed',
        'weather', 'event', 'road_type',
        'rush_hour', 'is_weekend', 'is_late_night',
        'hour_multiplier', 'zone', 'day_of_week'
    ]

    feature_cols = [f for f in feature_cols if f in df.columns]

    X = df[feature_cols]
    y = df['congestion_score']

    return X, y, feature_cols


def train_xgboost(X, y):
    """Train XGBoost regressor for congestion score prediction."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators    = 200,
        max_depth       = 5,
        learning_rate   = 0.1,
        subsample       = 0.8,
        random_state    = 42,
        eval_metric     = 'rmse',
        early_stopping_rounds = 20,
        verbosity       = 0
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    return model, X_test, y_test


def plot_feature_importance(model, feature_names, city='Riyadh', save=False):
    """
    Plot XGBoost feature importance with business interpretation labels.
    Features are ranked by gain — most predictive at top.
    """
    importance_df = (
        pd.DataFrame({
            'feature'   : feature_names,
            'importance': model.feature_importances_
        })
        .sort_values('importance', ascending=True)
    )

    business_labels = {
        'avg_speed'       : 'Average Speed',
        'vehicle_count'   : 'Vehicle Count',
        'hour'            : 'Hour of Day',
        'hour_multiplier' : 'Hourly Traffic Weight',
        'rush_hour'       : 'Rush Hour Flag',
        'is_late_night'   : 'Late Night Flag',
        'is_weekend'      : 'Weekend Flag',
        'weather'         : 'Weather Condition',
        'road_type'       : 'Road Type',
        'zone'            : 'City Zone',
        'event'           : 'Special Event',
        'day_of_week'     : 'Day of Week'
    }

    importance_df['label'] = importance_df['feature'].map(
        lambda x: business_labels.get(x, x)
    )

    colors = [
        '#C0392B' if v > importance_df['importance'].quantile(0.75)
        else '#2E86C1' if v > importance_df['importance'].quantile(0.25)
        else '#AEB6BF'
        for v in importance_df['importance']
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle(f'What Drives Congestion in {city}?', fontsize=13, fontweight='bold')

    bars = ax.barh(importance_df['label'], importance_df['importance'],
                   color=colors, edgecolor='white', linewidth=0.5)

    ax.set_xlabel('Feature Importance (Gain)')
    ax.set_ylabel('')
    ax.axvline(importance_df['importance'].quantile(0.75),
               color='#C0392B', linestyle='--', linewidth=0.8, alpha=0.5,
               label='High importance threshold')
    ax.legend(fontsize=8)

    for bar, val in zip(bars, importance_df['importance']):
        ax.text(val + 0.001, bar.get_y() + bar.get_height() / 2,
                f'{val:.3f}', va='center', fontsize=8, color='#2C3E50')

    plt.tight_layout()

    if save:
        plt.savefig(f'feature_importance_{city.lower()}.png', dpi=150, bbox_inches='tight')

    plt.show()

    return importance_df


def importance_business_summary(importance_df):
    """Print a plain-language summary of the top driving factors."""
    top3    = importance_df.nlargest(3, 'importance')
    bottom3 = importance_df.nsmallest(3, 'importance')

    print("TOP CONGESTION DRIVERS:")
    for _, row in top3.iterrows():
        print(f"  {row['label']:<30} importance: {row['importance']:.4f}")

    print("\nLEAST PREDICTIVE FEATURES:")
    for _, row in bottom3.iterrows():
        print(f"  {row['label']:<30} importance: {row['importance']:.4f}")


# Usage
X, y, feature_names     = prepare_features(riyadh_df)
model, X_test, y_test   = train_xgboost(X, y)
importance_df           = plot_feature_importance(model, feature_names, city='Riyadh', save=True)
importance_business_summary(importance_df)