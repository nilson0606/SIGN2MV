import json, os, subprocess, sys
d=json.load(open('/tmp/tut_frames.json')); fr=d['frames']; mk=d['marks']
t_end=[m for m in mk if m.get('end')][0]['ts']
speeds=sorted([(m['ts'],m['speed']) for m in mk if 'speed' in m])
drops=[tuple(m['drop']) for m in mk if 'drop' in m]
scenes=[(m['ts'],m['scene']) for m in mk if 'scene' in m]
def speed_at(t):
    s=1
    for ts,v in speeds:
        if ts<=t: s=v
    return s
def film(a,b):
    pts=sorted({a,b,*[ts for ts,_ in speeds if a<ts<b],*[x for dr in drops for x in dr if a<x<b]})
    tot=0
    for x,y in zip(pts,pts[1:]):
        mid=(x+y)/2
        if any(l<=mid<r for l,r in drops): continue
        tot+=(y-x)/speed_at(mid)
    return tot
fr=[f for f in fr if os.path.getsize(f['file'])>0]
bounds=[ts for ts,_ in scenes]+[t_end]
out='/tmp/tut_out'; os.makedirs(out,exist_ok=True)
total=0; parts=[]
for i,(ts,name) in enumerate(scenes):
    a,b=bounds[i],bounds[i+1]
    prev=[f for f in fr if f['ts']<=a]
    seq=([dict(prev[-1],ts=a)] if prev else [])+[f for f in fr if a<f['ts']<b]
    items=[(f['file'],film(f['ts'],nx['ts'])) for f,nx in zip(seq,seq[1:]+[{'ts':b}])]
    items=[x for x in items if x[1]>0.0005]
    dur=sum(x[1] for x in items); total+=dur
    lst=f'{out}/{i:02d}_{name}.txt'
    with open(lst,'w') as fh:
        fh.write("ffconcat version 1.0\n")
        for file,du in items: fh.write(f"file '{file}'\nduration {du:.4f}\n")
        fh.write(f"file '{items[-1][0]}'\n")
    mp4=f'{out}/{i:02d}_{name}.mp4'; tmp=mp4.replace('.mp4','.tmp.mp4')
    r=subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',lst,'-vf','fps=30,format=yuv420p','-t',f'{dur:.3f}',
                      '-c:v','libx264','-crf','19','-preset','veryfast','-pix_fmt','yuv420p','-video_track_timescale','30000',tmp])
    if r.returncode: sys.exit(f'encode failed: {name}')
    os.replace(tmp,mp4); parts.append(mp4); print(f'{i:02d} {name:12s} {dur:6.1f}s  {len(items)} frames')
print('total', round(total,1),'s')
with open(f'{out}/all.txt','w') as fh:
    for p in parts: fh.write(f"file '{p}'\n")
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',f'{out}/all.txt','-c','copy',f'{out}/video.tmp.mp4'],check=True)
subprocess.run(['ffmpeg','-y','-v','error','-i',f'{out}/video.tmp.mp4','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','64k','-shortest','-movflags','+faststart',f'{out}/final.tmp.mp4'],check=True)
os.replace(f'{out}/final.tmp.mp4', f'{out}/SIGN2MV_分段錄音教學.mp4'); os.remove(f'{out}/video.tmp.mp4')
