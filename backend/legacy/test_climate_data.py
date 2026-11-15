"""Regression checks for publication delays and partial-year comparisons."""
import csv
import json
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import climate_data
import jobs


class ClimateDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = pd.DataFrame({'date': pd.date_range('1991-01-01', '2026-01-10')})
        for column, value in {'t_max': 10., 't_min': 0., 'rain_mm': 1., 'humidity': 70.,
                              'solar': 10., 'wind': 2., 'et0': 2.}.items():
            cls.frame[column] = value
        current = cls.frame.date.dt.year == 2026
        cls.frame.loc[current, ['t_max', 't_min']] += 4
        cls.frame.loc[current, 'rain_mm'] = 2
        cls.frame.loc[cls.frame.date > '2026-01-08', ['solar', 'et0']] = float('nan')
        cls.meta = {'first_date': '1991-01-01', 'last_date': '2026-01-10',
                    'source_url': 'https://power.larc.nasa.gov/', 'downloaded_at': '2026-01-13T06:00:00Z'}
        cls.loc = dict(id='test', name='Test', name_mk='Test', lat=41., lon=22.)

    def test_partial_year_uses_matching_dates_and_keeps_normals(self):
        result = climate_data.compute(self.frame, self.meta, self.loc)
        current = result['current']
        self.assertEqual(current['year'], 2026)
        self.assertTrue(current['partial'])
        self.assertEqual(current['rain_mm'], 20.)
        self.assertEqual(current['rain_change_pct'], 100.)
        self.assertEqual(current['t_mean_change_c'], 4.)
        self.assertEqual(result['periods']['recent'], '2016-2025')
        self.assertEqual(result['yearly'][-1]['year'], 2025)
        self.assertEqual(current['dates']['rain_mm'], '2026-01-10')
        self.assertEqual(current['dates']['solar'], '2026-01-08')
        self.assertEqual(current['monthly'][0]['et0_mm'], 16.)
        self.assertIsNone(current['monthly'][0]['balance_mm'])
        self.assertIsNone(current['monthly'][1]['rain_mm'])
        json.dumps(result, allow_nan=False)

    def test_unpublished_rain_is_missing_instead_of_zero(self):
        frame = self.frame.copy()
        frame.loc[frame.date.dt.year == 2026, 'rain_mm'] = float('nan')
        current = climate_data.compute(frame, self.meta, self.loc)['current']
        self.assertIsNone(current['rain_mm'])
        self.assertIsNone(current['dates']['rain_mm'])
        self.assertIsNone(current['rain_change_pct'])

    def test_delayed_updates_preserve_published_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'locations' / 'test'
            folder.mkdir(parents=True)
            (folder / 'power.csv').write_text('date,t_max,t_min,rain_mm,solar,et0\n2026-01-10,14,4,2,,\n', encoding='utf-8')
            (folder / 'power_meta.json').write_text(json.dumps(self.meta), encoding='utf-8')
            updates = {date(2026, 1, 10): {'t_max': None, 't_min': None, 'rain_mm': None, 'solar': 9., 'et0': 1.}}
            with patch.object(jobs.nasa, 'DATA_DIR', root), patch.object(jobs, 'fetch_power', return_value=updates), patch.object(jobs.climate_data, 'compute_location'):
                jobs.refresh_climate(self.loc, date(2026, 1, 13))
            with (folder / 'power.csv').open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['t_max'], '14')
            self.assertEqual(rows[0]['rain_mm'], '2')
            self.assertEqual(rows[0]['solar'], '9.0')


if __name__ == '__main__':
    unittest.main()
