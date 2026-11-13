"""Rule tables for the explicitly approximate IZE model."""

from dataclasses import dataclass
from .extended_plants import SPECS as EXTENDED_PLANTS


@dataclass(frozen=True)
class PlantSpec:
    hp: int = 300
    period: int = 0
    windup: int = 0
    reach: int = 800


PLANTS = {
    "peashooter": PlantSpec(period=150, windup=34),
    "snow_pea": PlantSpec(period=150, windup=34),
    "repeater": PlantSpec(period=150, windup=25),
    "threepeater": PlantSpec(period=150, windup=34),
    "split_pea": PlantSpec(period=150, windup=25),
    "puff_shroom": PlantSpec(period=150, windup=28, reach=230),
    "fume_shroom": PlantSpec(period=150, windup=49, reach=340),
    "scaredy_shroom": PlantSpec(period=150, windup=24),
    "starfruit": PlantSpec(period=150, windup=39),
    "kernelpult": PlantSpec(period=300, windup=29),
    "sunflower": PlantSpec(),
    "wallnut": PlantSpec(hp=4000),
    "tallnut": PlantSpec(hp=8000),
    "umbrella_leaf": PlantSpec(),
    "torchwood": PlantSpec(),
    "spikeweed": PlantSpec(period=100),
    "potato_mine": PlantSpec(),
    "magnet_shroom": PlantSpec(),
    "chomper": PlantSpec(),
    "squash": PlantSpec(),
}
PLANTS.update({name: PlantSpec(hp=hp, period=period, windup=windup)
               for name, (hp, period, windup) in EXTENDED_PLANTS.items()})


@dataclass(frozen=True)
class ZombieSpec:
    hp: int = 270
    helmet: int = 0
    shield: int = 0
    speed: float = 0.143
    hit_offset: int = 36
    hit_width: int = 42
    metal: bool = False
    spawn_offset: int = -30
    can_lose_head: bool = True


ZOMBIES = {
    "normal": ZombieSpec(),
    "conehead": ZombieSpec(helmet=370),
    "buckethead": ZombieSpec(helmet=1100, metal=True),
    "screen_door": ZombieSpec(shield=1100, metal=True),
    "football": ZombieSpec(helmet=1400, speed=0.32,
                           hit_offset=50, hit_width=57, metal=True),
    "imp": ZombieSpec(hp=70, speed=0.423),
    "pole_vaulting": ZombieSpec(hp=500, speed=0.32),
    "ladder": ZombieSpec(hp=500, shield=500, speed=0.38, metal=True),
    "digger": ZombieSpec(helmet=100, speed=0.67, hit_offset=50, hit_width=28, metal=True),
    "dancing": ZombieSpec(hp=500, speed=0.22),
    "backup_dancer": ZombieSpec(speed=0.22),
    "bungee": ZombieSpec(hp=450, speed=0.001, hit_offset=-20,
                          hit_width=110, spawn_offset=0, can_lose_head=False),
    "gargantuar": ZombieSpec(hp=3000, speed=.2, hit_offset=-17, hit_width=125, can_lose_head=False),
    "red_eye_gargantuar": ZombieSpec(hp=6000, speed=.2, hit_offset=-17, hit_width=125, can_lose_head=False),
    "catapult": ZombieSpec(hp=850, speed=.2, hit_offset=0, hit_width=153, can_lose_head=False),
    "zamboni": ZombieSpec(hp=1350, speed=.25, hit_offset=0, hit_width=153, can_lose_head=False),
    "balloon": ZombieSpec(speed=.2, can_lose_head=False),
    "newspaper": ZombieSpec(shield=150, speed=.09),
    "jack_in_the_box": ZombieSpec(hp=500, speed=.32, metal=True),
    "flag": ZombieSpec(speed=.22),
    "pogo": ZombieSpec(hp=500, speed=.45, metal=True),
    "yeti": ZombieSpec(hp=1350, speed=.2),
    "boss": ZombieSpec(hp=60000, speed=.001, hit_offset=700, hit_width=90,
                       spawn_offset=-40, can_lose_head=False),
    "pea_head": ZombieSpec(),
    "wallnut_head": ZombieSpec(helmet=1100),
    "jalapeno_head": ZombieSpec(hp=500),
    "gatling_head": ZombieSpec(),
    "squash_head": ZombieSpec(speed=.38),
    "tallnut_head": ZombieSpec(helmet=2200),
}

# The single-letter plant aliases match rpze's layout notation.
PLANT_ALIASES = dict(zip(
    "1bo2pdxw3_jlctzhs",
    ["peashooter", "snow_pea", "wallnut", "repeater", "puff_shroom",
     "fume_shroom", "scaredy_shroom", "squash", "threepeater", "spikeweed",
     "torchwood", "split_pea", "magnet_shroom", "potato_mine", "chomper",
     "sunflower", "umbrella_leaf"],
))
ZOMBIE_ALIASES = {"lz": "conehead", "tt": "buckethead", "gl": "football",
                  "xg": "imp", "cg": "pole_vaulting", "tz": "ladder",
                  "ft": "ladder", "kg": "digger", "ww": "dancing",
                  "mj": "dancing", "bj": "bungee", "xt": "bungee"}
PLANT_ALIASES.update({"5": "starfruit", "y": "kernelpult"})
MODEL = "izc-predict-v5.6"
WARNINGS = [
    "Approximate offline model; not frame-equivalent to PvZ 1.0.0.1051.",
    "Animation-driven movement, attack geometry and special timings are simplified; "
    "the seed reproduces this model only, not the original game RNG.",
    "IZC 0.7.1 mode rules are statically checked; no live-game differential accuracy is claimed.",
]
