"""곡을 Qwen2-Audio 에게 들려 주고 구간마다 말로 설명을 받는다 (GPU 팟에서 실행 — transformers · librosa).

  python describe_audio.py voland_full.flac out.json 75-95 132-153 154-180 --chunks 30

Qwen2-Audio 는 한 번에 30초까지만 듣는다. 지정한 구간(초-초)과 곡 전체를 30초씩 자른 조각마다
같은 질문 여러 개를 묻고, 태그 질문은 샘플링으로 여러 번 물어 여러 번 나온 태그만 믿는다.
모델 설명은 세부(악기 수 · 언어 · 장르 이름)를 지어낼 수 있다 — 사람 귀와 대조하는 재료로 쓴다.
"""
import argparse, json, time
from collections import Counter

import librosa
import torch
from transformers import AutoProcessor, Qwen2AudioForConditionalGeneration

MODEL = 'Qwen/Qwen2-Audio-7B-Instruct'
QUESTIONS = {
    'describe': 'Describe this music in detail: genre, instrumentation, vocals (gender, choir or solo, singing style), '
                'tempo feel, rhythm, dynamics, mood and emotion.',
    'instruments': 'List every instrument and sound source you can hear in this clip, one per line, most prominent first.',
    'vocals': 'Describe the vocals: are they a choir or a soloist, male or female or mixed, what language, '
              'and how are they delivered (chanting, singing, shouting, whispering)?',
    'arc': 'How does the energy and emotion develop from the start to the end of this clip? Be specific about what changes.',
    'mood': 'In a few words, what feeling does this music give a listener? Is it calm, urgent, menacing, triumphant, sad, angry?',
}
TAGS_Q = ('Write a comma-separated list of 15 short music tags (as in a music tagging dataset) describing this clip: '
          'genre, instruments, vocal style, mood, tempo. Output only the tags.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio')
    ap.add_argument('out')
    ap.add_argument('sections', nargs='*', help='시작-끝 (초)')
    ap.add_argument('--chunks', type=int, default=30, help='곡 전체를 이 길이(초)로 잘라서도 묻는다 · 0 이면 안 한다')
    ap.add_argument('--tag-samples', type=int, default=4)
    a = ap.parse_args()

    proc = AutoProcessor.from_pretrained(MODEL)
    model = Qwen2AudioForConditionalGeneration.from_pretrained(MODEL, torch_dtype=torch.bfloat16, device_map='cuda').eval()
    sr = proc.feature_extractor.sampling_rate
    total = librosa.get_duration(path=a.audio)

    def ask(y, q, sample=False):
        conv = [{'role': 'user', 'content': [{'type': 'audio', 'audio_url': 'clip'}, {'type': 'text', 'text': q}]}]
        text = proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
        try:
            inputs = proc(text=text, audio=[y], sampling_rate=sr, return_tensors='pt', padding=True)
        except TypeError:   # 예전 transformers 는 audios=
            inputs = proc(text=text, audios=[y], sampling_rate=sr, return_tensors='pt', padding=True)
        inputs = inputs.to('cuda')
        kw = dict(do_sample=True, temperature=0.8, top_p=0.9) if sample else dict(do_sample=False)
        with torch.no_grad():
            ids = model.generate(**inputs, max_new_tokens=400, **kw)
        return proc.batch_decode(ids[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True)[0].strip()

    spans = []
    for s in a.sections:
        b, e = (float(x) for x in s.split('-'))
        spans.append(('section', b, min(e, total)))
    if a.chunks:
        t = 0.0
        while t < total - 3:
            spans.append(('chunk', t, min(t + a.chunks, total)))
            t += a.chunks

    results = []
    for kind, b, e in spans:
        y, _ = librosa.load(a.audio, sr=sr, offset=b, duration=min(30.0, e - b), mono=True)
        t0 = time.time()
        r = {'kind': kind, 'start': b, 'end': e, 'answers': {k: ask(y, q) for k, q in QUESTIONS.items()}}
        runs = [ask(y, TAGS_Q, sample=True) for _ in range(a.tag_samples)]
        cnt = Counter(t.strip().lower() for run in runs for t in run.split(',') if t.strip())
        r['tag_runs'] = runs
        r['tags'] = [t for t, n in cnt.most_common() if n >= max(2, a.tag_samples // 2)]
        r['took_sec'] = round(time.time() - t0, 1)
        results.append(r)
        print(f'{kind} {b:.0f}-{e:.0f}s ({r["took_sec"]}s): {", ".join(r["tags"][:10])}', flush=True)
        with open(a.out, 'w', encoding='utf-8') as f:   # 조각마다 저장 — 중간에 끊겨도 남는다
            json.dump({'model': MODEL, 'audio': a.audio, 'duration': total, 'results': results}, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
