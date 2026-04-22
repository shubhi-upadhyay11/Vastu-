import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 1. Get data from your running API
url = "http://127.0.0.1:5000/optimize"
payload = {
    "room_dimensions": {"width": 15, "height": 12},
    "detected_furniture": [
        {"label": "bed", "w": 6, "h": 6},
        {"label": "wardrobe", "w": 4, "h": 2},
        {"label": "desk", "w": 3, "h": 2}
    ]
}

response = requests.post(url, json=payload)
best_layout = response.json()['optimized_layouts'][0]

# 2. Setup the Plot
fig, ax = plt.subplots(figsize=(8, 6))
ax.set_xlim(0, 15)
ax.set_ylim(0, 12)
ax.set_title(f"Optimized Layout (Vastu: {best_layout['vastu_score']} | CNN: {best_layout['functional_score']})")

# 3. Draw Furniture
colors = {'bed': 'blue', 'wardrobe': 'brown', 'desk': 'green'}

for f in best_layout['furniture_positions']:
    rect = patches.Rectangle(
        (f['x'], f['y']), f['w'], f['h'], 
        linewidth=2, edgecolor='black', facecolor=colors.get(f['label'], 'grey'), alpha=0.6
    )
    ax.add_patch(rect)
    plt.text(f['x']+0.5, f['y']+0.5, f['label'].capitalize(), fontsize=10, weight='bold')

plt.grid(True, linestyle='--', alpha=0.5)
plt.show()
