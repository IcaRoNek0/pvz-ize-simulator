import unittest
from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator

class PhaseInputTests(unittest.TestCase):
    def test_explicit_phase_timer_round_trip(self):
        s = parse_scenario({'zombies': [
            {'type':'jack_in_the_box','row':3,'col':8,'phase':'jack_running','phase_timer':17,'jack_countdown_frames':3},
            {'type':'yeti','row':2,'col':8,'phase':'yeti_walking','phase_timer':29},
            {'type':'jalapeno_head','row':1,'col':8,'phase':'head_walking','phase_timer':23},
        ]})
        self.assertEqual([(z.phase,z.phase_timer) for z in s.zombies], [('jack_running',17),('yeti_walking',29),('head_walking',23)])

if __name__ == '__main__': unittest.main()
