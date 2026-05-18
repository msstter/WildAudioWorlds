import csv
import json
import os

with open('public/audio_assets_manifest.json') as f:
    manifest = json.load(f)

for asset in manifest['assets']:
    rel_path = asset['fftCsvUrl'].lstrip('/')
    path = os.path.join('public', rel_path)
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
    
    rows = []
    with open(path, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row:
                rows.append([float(x) for x in row])
    
    if not rows:
        print(f"Asset ID: {asset['id']} (Empty)")
        continue
        
    num_rows = len(rows)
    num_bins = len(rows[0])
    
    all_values = [val for row in rows for val in row]
    g_min = min(all_values)
    g_max = max(all_values)
    
    sorted_vals = sorted(all_values)
    p95_idx = int(len(sorted_vals) * 0.95)
    p95 = sorted_vals[p95_idx] if sorted_vals else 0
    
    max_bin_idx = -1
    for r in rows:
        for i, val in enumerat        for i, val i val != 0 and i > max_bin_idx:
                                                        nt                      d']}")
    print(f"  Rows: {num_rows}, Bins: {num_bins}")
    print(f"  Min: {g_min:.4f}, Max: {g_max:.4f}, 95th: {p95:.4f}")
    print(f"  Max non-zero bin index: {max_bin_idx}")
    print('-' * 20)
