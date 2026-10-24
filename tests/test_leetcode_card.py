import importlib.util
import unittest
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
from unittest.mock import patch
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/leetcode_card.py'

class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(),'LeetCode card generator is missing')
        spec=importlib.util.spec_from_file_location('card',SCRIPT)
        self.card=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.card)

    def test_empty_account_is_an_honest_zero_state(self):
        result=self.card.activity({},date(2026,10,24))
        self.assertEqual(result['current'],0)
        self.assertEqual(result['best'],0)
        self.assertEqual(result['active_days'],0)
        self.assertEqual(result['submissions'],0)

    def test_current_streak_allows_yesterday_and_expires_after_gap(self):
        calendar={'2026-10-20':1,'2026-10-21':3,'2026-10-22':1,'2026-10-23':2}
        self.assertEqual(self.card.activity(calendar,date(2026,10,24))['current'],4)
        self.assertEqual(self.card.activity(calendar,date(2026,10,25))['current'],0)

    def test_best_run_and_active_days_use_the_visible_year_window(self):
        calendar={'2025-01-01':99,'2026-10-20':1,'2026-10-21':3,'2026-10-23':2,'2026-10-25':7}
        result=self.card.activity(calendar,date(2026,10,24))
        self.assertEqual((result['best'],result['active_days'],result['submissions']),(2,3,6))

    def test_unknown_user_is_not_reported_as_zero_solved(self):
        with self.assertRaises(ValueError):
            self.card.normalize({'data':{'matchedUser':None}},'farhanakhtar0x66','2026-10-24T07:00:00+00:00')

    def test_duplicate_calendar_keys_across_year_responses_are_not_added_twice(self):
        payload={'data':{'allQuestionsCount':[{'difficulty':d,'count':n} for d,n in [('All',10),('Easy',3),('Medium',5),('Hard',2)]],
            'matchedUser':{'username':'farhanakhtar0x66','submitStatsGlobal':{'acSubmissionNum':[{'difficulty':d,'count':n} for d,n in [('All',1),('Easy',1),('Medium',0),('Hard',0)]]},'current':{'submissionCalendar':'{"1792800000":2}'},'previous':{'submissionCalendar':'{"1792800000":2}'}}}}
        snapshot=self.card.normalize(payload,'farhanakhtar0x66','2026-10-24T07:00:00+00:00')
        self.assertEqual(sum(snapshot['calendar'].values()),2)

    def test_fetch_preserves_a_long_streak_at_new_year(self):
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                return cls(2027,1,1,12,tzinfo=timezone.utc)
        def calendar(year):
            days={};day=date(year,1,1)
            while day<=date(2027,1,1) and day.year==year:
                if day>=date(2025,1,1):
                    days[str(int(datetime(day.year,day.month,day.day,tzinfo=timezone.utc).timestamp()))]=1
                day+=timedelta(days=1)
            return json.dumps(days)
        def response(year):
            items=[{'difficulty':d,'count':n} for d,n in [('All',1),('Easy',1),('Medium',0),('Hard',0)]]
            return BytesIO(json.dumps({'data':{'allQuestionsCount':items,'matchedUser':{
                'username':'farhanakhtar0x66','submitStatsGlobal':{'acSubmissionNum':items},
                'current':{'submissionCalendar':calendar(year)},
                'previous':{'submissionCalendar':calendar(year-1)}}}}).encode())
        with patch.object(self.card,'datetime',Clock), patch.object(self.card.urllib.request,'urlopen',side_effect=[response(2027),response(2025)]):
            snapshot=self.card.fetch()
        self.assertEqual(self.card.activity(snapshot['calendar'],date(2027,1,1))['current'],731)

if __name__=='__main__':unittest.main()
