#!/usr/bin/env python3
"""Compose complete PvZ icons from compiled reanimation transforms and PNG layers."""
from __future__ import annotations
import argparse, re, struct, zlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'ref/ize-creative/【推荐】我是僵尸创造+0.7.1+Pro'; REANIM=SRC/'reanim'; COMPILED=SRC/'compiled/reanim'; OUT=ROOT/'pvz_ize/web/assets'
UNITS={'peashooter':'PeaShooter','snow_pea':'SnowPea','repeater':'Repeater','threepeater':'Threepeater','split_pea':'SplitPea','puff_shroom':'PuffShroom','fume_shroom':'FumeShroom','scaredy_shroom':'ScaredyShroom','starfruit':'Starfruit','kernelpult':'KernelPult','sunflower':'SunFlower','wallnut':'Wallnut','tallnut':'TallNut','umbrella_leaf':'UmbrellaLeaf','torchwood':'Torchwood','spikeweed':'Spikeweed','potato_mine':'PotatoMine','magnet_shroom':'Magnetshroom','chomper':'Chomper','squash':'Squash','cactus':'Cactus','cattail':'Cattail','gatling_pea':'GatlingPea','cabbage_pult':'Cabbagepult','melon_pult':'Melonpult','winter_melon':'WinterMelon','gloom_shroom':'GloomShroom','garlic':'Garlic','pumpkin':'Pumpkin','lily_pad':'LilyPad','flower_pot':'FlowerPot','spikerock':'SpikeRock','cherry_bomb':'CherryBomb','jalapeno':'Jalapeno','doom_shroom':'DoomShroom','ice_shroom':'IceShroom','blover':'Blover','hypno_shroom':'HypnoShroom','cob_cannon':'CobCannon','normal':'Zombie','flag':'Zombie_flag','conehead':'Zombie_cone','buckethead':'Zombie_bucket','screen_door':'Zombie_screen','football':'Zombie_football','pole_vaulting':'Zombie_polevaulter','ladder':'Zombie_ladder','digger':'Zombie_digger','dancing':'Zombie_dancer','backup_dancer':'Zombie_backupdancer','bungee':'Zombie_bungi','gargantuar':'Zombie_gargantuar','red_eye_gargantuar':'Zombie_gargantuar','imp':'Zombie_imp','zamboni':'Zombie_zamboni','catapult':'Zombie_catapult','balloon':'Zombie_balloon','newspaper':'Zombie_paper','jack_in_the_box':'Zombie_jackbox','pogo':'Zombie_pogo','yeti':'Zombie_yeti','pea_head':'Zombie_peahead','gatling_head':'Zombie_gatlinghead','wallnut_head':'Zombie_wallnuthead','tallnut_head':'Zombie_tallnuthead','jalapeno_head':'Zombie_jalapenohead','squash_head':'Zombie_squashhead'}
# The generic Zombie reanimation contains optional tracks used by cone, bucket,
# flag and water variants.  They are toggled by game code, not part of the
# ordinary zombie icon, so suppress them for the base ``normal`` key.
EXCLUDE_TRACKS={'normal':{'anim_cone','anim_bucket','Zombie_flaghand','Zombie_innerarm_screendoor','Zombie_duckytube','Zombie_whitewater','Zombie_whitewater2'}}
def norm(s): return re.sub(r'[^a-z0-9]','',s.lower())

def parse(path):
 raw=zlib.decompress(path.read_bytes()[8:]); pos=0
 def take(n):
  nonlocal pos; b=raw[pos:pos+n]; pos+=n; return b
 def unpack(fmt): return struct.unpack(fmt,take(struct.calcsize(fmt)))
 def string(): return take(unpack('<I')[0]).decode('utf8')
 if unpack('<I')[0]!=0xB393B4C0: raise ValueError('bad schema')
 pointer,count,fps,atlas=unpack('<IIfI'); stride=unpack('<I')[0]; headers=[unpack('<III') for _ in range(count)]
 tracks=[]
 for nameptr,trptr,nframes in headers:
  name=string(); ts=unpack('<I')[0]
  if ts!=44: raise ValueError('bad transform stride')
  frames=[list(unpack('<8fIII')[:8]) for _ in range(nframes)]; imgs=[]
  for i in range(nframes): imgs.append((string(),string(),string()))
  prev=[0,0,0,0,1,1,-1,1]; last=''
  for i,f in enumerate(frames):
   for j,v in enumerate(f):
    if v==-10000.0:f[j]=prev[j]
    else:prev[j]=v
   if imgs[i][0]: last=imgs[i][0]
   imgs[i]=(last,imgs[i][1],imgs[i][2])
  tracks.append((name,frames,imgs))
 return tracks

def choose_frame(tracks):
 # Compiled files concatenate several animations.  A fixed frame (80) works for
 # plants but is often before the zombie's idle segment (normal Zombie starts
 # around frame 454).  Pick the frame with the richest set of visible image
 # tracks, preferring the middle of a plateau so we avoid transition/death
 # frames.  This is deterministic and does not require knowing each unit's
 # animation table.
 n=max(len(x[1]) for x in tracks)
 scores=[]
 for i in range(n):
  count=sum(1 for _,frames,imgs in tracks if i<len(frames) and frames[i][6]>=0 and imgs[i][0])
  scores.append(count)
 best=max(scores,default=0)
 if not best:return min(4,n-1)
 candidates=[i for i,s in enumerate(scores) if s==best]
 # Choose an interior candidate when a long plateau exists, else earliest.
 return candidates[len(candidates)//2]

def compose(unit, basename, outdir=OUT):
 cp=COMPILED/(basename+'.reanim.compiled')
 if not cp.exists(): return None,'compiled missing'
 tracks=parse(cp); frame=(min(50, max(len(x[1]) for x in tracks)-1)
                           if unit == 'yeti' else choose_frame(tracks))
 files={norm(p.stem):p for p in REANIM.glob('*.png')}; layers=[]; missing=[]
 for name,frames,imgs in tracks:
  if name in EXCLUDE_TRACKS.get(unit,set()): continue
  if frame>=len(frames): continue
  f=frames[frame]; image=imgs[frame][0]
  # Static layers in several creative exports (Pumpkin, Blover,
  # HypnoShroom, etc.) intentionally keep atlas frame -1.  The PNG name is
  # still a drawable layer; only an absent image name means the track is a
  # controller and should be skipped.
  if not image: continue
  key=norm(image.replace('IMAGE_REANIM_',''))
  p=files.get(key)
  if not p: missing.append((name,image)); continue
  try: im=Image.open(p).convert('RGBA')
  except: continue
  sx,sy=max(.01,abs(f[4])),max(.01,abs(f[5])); im=im.resize((max(1,round(im.width*sx)),max(1,round(im.height*sy))),Image.Resampling.LANCZOS)
  if f[4]<0: im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
  # reanim's x/y are layer top-left in a ~100x100 icon coordinate system.
  layers.append((name,im,round(f[0]),round(f[1]),f[7]))
 if not layers:return None,'no image layers'
 minx=min(x for _,im,x,y,a in layers); miny=min(y for _,im,x,y,a in layers); maxx=max(x+im.width for _,im,x,y,a in layers); maxy=max(y+im.height for _,im,x,y,a in layers)
 pad=4; w=maxx-minx+pad*2; h=maxy-miny+pad*2; canvas=Image.new('RGBA',(w,h),(0,0,0,0))
 for name,im,x,y,a in layers:
  if a!=1: im.putalpha(im.getchannel('A').point(lambda p:round(p*max(0,min(1,a)))))
  canvas.alpha_composite(im,(x-minx+pad,y-miny+pad))
 # Normalize to icon card while preserving complete silhouette.
 scale=min(150/w,150/h,1.0); canvas=canvas.resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.LANCZOS)
 card=Image.new('RGBA',(160,160),(0,0,0,0)); card.alpha_composite(canvas,((160-canvas.width)//2,(160-canvas.height)//2)); outdir.mkdir(parents=True,exist_ok=True); card.save(outdir/(unit+'.png'),optimize=True)
 return outdir/(unit+'.png'),{'layers':len(layers),'missing':missing,'frame':frame,'size':card.size}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--unit',action='append'); ap.add_argument('--all',action='store_true'); ap.add_argument('--out',type=Path,default=OUT); a=ap.parse_args(); units=UNITS if a.all or not a.unit else {k:UNITS[k] for k in a.unit if k in UNITS}
 for unit,b in units.items():
  try:
   out,info=compose(unit,b,a.out); print(f'{unit}: {out or info} {info if out else ""}')
  except Exception as e: print(f'{unit}: ERROR {e}')
if __name__=='__main__':main()
