"""Isolated checks of extended zombie mechanics and documented timings."""
import random
from types import SimpleNamespace
import unittest
from pvz_ize import extended_zombies as ext
from tests.test_ground_special import unit, plant


class Board:
    def __init__(self, plants=(), brains=(), zombies=()):
        self.plants, self.brains, self.zombies = list(plants), list(brains), list(zombies)
        self.events, self.frame, self.rng = [], 0, random.Random(0)

    def emit(self, event, **data):
        self.events.append((event, data))

    def active(self, row=None):
        return [z for z in self.zombies if z.status == 'active' and z.hp > 0 and (row is None or z.row == row)]

    def destroy_plant(self, p, source):
        p.hp = 0
        self.emit('plant_died', plant=p.id, source=source)

    def damage(self, z, amount, source, **kwargs):
        z.hp = max(0, z.hp-amount)
        if not z.hp:
            self.kill(z, source)

    def kill(self, z, source):
        z.hp, z.status = 0, 'dead'

    def spawn_zombie(self, type_, row, x):
        z = unit(type_, id=f'spawn{len(self.zombies)}', row=row, x=x)
        self.zombies.append(z)
        return z

    def resolve_umbrella(self, row, col):
        return next((p for p in self.plants if p.hp > 0 and p.type == 'umbrella_leaf' and abs(p.row-row)<=1 and abs(p.col-col)<=1), None)


def tick(board, zombie, frames):
    for _ in range(frames):
        board.frame += 1
        ext.update(board, zombie)
        ext.update_projectiles(board)


class GiantTests(unittest.TestCase):
    def test_smash_squishes_entire_stack(self):
        p, q = plant(), plant('pumpkin', id='shell')
        b, z = Board([p,q]), unit('gargantuar', hp=3000, x=120)
        ext.update(b,z)
        self.assertEqual(z.phase, 'giant_smashing')
        tick(b,z,133)
        self.assertEqual((p.hp,q.hp), (0,0))

    def test_chill_slows_smash_animation(self):
        p = plant()
        b, z = Board([p]), unit('gargantuar', hp=3000, x=120, chilled=999)
        ext.update(b,z)
        tick(b,z,133)
        self.assertGreater(p.hp,0)
        tick(b,z,133)
        self.assertEqual(p.hp,0)

    def test_throws_only_once_below_half(self):
        b, z = Board(), unit('gargantuar', hp=1499, x=600)
        ext.update(b,z)
        tick(b,z,ext.THROW_FRAMES)
        self.assertEqual(len(b.zombies),1)
        child=b.zombies[0]
        self.assertEqual(child.phase,'imp_thrown')
        self.assertFalse(z.tool)
        self.assertFalse(ext.targetable(child))
        tick(b,child,child.phase_timer+ext.IMP_LAND_FRAMES)
        self.assertEqual(child.phase,'walking')
        self.assertLess(child.x,467)

    def test_full_health_does_not_throw(self):
        b,z=Board(),unit('red_eye_gargantuar',hp=6000,x=600)
        ext.update(b,z)
        self.assertEqual(z.phase,'giant_walking')

    def test_squish_brain(self):
        brain=SimpleNamespace(row=3,hp=70)
        b,z=Board(brains=[brain]),unit('gargantuar',hp=3000,x=-31)
        ext.update(b,z)
        tick(b,z,133)
        self.assertEqual(brain.hp,0)

    def test_spikerock_takes_multiple_smashes(self):
        p=plant('spikerock',hp=450)
        b,z=Board([p]),unit('gargantuar',hp=3000,x=120)
        ext.update(b,z)
        tick(b,z,133)
        self.assertEqual(p.hp,400)
        self.assertEqual(z.hp,2980)


class MachineTests(unittest.TestCase):
    def test_hypnotized_vehicle_does_not_crush_plants(self):
        p = plant()
        b,z=Board([p]),unit('catapult',x=120,hypnotized=True,direction=1)
        ext.update(b,z)
        self.assertEqual(p.hp,4000)
        self.assertGreater(z.x,120)

    def test_basketball_targets_main_before_shell(self):
        p,q=plant(col=1,layer='main'),plant('pumpkin',col=1,id='shell',hp=4000,layer='shell')
        b,z=Board([p,q]),unit('catapult',x=600)
        ext.update(b,z)
        tick(b,z,220)
        self.assertEqual(p.hp,3925)
        self.assertEqual(q.hp,4000)

    def test_catapult_chill_slows_animation(self):
        b,z=Board([plant(col=1)]),unit('catapult',x=600,chilled=999)
        ext.update(b,z)
        tick(b,z,90)
        self.assertNotIn('basketball_fired',[e for e,_ in b.events])
        tick(b,z,90)
        self.assertIn('basketball_fired',[e for e,_ in b.events])

    def test_catapult_targets_leftmost_and_hits_for_75(self):
        p,q=plant(col=1),plant(col=3,id='p2')
        b,z=Board([q,p]),unit('catapult',hp=850,x=600)
        ext.update(b,z)
        self.assertEqual(z.phase,'catapult_launching')
        tick(b,z,220)
        self.assertEqual(p.hp,3925)
        self.assertEqual(q.hp,4000)

    def test_umbrella_blocks_basketball(self):
        p,u=plant(col=1),plant('umbrella_leaf',col=2,id='umbrella')
        b,z=Board([p,u]),unit('catapult',hp=850,x=600)
        ext.update(b,z)
        tick(b,z,220)
        self.assertEqual(p.hp,4000)
        self.assertIn('basketball_blocked',[e for e,_ in b.events])

    def test_ball_survives_shooter_death(self):
        p=plant(col=1)
        b,z=Board([p]),unit('catapult',hp=850,x=600)
        ext.update(b,z)
        tick(b,z,82)
        b.kill(z,'test')
        b.frame+=120
        ext.update_projectiles(b)
        self.assertEqual(p.hp,3925)

    def test_vehicle_crush_and_spike(self):
        p=plant()
        b,z=Board([p]),unit('zamboni',x=120,hp=1350)
        ext.update(b,z)
        self.assertEqual(p.hp,0)
        p=plant('spikeweed')
        b,z=Board([p]),unit('zamboni',x=120,hp=1350)
        ext.update(b,z)
        self.assertEqual(z.status,'dead')
        self.assertEqual(p.hp,0)

    def test_machine_squashes_brain(self):
        brain=SimpleNamespace(row=3,hp=70)
        b,z=Board(brains=[brain]),unit('catapult',hp=850,x=-31)
        ext.update(b,z)
        self.assertEqual(brain.hp,0)


class OtherTests(unittest.TestCase):
    def test_balloon_is_only_air_target_until_popped(self):
        b,z=Board(),unit('balloon')
        ext.initialize(b,z)
        self.assertFalse(ext.targetable(z))
        self.assertTrue(ext.targetable(z,'air'))
        ext.pop_balloon(b,z)
        tick(b,z,ext.BALLOON_POP_FRAMES)
        self.assertEqual(z.phase,'balloon_walking')
        self.assertTrue(ext.targetable(z))
        self.assertTrue(ext.targetable(z,'air'))

    def test_balloon_lands_for_brain(self):
        b=Board(brains=[SimpleNamespace(row=3,hp=70)])
        z=unit('balloon',x=-31)
        ext.update(b,z)
        self.assertEqual(z.phase,'balloon_popping')

    def test_newspaper_anger(self):
        b,z=Board(),unit('newspaper',shield_hp=150)
        ext.initialize(b,z)
        z.shield_hp=0
        ext.after_damage(b,z)
        self.assertEqual(z.phase,'newspaper_maddening')
        tick(b,z,ext.NEWSPAPER_GASP_FRAMES)
        self.assertEqual(z.speed,.4)

    def test_jack_110_frame_pop_and_radius(self):
        p,q=plant(col=2),plant(col=4,id='p2')
        b,z=Board([p,q]),unit('jack_in_the_box',x=100)
        ext.initialize(b,z)
        z.phase_timer=1
        ext.update(b,z)
        self.assertEqual(z.phase,'jack_popping')
        tick(b,z,110)
        self.assertEqual(p.hp,0)
        self.assertEqual(q.hp,4000)
        self.assertEqual(z.status,'dead')

    def test_pogo_ignores_short_but_not_tall(self):
        for type_ in ('wallnut', 'tallnut'):
            b,z=Board([plant(type_)]),unit('pogo',x=120)
            self.assertTrue(ext.update(b,z))
            self.assertTrue(z.tool)  # High nuts break only on the forward-bounce check.
        ext.remove_tool(b,z)
        self.assertFalse(z.tool)
        self.assertEqual(z.speed,.45*.47)

    def test_yeti_reverses(self):
        b,z=Board(),unit('yeti')
        ext.initialize(b,z)
        z.phase_timer=1
        ext.update(b,z)
        self.assertEqual(z.direction,1)

    def test_random_jack_timing_reproducible(self):
        b,c,z,w=Board(),Board(),unit('jack_in_the_box'),unit('jack_in_the_box')
        ext.initialize(b,z)
        ext.initialize(c,w)
        self.assertEqual(z.phase_timer,w.phase_timer)


class EngineIntegrationTests(unittest.TestCase):
    def simulator(self, zombies, plants=(), max_frames=1000):
        from pvz_ize.model import parse_scenario
        from pvz_ize.engine import Simulator
        return Simulator(parse_scenario(dict(plants=list(plants), zombies=list(zombies), max_frames=max_frames)))

    def test_giant_full_engine_smashes_layers_and_brain(self):
        sim=self.simulator([dict(type='gargantuar',row=3,x=120)],
                           [dict(type='wallnut',row=3,col=2),dict(type='pumpkin',row=3,col=2)])
        result=sim.run()
        self.assertTrue(all(p['hp']==0 for p in result['plants']))
        self.assertGreater(result['events'].get('giant_smash',0),0)
        sim=self.simulator([dict(type='gargantuar',row=3,x=-31)])
        result=sim.run()
        self.assertEqual(result['winner'],'zombies')
        self.assertEqual(result['brains'][0]['hp'],0)

    def test_low_hp_giant_and_vehicles_do_not_lose_heads(self):
        for type_ in ['gargantuar','red_eye_gargantuar','catapult','zamboni']:
            with self.subTest(type_=type_):
                sim=self.simulator([dict(type=type_,row=3,x=600,hp=50)])
                z=sim.zombies[0]
                sim.damage(z,1,'test')
                self.assertFalse(z.headless)

    def test_catapult_full_engine_hits_and_umbrella_blocks(self):
        for umbrella in [False,True]:
            plants=[dict(type='wallnut',row=3,col=1)]
            if umbrella:
                plants.append(dict(type='umbrella_leaf',row=2,col=1))
            sim=self.simulator([dict(type='catapult',row=3,x=600)],plants,max_frames=230)
            result=sim.run()
            self.assertEqual(result['plants'][0]['hp'],4000 if umbrella else 3925)
            self.assertGreater(result['events'].get('basketball_blocked' if umbrella else 'basketball_hit',0),0)

    def test_balloon_attack_filter_and_pop_in_engine(self):
        sim=self.simulator([dict(type='balloon',row=3,x=600)])
        z=sim.zombies[0]
        self.assertFalse(sim.targetable(z))
        self.assertTrue(sim.targetable(z,'air'))
        sim.pop_balloon(z, "test")
        self.assertFalse(sim.targetable(z))
        self.assertFalse(sim.targetable(z,"homing"))
        self.assertTrue(sim.targetable(z,"explosion"))

    def test_vehicle_chill_eligibility_and_movement(self):
        for type_,expected in [('zamboni',0),('catapult',1000)]:
            sim=self.simulator([dict(type=type_,row=3,x=600)])
            z=sim.zombies[0]
            sim.damage(z,1,'ice',chill=True)
            self.assertEqual(z.chilled,expected)
            before=z.x
            sim.update_zombie(z)
            self.assertLess(z.x,before)


class ExtendedReviewTests(unittest.TestCase):
    def test_magnet_stops_jack_permanently(self):
        b,z=Board(),unit('jack_in_the_box')
        ext.initialize(b,z)
        ext.remove_tool(b,z)
        tick(b,z,10000)
        self.assertFalse(z.tool)
        self.assertEqual(z.phase,'walking')
        self.assertNotIn('jack_exploded',[e for e,_ in b.events])

    def test_initial_jack_without_box_stays_disarmed(self):
        b,z=Board(),unit('jack_in_the_box',tool=False)
        ext.update(b,z)
        self.assertEqual(z.phase,'walking')

    def test_magnet_does_not_cancel_already_popping_box(self):
        b,z=Board(),unit('jack_in_the_box',phase='jack_popping',phase_timer=110)
        ext.remove_tool(b,z)
        self.assertTrue(z.tool)
        tick(b,z,110)
        self.assertEqual(z.status,'dead')

    def test_hypnotized_giant_throws_forward(self):
        b,z=Board(),unit('gargantuar',hp=1499,x=600,hypnotized=True,direction=1)
        ext.update(b,z)
        tick(b,z,106)
        child=b.zombies[0]
        self.assertEqual(child.x,780)
        self.assertTrue(child.hypnotized)
        self.assertEqual(child.direction,1)

    def test_special_airborne_masks(self):
        for phase in ['balloon_popping','imp_thrown','imp_landing']:
            z=unit('imp',phase=phase)
            self.assertFalse(ext.targetable(z))
            self.assertFalse(ext.targetable(z,'homing'))
            self.assertTrue(ext.targetable(z,'explosion'))
        z=unit('balloon',phase='balloon_flying')
        self.assertTrue(ext.targetable(z,'explosion'))
        self.assertTrue(ext.targetable(z,'air'))

    def test_chilled_catapult_keeps_realtime_reload_counter(self):
        b,z=Board([plant(col=1)]),unit('catapult',x=600,chilled=999)
        ext.update(b,z)
        tick(b,z,302)
        self.assertEqual(z.phase,'catapult_launching')
        self.assertEqual(ext._state(b,z)['ammo'],19)


if __name__ == "__main__":
    unittest.main()
