"""참조 곡의 템포 · 박자 · 조성을 잰다 (numpy · soundfile) — 태그를 원곡에 맞추려고.

  python latin_chant/tools/analyze_ref.py latin_chant/ref/voland_full.flac latin_chant/ref/voland_climax_132-180.flac

- bpm   : 온셋 세기의 자기상관이 가장 큰 박 간격 (60–180 BPM 안, 절반 · 두 배 후보도 함께 보인다)
- meter : 박 간격의 3배 · 4배 지점 자기상관을 비교해 3박 / 4박 중 더 맞는 쪽
- key   : 곡 전체 크로마를 Krumhansl 장 · 단조 윤곽과 상관 비교한 상위 3개
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from melody_sim import chroma  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8', errors='replace')

NAMES = 'C C# D D# E F F# G G# A A# B'.split()
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def onset_env(path, hop=512):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    x = x.mean(axis=1)
    n = 2048
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    flux -= np.convolve(flux, np.ones(16) / 16, mode='same')   # 느린 세기 변화는 뺀다
    return np.maximum(flux, 0), sr / hop


def tempo(env, fps):
    ac = np.correlate(env, env, mode='full')[len(env) - 1:]
    ac /= ac[0]
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= 60) & (bpm <= 180)
    w = np.exp(-0.5 * (np.log2(bpm / 110) / 0.9) ** 2)   # 사람이 느끼는 박(110 BPM 근처)을 조금 더 친다
    cand = np.argsort(-(ac * w * ok))[:40]
    seen = []
    for c in cand:
        b = round(float(bpm[c]))
        if all(abs(b - s[0]) > 3 for s in seen):
            seen.append((b, round(float(ac[c]), 3), int(c)))
    beat = seen[0][2]
    m3 = ac[min(beat * 3, len(ac) - 1)]
    m4 = ac[min(beat * 4, len(ac) - 1)]
    return seen[:4], ('3' if m3 > m4 * 1.05 else '4', round(float(m3), 3), round(float(m4), 3))


def key(path):
    c, _ = chroma(path)
    p = c.mean(axis=0)
    scores = []
    for k in range(12):
        scores.append((float(np.corrcoef(p, np.roll(MAJOR, k))[0, 1]), f'{NAMES[k]} major'))
        scores.append((float(np.corrcoef(p, np.roll(MINOR, k))[0, 1]), f'{NAMES[k]} minor'))
    return sorted(scores, reverse=True)[:3]


for f in sys.argv[1:]:
    env, fps = onset_env(f)
    cands, meter = tempo(env, fps)
    print(Path(f).name)
    print('  bpm  ', '  '.join(f'{b}({a})' for b, a, _ in cands))
    print('  meter', meter[0], f'(3박 {meter[1]} / 4박 {meter[2]})')
    print('  key  ', '  '.join(f'{n} {s:.2f}' for s, n in key(f)))
