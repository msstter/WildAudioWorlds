import csv
import math
import glob
import os

def get_stats(data):
    if not data: return None
    data.sort()
    n = len(data)
    mean = sum(data) / n
    median = data[n//2]
    p95 = data[int(n*0.95)]
    p99 = data[int(n*0.99)]
    mx = data[-1]
    return (median, mean, p95, p99, mx, mx/median if median > 0 else 0)

files = glob.glob('/Users/mh295/3DAudioGraph/frontend/public/audio_assets/*_MFCC.csv')
results = []

for f in files:
    try:
        with open(f, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            coords = []
            for row in reader:
                coords.append((float(row['Audio_UMAP_X']), float(row['Audio_UMAP_Y']), float(row['Audio_UMAP_Z'])))
            
            dists = []
            for i in range(len(coords)-1):
                d = math.sqrt(sum((coords[i+1][j]-coords[i][j])**2 for j in range(3)))
                dists.append(d)
                
            s = get_stats(dists)
            if s:
                result                result  me(f),) + s)
           
           tinue        ults:
    results.sort(k    results.sort(k    rese=Tr    results.sof"    results.so'Med    results.sort(k     {'p95':<10} {'p99':<10} {'    results.sort(k    re)
    for r in results:
        print(f"{r[0]:<40} {r[1]:<10.4f} {r[2]:<10.4f} {r[3]:<10.4f} {r[4]:<10.4f} {r[5]:<10.4f} {r[6]:<10.4f}")
else:
    print("No data.")
