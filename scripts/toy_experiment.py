"""Small real CPU experiment on explicitly synthetic data; no model-generated metrics."""
import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(args.seed)
    clean = [math.sin(i * 2 * math.pi / 64) for i in range(128)]
    noisy = [x + rng.gauss(0, 0.25) for x in clean]
    filtered = [statistics.fmean(noisy[max(0, i - 1):min(len(noisy), i + 2)]) for i in range(len(noisy))]
    with (args.output / 'raw.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['x', 'clean', 'noisy', 'filtered'])
        writer.writerows(zip(range(128), clean, noisy, filtered))
    metrics = {'seed': args.seed, 'samples': 128, 'dataset': 'synthetic sine with Gaussian noise sigma=0.25',
               'mse_noisy': statistics.fmean((a-b)**2 for a, b in zip(clean, noisy)),
               'mse_filtered': statistics.fmean((a-b)**2 for a, b in zip(clean, filtered))}
    (args.output / 'metrics.json').write_text(json.dumps(metrics, indent=2), 'utf-8')
    print(json.dumps(metrics))


if __name__ == '__main__':
    main()
