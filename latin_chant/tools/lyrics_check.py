"""곡에서 실제로 불린 가사가 '자기 가사' 인지 '모체곡 가사' 인지 Whisper 로 받아 적어 잰다 (faster-whisper · ffmpeg 필요).

  python latin_chant/tools/lyrics_check.py latin_chant/config/lyrics.json latin_chant/runs/exp1/*.flac

- own : 받아 적은 글자 3-gram 중 이 곡 가사에만 있는(모체곡 가사에는 없는) 것의 비율
- mom : 받아 적은 글자 3-gram 중 모체곡 가사에만 있는 것의 비율
Whisper 가 라틴어 합창을 단어 단위로 끊어 적어서("noks desen ty" = nox descendit) 단어 대신 발음을 고른 글자 3-gram 으로 본다.
own 이 mom 보다 확실히 높으면 가사가 바뀐 것이다. 합창 · 잔향 탓에 절대값은 낮다 — 곡끼리 비교용.
"""
import json, re, subprocess, sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8', errors='replace')


def load(f):   # faster-whisper 의 PyAV 디코딩 대신 ffmpeg 로 16kHz 모노를 받는다
    raw = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', f, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def sound(s):
    """철자 차이를 줄인 발음 문자열 (교회 라틴어를 Whisper 가 적는 버릇에 맞춘다)."""
    s = re.sub(r'\[.*?\]', ' ', s.lower())
    s = re.sub(r'[^a-z]', '', s)
    for a, b in (('ae', 'e'), ('oe', 'e'), ('ph', 'f'), ('ch', 'k'), ('qu', 'k'), ('x', 'ks'), ('h', ''), ('j', 'i'), ('y', 'i'),
                 ('v', 'u'), ('w', 'u'), ('c', 'k'), ('q', 'k'), ('z', 's'), ('ki', 'si'), ('ke', 'se')):
        s = s.replace(a, b)
    return re.sub(r'(.)\1+', r'\1', s)


def grams(s):
    return [s[i:i + 3] for i in range(len(s) - 2)]


def main():
    prompts = {p['id']: p for p in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))}
    mom = prompts[next(k for k in prompts if k.startswith('m0'))]
    model = WhisperModel('small', device='cpu', compute_type='int8')
    print(f'{"곡":<32} {"own":>5} {"mom":>5}  받아 적은 앞부분')
    for f in sys.argv[2:]:
        p = prompts[re.match(r'(.+?)_(turbo|sft)_', Path(f).stem).group(1)]
        segs, _ = model.transcribe(load(f), language='la', vad_filter=False, beam_size=5)
        text = ' '.join(s.text for s in segs)
        heard = grams(sound(text))
        own_g, mom_g = set(grams(sound(p['lyrics']))), set(grams(sound(mom['lyrics'])))
        if p is not mom:
            own_g, mom_g = own_g - mom_g, mom_g - own_g
        own = sum(g in own_g for g in heard) / max(1, len(heard))
        mm = sum(g in mom_g for g in heard) / max(1, len(heard))
        print(f'{Path(f).stem:<32} {own:5.2f} {mm:5.2f}  {" ".join(text.split())[:80]}', flush=True)


if __name__ == '__main__':
    main()
