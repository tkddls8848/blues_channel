"""모체곡과 변이곡이 같은 멜로디 · 화성 위에 있는지 크로마(12음 분포)로 잰다 (numpy · soundfile).

  python latin_chant/tools/melody_sim.py latin_chant/runs/exp1/m0_cinis_turbo_s1.flac latin_chant/runs/exp1/*.flac

같은 시점의 프레임끼리 코사인 유사도를 내고, 박자가 조금 어긋나도 되도록 ±1박 안에서 가장 잘 맞는 어긋남을 고른다.
- same : 시점을 맞춘 프레임 유사도 평균 (1 이면 같은 곡)
- key  : 곡 전체 12음 분포의 유사도 (조성 · 화음 재료가 같으면 높다 — 멜로디가 달라도 높게 나온다)
same 이 시드만 다른 모체곡 후보끼리의 값보다 확실히 높아야 "멜로디가 잠겼다" 고 본다.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8', errors='replace')

N, HOP = 8192, 4096


def chroma(path):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    x = x.mean(axis=1)
    frames = np.lib.stride_tricks.sliding_window_view(x, N)[::HOP] * np.hanning(N)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    f = np.fft.rfftfreq(N, 1 / sr)
    band = (f >= 65) & (f <= 2000)   # 대략 C2 ~ B6, 멜로디 · 화성 대역
    pc = np.round(12 * np.log2(f[band] / 440.0)).astype(int) % 12
    c = np.zeros((len(frames), 12), dtype=np.float32)
    for k in range(12):
        c[:, k] = mag[:, band][:, pc == k].sum(axis=1)
    c /= np.linalg.norm(c, axis=1, keepdims=True) + 1e-9
    return c, sr


def same(a, b, max_shift):
    best = 0.0
    for s in range(-max_shift, max_shift + 1):
        x, y = (a[s:], b[:len(b) - s]) if s >= 0 else (a[:s], b[-s:])
        n = min(len(x), len(y))
        best = max(best, float((x[:n] * y[:n]).sum(axis=1).mean()))
    return best


def key(a, b):
    p, q = a.mean(axis=0), b.mean(axis=0)
    return float(p @ q / (np.linalg.norm(p) * np.linalg.norm(q)))


def main():
    ref, *others = sys.argv[1:]
    a, sr = chroma(ref)
    max_shift = max(1, round(60 / 84 * sr / HOP))   # 84 BPM 기준 1박
    print(f'기준 {Path(ref).name}')
    print(f'{"곡":<34} {"same":>6} {"key":>6}')
    for o in others:
        if Path(o).resolve() == Path(ref).resolve():
            continue
        b, _ = chroma(o)
        print(f'{Path(o).stem:<34} {same(a, b, max_shift):6.3f} {key(a, b):6.3f}')


if __name__ == '__main__':
    main()
