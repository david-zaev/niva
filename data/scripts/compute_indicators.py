"""Recompute climate normals and latest partial-year observations from power.csv."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from climate_data import DATA, compute_location


def main():
    for loc in json.loads((DATA / 'locations.json').read_text(encoding='utf-8')):
        out = compute_location(loc)
        print(f"{loc['id']}: observations through {out['current']['end_date']}; "
              f"complete-year comparison {out['periods']['recent']}")


if __name__ == '__main__':
    main()
