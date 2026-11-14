#!/usr/bin/env python3
"""Build readable unit icons from local PvZ reanimation PNG layers.

The original game stores each character as layered reanimation parts. This tool
selects the largest body/head layer for each unit, centers it on a transparent
canvas, and never uses tiny blink/face-only parts when a body/head layer exists.
It is a fallback icon builder; exact game rendering still requires the compiled
reanimation renderer.
"""
from pathlib import Path
import shutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ref/ize-creative/【推荐】我是僵尸创造+0.7.1+Pro/reanim"
DST = ROOT / "pvz_ize/web/assets"
PLANTS = {
    "peashooter":"PeaShooter", "snow_pea":"SnowPea", "repeater":"Repeater",
    "threepeater":"ThreePeater", "split_pea":"SplitPea", "puff_shroom":"PuffShroom",
    "fume_shroom":"FumeShroom", "scaredy_shroom":"ScaredyShroom", "starfruit":"Starfruit",
    "kernelpult":"KernelPult", "sunflower":"SunFlower", "wallnut":"Wallnut", "tallnut":"TallNut",
    "umbrella_leaf":"UmbrellaLeaf", "torchwood":"Torchwood", "spikeweed":"Spikeweed",
    "potato_mine":"PotatoMine", "magnet_shroom":"Magnetshroom", "chomper":"Chomper",
    "squash":"Squash", "cactus":"Cactus", "cattail":"Cattail", "gatling_pea":"GatlingPea",
    "cabbage_pult":"Cabbagepult", "melon_pult":"Melonpult", "winter_melon":"WinterMelon",
    "gloom_shroom":"GloomShroom", "garlic":"Garlic", "pumpkin":"Pumpkin", "lily_pad":"LilyPad",
    "flower_pot":"FlowerPot", "spikerock":"SpikeRock", "cherry_bomb":"CherryBomb",
    "jalapeno":"Jalapeno", "doom_shroom":"DoomShroom", "ice_shroom":"IceShroom",
    "blover":"Blover", "hypno_shroom":"HypnoShroom", "cob_cannon":"CobCannon",
}
ZOMBIES = {
    "normal":"Zombie", "flag":"Zombie_flag", "conehead":"Zombie_cone", "buckethead":"Zombie_bucket",
    "screen_door":"Zombie_screen", "football":"Zombie_football", "pole_vaulting":"Zombie_polevaulter",
    "ladder":"Zombie_ladder", "digger":"Zombie_digger", "dancing":"Zombie_dancer", "backup_dancer":"Zombie_backupdancer",
    "bungee":"Zombie_bungi", "gargantuar":"Zombie_gargantuar", "red_eye_gargantuar":"Zombie_gargantuar",
    "imp":"Zombie_imp", "zamboni":"Zombie_zamboni", "catapult":"Zombie_catapult", "balloon":"Zombie_balloon",
    "newspaper":"Zombie_paper", "jack_in_the_box":"Zombie_jackbox", "pogo":"Zombie_pogo", "yeti":"Zombie_yeti",
    "pea_head":"Zombie_peahead", "gatling_head":"Zombie_gatlinghead", "wallnut_head":"Zombie_wallnuthead",
    "tallnut_head":"Zombie_tallnuthead", "jalapeno_head":"Zombie_jalapenohead", "squash_head":"Zombie_squashhead",
}

def choose(prefix):
    files=[]
    for p in SRC.glob(prefix+"*"):
        try:
            im=Image.open(p).convert("RGBA")
        except Exception:
            continue
        name=p.stem.lower()
        # Prefer a body/head/base over tiny facial or projectile pieces.
        rank=(0 if any(x in name for x in ("body","head","base","front","full")) else 1,
              1 if any(x in name for x in ("projectile","leaf","arm","leg","foot","eye","blink","mouth")) else 0,
              -(im.width*im.height))
        files.append((rank,p,im))
    return min(files,key=lambda x:x[0]) if files else None

def write_icon(name,prefix):
    chosen=choose(prefix)
    if not chosen: return None
    _,path,im=chosen
    # Keep ratio and center on a predictable transparent card.
    max_side=150
    scale=min(max_side/im.width,max_side/im.height,1.0)
    if scale != 1: im=im.resize((max(1,round(im.width*scale)),max(1,round(im.height*scale))),Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",(160,160),(0,0,0,0)); canvas.alpha_composite(im,((160-im.width)//2,(160-im.height)//2))
    canvas.save(DST/(name+".png"),optimize=True)
    return path.name

if __name__ == "__main__":
    DST.mkdir(parents=True,exist_ok=True)
    for name,prefix in {**PLANTS,**ZOMBIES}.items():
        chosen=write_icon(name,prefix)
        print(f"{name}: {chosen or 'MISSING'}")
