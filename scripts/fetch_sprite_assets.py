"""Fetch complete PvZ unit thumbnails used by the editor palette.

The wiki 1-suffix files are the 96x96 full-body thumbnails (the same style as
Giant_Sunflower1.png).  A raw GitHub frame is used only for the normal zombie,
which has no matching wiki file in the source index.  Existing files are kept
when a remote request is unavailable or returns HTML.
"""
from __future__ import annotations
import concurrent.futures, pathlib, subprocess, sys

OUT = pathlib.Path(__file__).resolve().parents[1] / "pvz_ize/web/assets"
WIKI = "https://plantsvszombies.wiki.gg/images/{}"
GITHUB = "https://raw.githubusercontent.com/limuy2022/PlantsVsZombies/main/resources/graphics/Zombies/NormalZombie/Zombie/Zombie_0.png"
# Use the complete 96px thumbnails where available.  Names intentionally match
# the wiki's public file names; do not replace these with partial body/head files.
M = {
"peashooter":"Peashooter1.png","snow_pea":"Snow_Pea1.png","repeater":"Repeater1.png","threepeater":"Threepeater1.png","split_pea":"Split_Pea1.png","puff_shroom":"Puff-shroom1.png","fume_shroom":"Fume-shroom1.png","scaredy_shroom":"Scaredy-shroom1.png","starfruit":"Starfruit1.png","kernelpult":"Kernel-pult1.png","wallnut":"Wall-nut1.png","tallnut":"Tall-nut1.png","umbrella_leaf":"Umbrella_Leaf1.png","torchwood":"Torchwood1.png","spikeweed":"Spikeweed1.png","potato_mine":"Potato_Mine1.png","magnet_shroom":"Magnet-shroom1.png","chomper":"Chomper1.png","squash":"Squash1.png","cactus":"Cactus1.png","cattail":"Cattail1.png","gatling_pea":"Gatling_Pea1.png","cabbage_pult":"Cabbage-pult1.png","melon_pult":"Melon-pult1.png","winter_melon":"Winter_Melon1.png","gloom_shroom":"Gloom-shroom1.png","garlic":"Garlic1.png","pumpkin":"Pumpkin1.png","lily_pad":"Lily_Pad1.png","flower_pot":"Flower_Pot1.png","spikerock":"Spikerock1.png","cherry_bomb":"Cherry_Bomb1.png","jalapeno":"Jalapeno1.png","doom_shroom":"Doom-shroom1.png","ice_shroom":"Ice-shroom1.png","blover":"Blover1.png","hypno_shroom":"Hypno-shroom1.png",
"flag":"Flag_Zombie1.png","conehead":"Conehead_Zombie1.png","buckethead":"Buckethead_Zombie1.png","screen_door":"Screen_Door_Zombie1.png","football":"Football_Zombie1.png","pole_vaulting":"Pole_Vaulting_Zombie1.png","ladder":"Ladder_Zombie1.png","digger":"Digger_Zombie1.png","dancing":"Dancing_Zombie1.png","backup_dancer":"Backup_Dancer1.png","bungee":"Bungee_Zombie1.png","gargantuar":"Gargantuar1.png","imp":"Imp1.png","zamboni":"Zomboni1.png","catapult":"Catapult_Zombie1.png","balloon":"Balloon_Zombie1.png","newspaper":"Newspaper_Zombie1.png","jack_in_the_box":"Jack-in-the-Box_Zombie1.png","pogo":"Pogo_Zombie1.png","yeti":"Yeti1.png",
}

def fetch(item):
    typ, filename = item
    dst = OUT / f"{typ}.png"
    tmp = dst.with_suffix('.png.download')
    url = WIKI.format(filename.replace(' ', '_'))
    # Three short attempts; a failed request must not destroy a known-good file.
    for _ in range(3):
        try:
            p = subprocess.run(["curl","-L","--fail","--silent","--show-error","--max-time","15","-A","pvz-ize/1.0","-o",str(tmp),url],capture_output=True,text=True)
            data = tmp.read_bytes() if tmp.exists() else b""
            if p.returncode == 0 and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 500:
                tmp.replace(dst); return typ, len(data), filename
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
    return typ, None, filename

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for typ, size, fn in pool.map(fetch, M.items()):
            print(f"{typ}: {size or 'kept'} ({fn})", flush=True)
    # Normal zombie is the only catalog item deliberately sourced elsewhere.
    dst = OUT / "normal.png"; tmp = dst.with_suffix('.png.download')
    p = subprocess.run(["curl","-L","--fail","--silent","--show-error","--max-time","20","-o",str(tmp),GITHUB],capture_output=True,text=True)
    data = tmp.read_bytes() if tmp.exists() else b""
    if p.returncode == 0 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        tmp.replace(dst); print(f"normal: {len(data)} (GitHub Zombie_0.png)")
    else:
        tmp.unlink(missing_ok=True); print("normal: kept", file=sys.stderr)

if __name__ == '__main__': main()
