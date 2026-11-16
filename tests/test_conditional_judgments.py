import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from conditional_judgments import ranges


class ConditionalJudgmentTests(unittest.TestCase):
    def chart(self):
        keys=('earlyPerfectTag','latePerfectTag','veryEarlyTag','veryLateTag','tooEarlyTag','tooLateTag')
        enable=dict(floor=2,eventType='SetConditionalEvents',perfectTag='NONE',**dict.fromkeys(keys,'death'))
        disable=dict(floor=5,eventType='SetConditionalEvents',perfectTag='NONE',**dict.fromkeys(keys,'NONE'))
        return dict(perfect_only_tag='death',floors=[{}]*9,
                    featured_decorations=[dict(tag='death',hitbox='Kill',relativeTo=p,position=[0,20])
                                          for p in ('RedPlanet','BluePlanet')],
                    featured_actions=[enable,disable,dict(floor=0,eventType='MoveDecorations',
                        eventTag='death',tag='death',duration=0,positionOffset=[None,-20])])

    def test_condition_persists_until_explicit_reset(self):
        self.assertEqual(ranges(self.chart()),[(2,5)])

    def test_disabled_reset_does_not_end_condition(self):
        chart=self.chart();chart['featured_actions'][1]['active']=False
        self.assertEqual(ranges(chart),[(2,9)])

    def test_unrelated_chart_has_no_rule(self):
        chart=self.chart();del chart['perfect_only_tag']
        self.assertEqual(ranges(chart),[])

    def test_nonlethal_or_differently_positioned_effect_is_rejected(self):
        chart=self.chart();chart['featured_decorations'][0]['position']=[5,20]
        with self.assertRaises(AssertionError):ranges(chart)

if __name__=='__main__':unittest.main()
