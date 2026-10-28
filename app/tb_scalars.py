"""Read scalar values from TensorBoard event files without tensorboard/protobuf.

Port of AI_COVER_MV scripts/tb_scalars.py. Applio writes each epoch's losses to
<training dir>/eval/events.out.tfevents.*; this picks the values the loss chart
needs, one entry per epoch. Pure Python (used by the server and the trainer).
"""
import glob
import json
import os
import struct

# Applio tag -> output field
WANTED = {
    "loss/g/mel": "mel",      # how far the voice detail is from the speaker (most important)
    "loss/g/total": "total",  # generator total loss
    "loss/g/kl": "kl",
    "loss/g/fm": "fm",
    "loss/d/adv": "d_adv",    # discriminator (shows whether training is stable)
}


def _varint(buf, i):
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _fields(buf):
    """Yield protobuf fields: (field number, wire type, value)."""
    i, n = 0, len(buf)
    while i < n:
        key, i = _varint(buf, i)
        fno, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _varint(buf, i)
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
        elif wt == 2:
            ln, i = _varint(buf, i)
            val = buf[i:i + ln]
            i += ln
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
        else:
            return  # unknown wire type: skip this record
        yield fno, wt, val


def read_scalars(path, wanted=WANTED):
    """{field: [(step, value), ...]}; also works on a file that is still being written."""
    out = {v: [] for v in wanted.values()}
    with open(path, "rb") as f:
        data = f.read()
    i, n = 0, len(data)
    while i + 12 <= n:
        ln = struct.unpack("<Q", data[i:i + 8])[0]
        if i + 12 + ln + 4 > n:
            break  # last record not complete yet
        rec = data[i + 12:i + 12 + ln]
        i += 12 + ln + 4
        step, summary = 0, None
        try:
            for fno, wt, val in _fields(rec):
                if fno == 2 and wt == 0:
                    step = val
                elif fno == 5 and wt == 2:
                    summary = val
            if summary is None:
                continue
            for fno, wt, val in _fields(summary):
                if fno != 1 or wt != 2:
                    continue
                tag, sv = None, None
                for f2, w2, v2 in _fields(val):
                    if f2 == 1 and w2 == 2:
                        tag = v2.decode("utf-8", "replace")
                    elif f2 == 2 and w2 == 5:
                        sv = struct.unpack("<f", v2)[0]
                if tag in wanted and sv is not None:
                    out[wanted[tag]].append((int(step), float(sv)))
        except Exception:
            continue
    return out


def latest_event_file(log_dir):
    files = glob.glob(os.path.join(log_dir, "eval", "events.out.tfevents.*")) + \
        glob.glob(os.path.join(log_dir, "events.out.tfevents.*"))
    return max(files, key=os.path.getmtime) if files else None


def loss_by_epoch(path, steps_per_epoch=None):
    """One entry per epoch: {"epoch": [...], "mel": [...], ...}.
    Applio writes one record at the end of each epoch; step = epoch x steps per epoch."""
    sc = read_scalars(path)
    base = sc.get("mel") or sc.get("total") or []
    if not base:
        return {"epoch": []}
    steps = sorted({s for s, _ in base})
    if not steps_per_epoch:
        steps_per_epoch = steps[0] if steps[0] > 0 else 1
    out = {"epoch": [round(s / steps_per_epoch) for s in steps], "steps_per_epoch": steps_per_epoch}
    for k, series in sc.items():
        d = dict(series)
        out[k] = [round(d[s], 4) if s in d else None for s in steps]
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(loss_by_epoch(sys.argv[1]), ensure_ascii=False)[:2000])
