"""Local-only PCM capture. No audio files are written."""
import argparse,json,sys,threading
import numpy as np
import soundcard as sc
from native_monitor import NativeMonitor
from native_capture import ContinuousCapture, WasapiPackets, CaptureInterrupted, CAPTURE_POLICY, PCMDelivery, audio_priority
p=argparse.ArgumentParser()
p.add_argument('--list',action='store_true')
p.add_argument('--outputs',action='store_true')
p.add_argument('--device',default='')
a=p.parse_args()
if a.list:
    print(json.dumps({'devices':[{'deviceId':m.id,'label':m.name,'kind':'audioinput'} for m in sc.all_microphones()]}))
elif a.outputs:
    print(json.dumps({'devices':[{'deviceId':s.id,'label':s.name,'kind':'audiooutput'} for s in sc.all_speakers()]}))
else:
    devices=sc.all_microphones()
    mic=next((m for m in devices if m.id==a.device),None) if a.device else sc.default_microphone()
    if mic is None: raise RuntimeError('Selected microphone is no longer available')
    def report(value):
        sys.stderr.write(json.dumps(value,ensure_ascii=True)+'\n')
        sys.stderr.flush()
    monitor=NativeMonitor(report)
    def controls():
        try:
            for line in sys.stdin:
                try:
                    command=json.loads(line)
                    if isinstance(command,dict): monitor.command(command)
                except (ValueError,TypeError): pass
        finally:
            monitor.close()
    threading.Thread(target=controls,daemon=True,name='monitor-controls').start()
    capture=None
    delivery=None
    out=sys.stdout.buffer
    def send_pcm(data):
        if not data:return
        frames=np.frombuffer(data,dtype='<f4').reshape(-1,2)
        mono=np.mean(frames,axis=1).astype('<f4')
        out.write(mono.tobytes());out.flush()
        monitor.feed(mono)
    try:
        # Device format and PCM wire format stay the same; never use SoundCard's
        # wall-clock-based silence insertion in record().
        # WASAPI blocksize is the device buffer capacity, not our delivery size.
        # A 20 ms capacity overflowed during ordinary Windows scheduling delays.
        # Reserve 500 ms of headroom but continue draining/sending every 20 ms;
        # do not wait for this buffer to fill or alter any captured samples.
        # Pipe writes and monitoring run separately, so even a blocked consumer
        # cannot prevent this thread from draining the device buffer promptly.
        delivery = PCMDelivery(send_pcm)
        out.write((json.dumps({'label':mic.name,'sampleRate':48000,'channels':1,'capturePolicy':CAPTURE_POLICY})+'\n').encode())
        out.flush()
        with audio_priority(report), mic.recorder(samplerate=48000,channels=2,blocksize=24000) as source:
            capture = ContinuousCapture(WasapiPackets(source), report)
            report({'capture':True,'event':'configured','bufferFrames':source.buffersize,
                    'sampleRate':48000,'deliveryFrames':960,'device':mic.name,'transport':'queued-v1'})
            while True:
                delivery.submit(capture.read(960))
    except CaptureInterrupted as error:
        # ContinuousCapture already emitted a structured diagnostic; closing
        # stdout tells the browser to preserve this take as incomplete.
        if not capture or capture.failed is None:
            report({'capture':True,'event':'error','code':error.code,'error':str(error)})
        if capture and delivery and capture.failed:delivery.submit(capture.drain())
        raise SystemExit(2)
    except BrokenPipeError:
        pass  # The browser closed this capture normally.
    except Exception as error:
        report({'capture':True,'event':'error','code':'capture-exception','error':str(error)[:500]})
        raise
    finally:
        if delivery:
            try:delivery.close()
            except BrokenPipeError:pass
            except Exception as error:
                report({'capture':True,'event':'error','code':getattr(error,'code','transport-error'),'error':str(error)})
        monitor.close()
