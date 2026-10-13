"""ACE-Step 1.5 XL 로 연주곡을 만든다 (gpu-art 음악 팟의 ComfyUI, 파이썬 표준 라이브러리만).

  python tools/ace_step.py --prompts config/phase0_prompts.json --out runs/phase0
  python tools/ace_step.py --prompts config/phase0_prompts.json --out runs/phase0 --model sft --only blues_slow_bar,piano_nocturne

음악 팟은 remote_coding/gpu-art 로 켠다(README "음악 팟"). 터널 주소는 COMFY_URL(기본 http://127.0.0.1:8189).
곡마다 <id>_<model>_s<seed>.flac 과 같은 이름의 .json(프롬프트 · 모델 · 시드 · 걸린 시간)을 남긴다.
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request, uuid
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8', errors='replace')

URL = os.environ.get('COMFY_URL', 'http://127.0.0.1:8189')

# ComfyUI 공식 템플릿(audio_ace_step1_5_xl_turbo / _xl_sft)과 같은 설정
MODELS = {
    'turbo': {'unet': 'acestep_v1.5_xl_turbo_bf16.safetensors', 'steps': 8, 'cfg': 1.0},
    'sft': {'unet': 'acestep_v1.5_xl_sft_bf16.safetensors', 'steps': 50, 'cfg': 7.0},
}


def http(path, body=None, timeout=60):
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw if path.startswith('/view') else json.loads(raw)


def workflow(p, model, seed, seconds):
    m = MODELS[model]
    return {
        'unet': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['unet'], 'weight_dtype': 'default'}},
        'sampling': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['unet', 0], 'shift': 3}},
        'clip': {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': 'qwen_0.6b_ace15.safetensors',
                                                            'clip_name2': 'qwen_4b_ace15.safetensors', 'type': 'ace', 'device': 'default'}},
        'vae': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'ace_1.5_vae.safetensors'}},
        'text': {'class_type': 'TextEncodeAceStepAudio1.5', 'inputs': {
            'clip': ['clip', 0], 'tags': p['tags'], 'lyrics': '[Instrumental]', 'seed': seed,
            'bpm': p['bpm'], 'duration': float(seconds), 'timesignature': p.get('timesignature', '4'),
            'language': 'en', 'keyscale': p['keyscale'], 'generate_audio_codes': True,
            'cfg_scale': 2.0, 'temperature': 0.85, 'top_p': 0.9, 'top_k': 0, 'min_p': 0.0}},
        'neg': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['text', 0]}},
        'latent': {'class_type': 'EmptyAceStep1.5LatentAudio', 'inputs': {'seconds': float(seconds), 'batch_size': 1}},
        'sampler': {'class_type': 'KSampler', 'inputs': {
            'model': ['sampling', 0], 'positive': ['text', 0], 'negative': ['neg', 0], 'latent_image': ['latent', 0],
            'seed': seed, 'steps': m['steps'], 'cfg': m['cfg'], 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        'decode': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['sampler', 0], 'vae': ['vae', 0]}},
        'save': {'class_type': 'SaveAudio', 'inputs': {'audio': ['decode', 0], 'filename_prefix': f'lonely_blues/{p["id"]}_{model}_s{seed}'}},
    }


def check_nodes():
    """보낼 노드 입력 이름이 서버의 ComfyUI 와 맞는지 먼저 본다 — 판이 바뀌면 여기서 멈춘다."""
    info = http('/object_info', timeout=120)
    wf = workflow({'id': 'x', 'tags': '', 'bpm': 60, 'keyscale': 'C major'}, 'turbo', 0, 10)
    bad = []
    for node in wf.values():
        spec = info.get(node['class_type'])
        if not spec:
            bad.append(f'{node["class_type"]}: 서버에 없는 노드')
            continue
        known = set(spec['input'].get('required', {})) | set(spec['input'].get('optional', {}))
        bad += [f'{node["class_type"]}.{k}: 없는 입력 (있는 것: {sorted(known)})' for k in node['inputs'] if k not in known]
    if bad:
        sys.exit('노드 입력이 서버와 다르다:\n  ' + '\n  '.join(bad))


def run(p, model, seed, seconds, out):
    stem = f'{p["id"]}_{model}_s{seed}'
    if (out / f'{stem}.flac').exists():
        print(f'  -- 있음 {stem}')
        return
    t0 = time.time()
    r = http('/prompt', {'prompt': workflow(p, model, seed, seconds), 'client_id': uuid.uuid4().hex})
    pid = r['prompt_id']
    while True:
        h = http(f'/history/{pid}').get(pid)
        if h and h.get('status', {}).get('completed'):
            break
        if h and h.get('status', {}).get('status_str') == 'error':
            sys.exit(f'생성 실패 {stem}: {json.dumps(h["status"], ensure_ascii=False)[:800]}')
        time.sleep(3)
    files = [a for o in h['outputs'].values() for a in o.get('audio', [])]
    for a in files:
        q = urllib.parse.urlencode({'filename': a['filename'], 'subfolder': a.get('subfolder', ''), 'type': a.get('type', 'output')})
        (out / f'{stem}.flac').write_bytes(http(f'/view?{q}', timeout=300))
    took = round(time.time() - t0, 1)
    meta = {**p, 'model': model, 'unet': MODELS[model]['unet'], 'steps': MODELS[model]['steps'], 'seed': seed,
            'seconds': seconds, 'took_sec': took, 'generator': 'ACE-Step 1.5 XL (MIT)', 'created': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (out / f'{stem}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ok {stem} ({took}초)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompts', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--model', default='turbo', choices=list(MODELS))
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--seeds', default='1', help='쉼표로 여러 개 (곡마다 시드 수만큼 만든다)')
    ap.add_argument('--only', default='', help='쉼표로 고른 id 만')
    a = ap.parse_args()
    prompts = json.loads(Path(a.prompts).read_text(encoding='utf-8'))
    if a.only:
        keep = set(a.only.split(','))
        prompts = [p for p in prompts if p['id'] in keep]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    check_nodes()
    seeds = [int(s) for s in a.seeds.split(',')]
    print(f'==> {len(prompts)}곡 × 시드 {len(seeds)}개 · {a.model} · {a.seconds}초 → {out}')
    for p in prompts:
        for s in seeds:
            run(p, a.model, s, a.seconds, out)


if __name__ == '__main__':
    main()
