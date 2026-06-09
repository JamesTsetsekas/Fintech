#!/usr/bin/env python3
"""
Bitcoin Price Prediction using Machine Learning

Uses a Random Forest Classifier to predict whether Bitcoin's price will
increase or decrease the next day based on historical features including:
- Daily percentage changes
- Moving averages (7-day, 21-day, 200-day)
- Price volatility measures

Based on https://github.com/engageintellect/bitcoin-price-predictor
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from datetime import datetime, timedelta
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

# Load data
script_dir = Path(__file__).parent
dataset_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'daily_price.csv'

print(f"Loading data from {dataset_path}")
data = pd.read_csv(dataset_path)

# Convert 'date' to datetime and 'price' to numeric
data['Date'] = pd.to_datetime(data['date'], format='%m/%d/%y')
data['Price'] = pd.to_numeric(data['price'], errors='coerce')
data = data.dropna(subset=['Date', 'Price'])
data = data.sort_values(by='Date').reset_index(drop=True)

# Filter out zero prices (early data)
data = data[data['Price'] > 0].copy()

print(f"Loaded {len(data)} records from {data['Date'].min()} to {data['Date'].max()}")

# --- Feature Engineering ---
print("Engineering features...")

# Calculate daily percentage change
data['Daily_Return'] = data['Price'].pct_change() * 100

# Calculate moving averages
data['MA_7'] = data['Price'].rolling(window=7, min_periods=1).mean()
data['MA_21'] = data['Price'].rolling(window=21, min_periods=1).mean()
data['MA_200'] = data['Price'].rolling(window=200, min_periods=1).mean()

# Calculate volatility (rolling standard deviation of returns)
data['Volatility_7'] = data['Daily_Return'].rolling(window=7, min_periods=1).std()
data['Volatility_21'] = data['Daily_Return'].rolling(window=21, min_periods=1).std()

# Price relative to moving averages
data['Price_to_MA7'] = (data['Price'] / data['MA_7'] - 1) * 100
data['Price_to_MA21'] = (data['Price'] / data['MA_21'] - 1) * 100
data['Price_to_MA200'] = (data['Price'] / data['MA_200'] - 1) * 100

# Create target variable: 1 if price goes up tomorrow, 0 if it goes down
data['Tomorrow_Price'] = data['Price'].shift(-1)
data['Target'] = (data['Tomorrow_Price'] > data['Price']).astype(int)

# Drop rows with NaN values
data_clean = data.dropna().copy()

print(f"Clean dataset: {len(data_clean)} records with features")

# --- Prepare data for modeling ---
# Use only data where we have all features (last ~200 days of data won't have target)
feature_columns = [
    'Daily_Return',
    'MA_7', 'MA_21', 'MA_200',
    'Volatility_7', 'Volatility_21',
    'Price_to_MA7', 'Price_to_MA21', 'Price_to_MA200'
]

X = data_clean[feature_columns]
y = data_clean['Target']

# Split data: use 80% for training, 20% for testing
# Use temporal split (earlier data for training, later data for testing)
split_idx = int(len(X) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]

train_dates = data_clean['Date'][:split_idx]
test_dates = data_clean['Date'][split_idx:]

print(f"Training set: {len(X_train)} records (up to {train_dates.max().strftime('%Y-%m-%d')})")
print(f"Test set: {len(X_test)} records (from {test_dates.min().strftime('%Y-%m-%d')})")

# --- Train Random Forest Model ---
print("\nTraining Random Forest Classifier...")
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)

rf_model.fit(X_train, y_train)

# Make predictions
y_train_pred = rf_model.predict(X_train)
y_test_pred = rf_model.predict(X_test)

# Calculate accuracy
train_accuracy = accuracy_score(y_train, y_train_pred)
test_accuracy = accuracy_score(y_test, y_test_pred)

print(f"\nModel Performance:")
print(f"Training Accuracy: {train_accuracy:.2%}")
print(f"Testing Accuracy: {test_accuracy:.2%}")

# Get feature importance
feature_importance = pd.DataFrame({
    'Feature': feature_columns,
    'Importance': rf_model.feature_importances_
}).sort_values('Importance', ascending=False)

print("\nTop 5 Most Important Features:")
for idx, row in feature_importance.head(5).iterrows():
    print(f"  {row['Feature']}: {row['Importance']:.4f}")

# Add predictions to dataframe for visualization
data_clean['Prediction'] = np.nan
data_clean.loc[data_clean.index[:split_idx], 'Prediction'] = y_train_pred
data_clean.loc[data_clean.index[split_idx:], 'Prediction'] = y_test_pred

# Calculate prediction probabilities for confidence
pred_proba = rf_model.predict_proba(X)
data_clean['Pred_Confidence'] = pred_proba.max(axis=1)

# --- Create Visualization ---
print("\nCreating visualization...")

# Create figure with dark background
fig = plt.figure(figsize=(20, 14))
plt.style.use('dark_background')
fig.patch.set_facecolor('black')

# Create grid for subplots
gs = fig.add_gridspec(4, 2,
                      height_ratios=[0.6, 1.5, 1, 0.8],
                      width_ratios=[1, 1],
                      hspace=0.3, wspace=0.25)

# --- HEADER SECTION ---
ax_header = fig.add_subplot(gs[0, :])
ax_header.set_facecolor('black')
ax_header.axis('off')

current_date = data_clean['Date'].iloc[-1]
current_price = data_clean['Price'].iloc[-1]
date_str = f"{current_date.strftime('%b')} {current_date.day}, {current_date.year}"

# Predict tomorrow
last_features = X.iloc[-1:].values
tomorrow_pred = rf_model.predict(last_features)[0]
tomorrow_proba = rf_model.predict_proba(last_features)[0]
tomorrow_confidence = tomorrow_proba.max()
tomorrow_direction = "UP" if tomorrow_pred == 1 else "DOWN"
tomorrow_color = '#00ff00' if tomorrow_pred == 1 else '#ff4444'

ax_header.text(0.02, 0.7, f'Date: {date_str}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color='white', fontweight='bold')
ax_header.text(0.02, 0.3, f'Current Price: ${current_price:,.2f}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color='white', fontweight='bold')

tomorrow_arrow = "↑" if tomorrow_pred == 1 else "↓"
ax_header.text(0.35, 0.7, f'Tomorrow Prediction: {tomorrow_direction} {tomorrow_arrow}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color=tomorrow_color, fontweight='bold')
ax_header.text(0.35, 0.3, f'Confidence: {tomorrow_confidence:.1%}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color='white', fontweight='bold')

ax_header.text(0.65, 0.7, f'Test Accuracy: {test_accuracy:.1%}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color='#00ffff', fontweight='bold')
ax_header.text(0.65, 0.3, f'Train Accuracy: {train_accuracy:.1%}',
               ha='left', va='top', transform=ax_header.transAxes,
               fontsize=14, color='#888888', fontweight='bold')

ax_header.text(0.5, 0.95, 'Bitcoin Price Prediction (Random Forest ML Model)',
               ha='center', va='top', transform=ax_header.transAxes,
               fontsize=20, fontweight='bold', color='white')

ax_header.text(0.98, 0.5, 'BTC',
               ha='right', va='center', transform=ax_header.transAxes,
               fontsize=24, color='#ff8c00', fontweight='bold')

# --- CHART 1: Price with Moving Averages and Predictions (Full History) ---
ax1 = fig.add_subplot(gs[1, :])
ax1.set_facecolor('black')

# Plot price
ax1.plot(data_clean['Date'], data_clean['Price'],
         color='white', linewidth=1.5, label='Price', zorder=3)

# Plot moving averages
ax1.plot(data_clean['Date'], data_clean['MA_7'],
         color='#FFD700', linewidth=1, label='7-day MA', alpha=0.7, zorder=2)
ax1.plot(data_clean['Date'], data_clean['MA_21'],
         color='#00ffff', linewidth=1, label='21-day MA', alpha=0.7, zorder=2)
ax1.plot(data_clean['Date'], data_clean['MA_200'],
         color='#ff8c00', linewidth=1.5, label='200-day MA', alpha=0.8, zorder=2)

# Add colored background for train/test split
split_date = data_clean['Date'].iloc[split_idx]
ax1.axvspan(data_clean['Date'].min(), split_date, alpha=0.05, color='blue', label='Training Period')
ax1.axvspan(split_date, data_clean['Date'].max(), alpha=0.05, color='green', label='Testing Period')

# Set log scale
ax1.set_yscale('log')
ax1.set_ylabel('Price (USD)', color='white', fontsize=12, fontweight='bold')
ax1.tick_params(axis='y', labelcolor='white', labelsize=10)
ax1.tick_params(axis='x', labelcolor='white', labelsize=9, rotation=45)

# Format Y-axis
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x:,.0f}' if x >= 1000 else f'${x:.2f}'))

# Format X-axis
ax1.xaxis.set_major_locator(mdates.YearLocator(2))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

# Grid
ax1.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)
ax1.grid(True, which="minor", linestyle='--', alpha=0.1, color='white', linewidth=0.5)

# Title
ax1.text(0.5, 0.98, 'Bitcoin Price History with Moving Averages',
         ha='center', va='top', transform=ax1.transAxes,
         fontsize=13, fontweight='bold', color='white')

# Legend
legend1 = ax1.legend(loc='upper left', framealpha=0.7, fontsize=9, ncol=2)
for text in legend1.get_texts():
    text.set_color('white')

for spine in ax1.spines.values():
    spine.set_visible(False)

# --- CHART 2: Recent Predictions (Last 180 Days) ---
ax2 = fig.add_subplot(gs[2, 0])
ax2.set_facecolor('black')

# Get last 180 days
recent_data = data_clean[data_clean['Date'] >= (data_clean['Date'].max() - timedelta(days=180))].copy()

# Plot price
ax2.plot(recent_data['Date'], recent_data['Price'],
         color='white', linewidth=2, label='Price', zorder=3)

# Plot moving averages
ax2.plot(recent_data['Date'], recent_data['MA_7'],
         color='#FFD700', linewidth=1.5, label='7-day MA', alpha=0.7, zorder=2)
ax2.plot(recent_data['Date'], recent_data['MA_21'],
         color='#00ffff', linewidth=1.5, label='21-day MA', alpha=0.7, zorder=2)
ax2.plot(recent_data['Date'], recent_data['MA_200'],
         color='#ff8c00', linewidth=1.5, label='200-day MA', alpha=0.8, zorder=2)

# Mark predictions with colors
up_mask = recent_data['Prediction'] == 1
down_mask = recent_data['Prediction'] == 0

# Plot prediction markers
ax2.scatter(recent_data[up_mask]['Date'], recent_data[up_mask]['Price'],
           color='#00ff00', s=20, alpha=0.3, label='Predicted UP', zorder=4)
ax2.scatter(recent_data[down_mask]['Date'], recent_data[down_mask]['Price'],
           color='#ff4444', s=20, alpha=0.3, label='Predicted DOWN', zorder=4)

ax2.set_ylabel('Price (USD)', color='white', fontsize=11)
ax2.tick_params(axis='y', labelcolor='white', labelsize=9)
ax2.tick_params(axis='x', labelcolor='white', labelsize=9, rotation=45)

# Format Y-axis
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))

# Format X-axis
ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

ax2.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)

ax2.text(0.5, 0.98, 'Recent Predictions (Last 180 Days)',
         ha='center', va='top', transform=ax2.transAxes,
         fontsize=12, fontweight='bold', color='white')

legend2 = ax2.legend(loc='upper left', framealpha=0.7, fontsize=8, ncol=2)
for text in legend2.get_texts():
    text.set_color('white')

for spine in ax2.spines.values():
    spine.set_visible(False)

# --- CHART 3: Feature Importance ---
ax3 = fig.add_subplot(gs[2, 1])
ax3.set_facecolor('black')

# Plot feature importance as horizontal bar chart
colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(feature_importance)))
ax3.barh(range(len(feature_importance)), feature_importance['Importance'],
         color=colors, alpha=0.8)

ax3.set_yticks(range(len(feature_importance)))
ax3.set_yticklabels(feature_importance['Feature'], fontsize=9)
ax3.set_xlabel('Importance', color='white', fontsize=10)
ax3.tick_params(axis='y', labelcolor='white', labelsize=9)
ax3.tick_params(axis='x', labelcolor='white', labelsize=9)

ax3.grid(True, axis='x', linestyle='-', alpha=0.2, color='white', linewidth=0.8)

ax3.text(0.5, 0.98, 'Feature Importance',
         ha='center', va='top', transform=ax3.transAxes,
         fontsize=12, fontweight='bold', color='white')

for spine in ax3.spines.values():
    spine.set_visible(False)

# --- CHART 4: Confusion Matrix ---
ax4 = fig.add_subplot(gs[3, 0])
ax4.set_facecolor('black')

# Calculate confusion matrix for test set
cm = confusion_matrix(y_test, y_test_pred)

# Plot confusion matrix
im = ax4.imshow(cm, interpolation='nearest', cmap='Blues', alpha=0.8)
ax4.figure.colorbar(im, ax=ax4, alpha=0.8)

# Add text annotations
thresh = cm.max() / 2.
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        ax4.text(j, i, format(cm[i, j], 'd'),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black",
                fontsize=14, fontweight='bold')

ax4.set_ylabel('Actual', color='white', fontsize=11)
ax4.set_xlabel('Predicted', color='white', fontsize=11)
ax4.set_xticks([0, 1])
ax4.set_yticks([0, 1])
ax4.set_xticklabels(['DOWN', 'UP'], color='white', fontsize=10)
ax4.set_yticklabels(['DOWN', 'UP'], color='white', fontsize=10)
ax4.tick_params(axis='both', labelcolor='white')

ax4.text(0.5, 1.08, 'Confusion Matrix (Test Set)',
         ha='center', va='top', transform=ax4.transAxes,
         fontsize=12, fontweight='bold', color='white')

# --- CHART 5: Accuracy Over Time ---
ax5 = fig.add_subplot(gs[3, 1])
ax5.set_facecolor('black')

# Calculate rolling accuracy for test set
test_results = data_clean.iloc[split_idx:].copy()
test_results['Correct'] = (test_results['Target'] == test_results['Prediction']).astype(int)
test_results['Rolling_Accuracy'] = test_results['Correct'].rolling(window=30, min_periods=1).mean() * 100

ax5.plot(test_results['Date'], test_results['Rolling_Accuracy'],
         color='#00ffff', linewidth=2, label='30-Day Rolling Accuracy')
ax5.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.5, label='Random Guess (50%)')
ax5.axhline(y=test_accuracy*100, color='#FFD700', linestyle='--', linewidth=1.5,
           alpha=0.7, label=f'Overall Test Accuracy ({test_accuracy:.1%})')

ax5.set_ylabel('Accuracy (%)', color='white', fontsize=11)
ax5.set_ylim(0, 100)
ax5.tick_params(axis='y', labelcolor='white', labelsize=9)
ax5.tick_params(axis='x', labelcolor='white', labelsize=9, rotation=45)

# Format X-axis
ax5.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
ax5.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

ax5.grid(True, which="major", linestyle='-', alpha=0.2, color='white', linewidth=0.8)

ax5.text(0.5, 0.98, 'Prediction Accuracy Over Time (Test Period)',
         ha='center', va='top', transform=ax5.transAxes,
         fontsize=12, fontweight='bold', color='white')

legend5 = ax5.legend(loc='lower left', framealpha=0.7, fontsize=8)
for text in legend5.get_texts():
    text.set_color('white')

for spine in ax5.spines.values():
    spine.set_visible(False)

# Save the chart
output_path = script_dir / 'price_prediction.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black',
            pad_inches=0.2, edgecolor='none')
print(f"\n[OK] Price prediction chart saved to: {output_path}")
print(f"Current Date: {date_str}")
print(f"Current Price: ${current_price:,.2f}")
print(f"Tomorrow Prediction: {tomorrow_direction} (Confidence: {tomorrow_confidence:.1%})")
print(f"Model Test Accuracy: {test_accuracy:.1%}")

plt.close()
