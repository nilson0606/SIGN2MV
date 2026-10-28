"""Synthetic test song: a formant-synthesised sung melody over drums, bass and pad.

Usage: synth_song.py OUT.wav SECONDS [--voice-only]   (engine python: numpy, scipy, soundfile)
"""
import numpy as np, soundfile as sf, sys
from scipy.signal import lfilter
sr=44100; secs=float(sys.argv[2]) if len(sys.argv)>2 else 12
t=np.arange(int(sr*secs))/sr
rng=np.random.default_rng(1)
notes=[57,60,62,64,62,60,59,57]  # midi
nd=1.0
f0=np.zeros_like(t); env=np.zeros_like(t)
for i in range(int(secs/nd)):
    m=notes[i%len(notes)]; s=int(i*nd*sr); e=int((i+1)*nd*sr)
    f0[s:e]=440*2**((m-69)/12)
    seg=np.arange(e-s)/sr
    env[s:e]=np.clip(seg/0.05,0,1)*np.clip((nd-0.12-seg)/0.05,0,1)
f0=f0*(1+0.012*np.sin(2*np.pi*5.5*t))*(1+0.003*rng.standard_normal(len(t)).cumsum()/np.sqrt(np.arange(1,len(t)+1)))
phase=np.cumsum(2*np.pi*f0/sr)
# glottal pulse train: sum of harmonics with -12 dB/oct
src=np.zeros_like(t)
for k in range(1,40):
    a=1/k**1.5
    src+=a*np.sin(k*phase)*(k*f0<sr/2-1000)
src+=0.02*rng.standard_normal(len(t))
def formant(x,f,bw):
    r=np.exp(-np.pi*bw/sr); th=2*np.pi*f/sr
    return lfilter([1-r],[1,-2*r*np.cos(th),r*r],x)
vowels=[(800,1150,2900),(400,1600,2700),(350,2300,3000),(450,800,2830)]
voice=np.zeros_like(t)
for i in range(int(secs/nd)):
    s=int(i*nd*sr); e=int((i+1)*nd*sr); F=vowels[i%4]
    seg=src[s:e]
    voice[s:e]=sum(formant(seg,f,bw) for f,bw in zip(F,(80,90,120)))
voice*=env; voice/=np.abs(voice).max()+1e-9; voice*=0.5
# backing: kick + hats + bass + pad chords
beat=0.5
kick=np.exp(-25*np.mod(t,beat))*np.sin(2*np.pi*55*t)*0.5
hat=rng.standard_normal(len(t))*np.exp(-60*np.mod(t+beat/2,beat))*0.08
bassf=np.where(np.mod(t,4)<2,110*2**(-9/12)*2,98)
bass=0.2*np.sign(np.sin(2*np.pi*np.cumsum(bassf)/sr))*0.5
pad=0.06*sum(np.sin(2*np.pi*f*t) for f in (220,277,330))
mix=voice if '--voice-only' in sys.argv else voice+kick+hat+bass+pad
mix=np.stack([mix,mix],1)/np.abs(mix).max()*0.8
sf.write(sys.argv[1],mix,sr,subtype='PCM_16')
