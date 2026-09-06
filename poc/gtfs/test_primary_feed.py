"""Regression checks for the primary-feed switch and rejection paths."""
import datetime as dt
import unittest
from poc.gtfs.pairing import TripIdToDate, check_pairing, pair_or_raise, FeedPairingError
from poc.gtfs.checks import e05
from poc.gtfs.ingest import PRIMARY, COMPARISON
from poc.routing.feed_context import departure_iso, resolve_rules

class PrimaryFeedTests(unittest.TestCase):
    def setUp(self):
        self.window = (dt.date(2026,9,4), dt.date(2026,10,4))
        self.mapping = TripIdToDate(distinct_trip_ids=1, trip_ids={'123'},
                                   min_from_date=self.window[0], max_to_date=self.window[1])

    def test_primary_and_comparison(self):
        self.assertEqual(PRIMARY, 'israel-public-transportation.zip')
        self.assertEqual(COMPARISON, 'Gtfs_10_days.zip')

    def test_normalized_keys(self):
        self.assertEqual(pair_or_raise(['123_040926'],self.mapping,self.window)['verdict'],'ACCEPTED')

    def test_partial_keys_rejected(self):
        with self.assertRaises(FeedPairingError):
            pair_or_raise(['123_040926','456_040926'], self.mapping,self.window)

    def test_missing_and_disjoint_dates_rejected(self):
        for window in ((None,None),(dt.date(2027,1,1),dt.date(2027,2,1))):
            with self.subTest(window=window), self.assertRaises(FeedPairingError):
                pair_or_raise(['123_040926'],self.mapping,window)

    def test_empty_feed_rejected(self):
        with self.assertRaises(FeedPairingError):
            pair_or_raise([], self.mapping, self.window)

    def test_negative_control_alone_cannot_pass_e05(self):
        pair=check_pairing(['bad'],self.mapping,self.window)
        self.assertEqual(e05(pair,None,{'raised':True},{})['result'],'fail')

    def test_timezone_changes_with_season(self):
        self.assertTrue(departure_iso('2026-09-08 13:00').endswith('+03:00'))
        self.assertTrue(departure_iso('2026-11-03 13:00').endswith('+02:00'))

    def test_window_based_resolution(self):
        rules = {'friday': {'weekday':'Friday','time':'15:30'}}
        self.assertEqual(resolve_rules(rules,self.window)['friday'],'2026-09-04 15:30')
        with self.assertRaises(ValueError):
            resolve_rules(rules,(dt.date(2026,9,5),dt.date(2026,9,6)))

    def test_calendar_only_and_exception_dates(self):
        from poc.gtfs.parse import parse_services
        class Zip:
            path = __import__('pathlib').Path('fixture.zip')
            data = {'calendar.txt': [{'service_id':'s','start_date':'20260904','end_date':'20260906',
                    **{d:'1' for d in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')}}]}
            def has(self,name): return name in self.data
            def rows(self,name,stats=None): return iter(self.data[name])
        z = Zip()
        self.assertEqual(len(parse_services(z).services['s'].active_dates),3)
        z.data = {**z.data, 'calendar_dates.txt':[{'service_id':'s','date':'20260904','exception_type':'2'}]}
        self.assertEqual(min(parse_services(z).services['s'].active_dates),dt.date(2026,9,5))

if __name__ == '__main__':
    unittest.main()
