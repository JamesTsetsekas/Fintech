import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from pathlib import Path
import numpy as np

# Load data
script_dir = Path(__file__).parent
data_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'node_software_counts_grouped.csv'
history_path = script_dir.parent / 'data' / 'bitcoin_csv_data' / 'bitcoin_node_history.csv'

try:
    # Read node software counts
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} software entries from {data_path}")
    
    # Read latest history entry for date/time
    history_df = pd.read_csv(history_path)
    latest_entry = history_df.iloc[-1]
    latest_datetime = pd.to_datetime(latest_entry['datetime'])
    latest_timestamp = latest_entry['timestamp']
    print(f"Latest data from: {latest_datetime}")
except Exception as e:
    print(f"Error loading data: {e}")
    raise

# Estimate block height (approximate: blocks are mined every ~10 minutes)
# Genesis block timestamp: 1231006505 (Jan 3, 2009)
genesis_timestamp = 1231006505
blocks_per_10min = 1
seconds_per_block = 600
estimated_block_height = int((latest_timestamp - genesis_timestamp) / seconds_per_block)

# Filter and prepare data
# Group Core versions
core_data = df[df['software'] == 'Bitcoin Core'].copy()
core_data = core_data.sort_values('total_count', ascending=False)
print(f"Found {len(core_data)} Core versions")

# Group Knots versions
knots_data = df[df['software'] == 'Bitcoin Knots'].copy()
knots_data = knots_data.sort_values('total_count', ascending=False)
print(f"Found {len(knots_data)} Knots versions")
if len(knots_data) > 0:
    print(f"Knots data sample: {knots_data[['software', 'main_version', 'total_count']].head()}")

# Group Other (everything else)
other_data = df[~df['software'].isin(['Bitcoin Core', 'Bitcoin Knots'])].copy()
other_total = other_data['total_count'].sum()

# Calculate totals
core_total = core_data['total_count'].sum()
knots_total = knots_data['total_count'].sum()
total_count = core_total + knots_total + other_total
print(f"Totals - Core: {core_total:,}, Knots: {knots_total:,}, Other: {other_total:,}, Total: {total_count:,}")

# Prepare data for plotting
# Create ordered list: Core versions (descending), then Knots, then Other
plot_data = []

# Add Core versions
for _, row in core_data.iterrows():
    version = row['main_version']
    # Version already includes 'v' prefix, so use it directly
    if version == 'unknown':
        label = 'unknown'
    elif version.startswith('v'):
        label = version
    else:
        label = f"v{version}"
    plot_data.append({
        'label': label,
        'count': row['total_count'],
        'percent': row['percent'],
        'category': 'Core',
        'version': version
    })

# Add Knots versions
for _, row in knots_data.iterrows():
    version = row['main_version']
    # Version already includes 'v' prefix, so use it directly
    if version == 'unknown':
        label = 'unknown'
    elif version.startswith('v'):
        label = version
    else:
        label = f"v{version}"
    plot_data.append({
        'label': label,
        'count': row['total_count'],
        'percent': row['percent'],
        'category': 'Knots',
        'version': version
    })

# Add Other
if other_total > 0:
    plot_data.append({
        'label': 'Other',
        'count': other_total,
        'percent': (other_total / total_count) * 100,
        'category': 'Other',
        'version': 'unknown'
    })

plot_df = pd.DataFrame(plot_data)

# Sort: Core versions by version number (descending), then Knots (descending), then Other
def sort_key(row):
    if row['category'] == 'Core':
        version = row['version']
        if version.startswith('v'):
            try:
                # Handle versions like v30, v29, v0.21, etc.
                version_str = version[1:]
                if '.' in version_str:
                    version_num = float(version_str)
                else:
                    version_num = float(version_str)
                return (0, -version_num)  # Core first, negative for descending
            except:
                return (0, 999)  # Unknown versions at end
        return (0, 999)
    elif row['category'] == 'Knots':
        version = row['version']
        if version.startswith('v'):
            try:
                version_str = version[1:]
                if '.' in version_str:
                    version_num = float(version_str)
                else:
                    version_num = float(version_str)
                return (1, -version_num)  # Knots second, negative for descending
            except:
                return (1, 999)
        return (1, 999)
    else:
        return (2, 0)  # Other last

plot_df['sort_key'] = plot_df.apply(sort_key, axis=1)
plot_df = plot_df.sort_values('sort_key').reset_index(drop=True)

# Don't filter out Core or Knots nodes - show all of them
# Only filter out very tiny segments (< 0.1%) that are Other
plot_df = plot_df[
    (plot_df['category'].isin(['Core', 'Knots'])) |
    (plot_df['count'] / total_count > 0.001)
].copy()
print(f"After filtering: {len(plot_df)} segments to plot")
print(f"Core segments: {len(plot_df[plot_df['category'] == 'Core'])}")
print(f"Knots segments: {len(plot_df[plot_df['category'] == 'Knots'])}")

# Create figure with dark background - wider and less tall
fig = plt.figure(figsize=(20, 6))
plt.style.use('dark_background')
fig.patch.set_facecolor('#1a1a1a')

ax = plt.subplot(111)
ax.set_facecolor('#1a1a1a')

# Define colors
# Core: various shades of orange
core_colors = {
    'v30': '#ff8c00',  # Dark orange
    'v29': '#ffa500',  # Orange
    'v28': '#ffb347',  # Light orange
    'v27': '#ffcc99',  # Lighter orange
    'v26': '#ffd700',  # Gold
    'v25': '#ffaa33',  # Orange-yellow
    'v24': '#ff9933',  # Orange
    'v23': '#ff8800',  # Dark orange
    'v22': '#ff7700',  # Darker orange
}

# Knots: green shades
knots_colors = {
    'v30': '#00ff00',  # Bright green
    'v29': '#32cd32',  # Lime green
    'v28': '#228b22',  # Forest green
    'v27': '#2ecc71',  # Green
    'v26': '#3cb371',  # Medium sea green
    'v25': '#50c878',  # Emerald green
    'v23': '#66ff66',  # Light green
    'v22': '#90ee90',  # Light green
    'v21': '#98fb98',  # Pale green
    'v0.20': '#7cfc00',  # Lawn green
    'v0.15': '#adff2f',  # Green yellow
    'v0.14': '#9acd32',  # Yellow green
    'v0.12': '#6b8e23',  # Olive drab
}

# Other: dark gray
other_color = '#555555'

# Create horizontal bar chart - make it even thinner
y_pos = 0
bar_height = 0.15  # Very thin bar, like the example
current_x = 0

# Store bar segments for legend
legend_elements = []
core_versions_plotted = set()
knots_versions_plotted = set()

# Plot bars
for idx, row in plot_df.iterrows():
    count = row['count']
    label = row['label']
    category = row['category']
    version = row['version']
    
    # Get color
    if category == 'Core':
        color = core_colors.get(version, '#ff8c00')  # Default orange
        if version not in core_versions_plotted:
            legend_elements.append(mpatches.Patch(color=color, label=f'Core {label}'))
            core_versions_plotted.add(version)
    elif category == 'Knots':
        color = knots_colors.get(version, '#32cd32')  # Default green
        if version not in knots_versions_plotted:
            legend_elements.append(mpatches.Patch(color=color, label=f'Knots {label}'))
            knots_versions_plotted.add(version)
    else:
        color = other_color
        if 'Other' not in [e.get_label() for e in legend_elements]:
            legend_elements.append(mpatches.Patch(color=color, label='Other'))
    
    # Draw bar segment
    bar = ax.barh(y_pos, count, height=bar_height, left=current_x, 
                  color=color, edgecolor='white', linewidth=0.5)
    
    # Add text label on bar if large enough
    if count / total_count > 0.01:  # Only label if > 1% of total
        mid_x = current_x + count / 2
        # Format label: version number, count, and percentage (matching image style)
        percent_str = f"{row['percent']:.1f}%"
        # Show version, count, and percentage - compact format
        ax.text(mid_x, y_pos, f"{label}\n{count:,}\n({percent_str})",
                ha='center', va='center', color='white', fontsize=7, fontweight='bold')
    
    current_x += count

# Set y-axis - very tight limits for compact look
ax.set_yticks([y_pos])
ax.set_yticklabels([''])
ax.set_ylim(-0.15, 0.15)

# Set x-axis - remove x-axis label for cleaner look
ax.set_xlim(0, total_count * 1.05)
ax.set_xlabel('', color='lightgray', fontsize=0)  # Remove label for cleaner look
ax.tick_params(axis='x', labelcolor='lightgray', labelsize=9)
ax.grid(True, axis='x', which="major", linestyle='-', alpha=0.1, color='gray')

# Format x-axis with commas
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))

# Add total count prominently at the top
total_text = f"{total_count:,}*"
ax.text(0.5, 0.98, total_text, transform=ax.transAxes,
        ha='center', va='top', fontsize=28, fontweight='bold', color='white')

# Add Core and Knots totals - lower to avoid overlap
core_percent = (core_total / total_count) * 100
knots_percent = (knots_total / total_count) * 100
totals_text = f"Core: {core_total:,} ({core_percent:.1f}%)  |  Knots: {knots_total:,} ({knots_percent:.1f}%)"
ax.text(0.5, 0.89, totals_text, transform=ax.transAxes,
        ha='center', va='top', fontsize=12, fontweight='bold', color='lightgray')

# Add date/time and block height info - more compact, moved down
info_text = f"{latest_datetime.strftime('%B %d, %Y, %H:%M (UTC)')} | Block Height: {estimated_block_height:,}"
ax.text(0.5, 0.85, info_text, transform=ax.transAxes,
        ha='center', va='top', fontsize=10, color='lightgray')

# Add source note
source_text = "Source: https://luke.dashjr.org/programs/bitcoin/files/charts/software.html\n*Total count includes listening nodes and estimated non-listening nodes"
ax.text(0.5, 0.05, source_text, transform=ax.transAxes,
        ha='center', va='bottom', fontsize=10, color='lightgray', style='italic')

# Add title - more compact
ax.set_title('Bitcoin Node Count By Software & Version', 
             fontsize=16, fontweight='bold', color='white', pad=10)

# Add legend (if we have space)
if len(legend_elements) <= 15:  # Only show if not too many items
    ax.legend(handles=legend_elements, loc='upper right', 
              framealpha=0.9, facecolor='#2a2a2a', edgecolor='gray',
              fontsize=9, ncol=2)

# Adjust layout
plt.tight_layout()

# Save the chart
output_path = script_dir / 'node_count.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#1a1a1a',
            pad_inches=0.1, edgecolor='none')
print(f"Node count chart saved to: {output_path}")

plt.close()

