"""ACE-Step 1.5 XL 로 곡을 만든다 (gpu-art 음악 팟의 ComfyUI, 파이썬 표준 라이브러리만).

  python tools/ace_step.py --prompts lonely_blues/config/phase0_prompts.json --out lonely_blues/runs/phase0
  python tools/ace_step.py --prompts lonely_blues/config/phase0_prompts.json --out lonely_blues/runs/phase0 --model sft --only blues_slow_bar,piano_nocturne
  python tools/ace_step.py --prompts latin_chant/config/lyrics.json --out latin_chant/runs/exp1 --ref mother.flac --denoise 0.6

프롬프트 항목에 lyrics · language 가 있으면 가사곡이 되고, 없으면 연주곡([Instrumental], en)이다.
--ref 를 주면 그 곡을 VAE 로 인코딩해 출발점으로 쓴다(audio-to-audio) — denoise 가 낮을수록 원래 곡에 가깝다.

음악 팟은 remote_coding/gpu-art 로 켠다(README "음악 팟"). 터널 주소는 COMFY_URL(기본 http://127.0.0.1:8189).
곡마다 <id>_<model>_s<seed>.flac 과 같은 이름의 .json(프롬프트 · 모델 · 시드 · 걸린 시간)을 남긴다.
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request, uuid
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


def workflow(p, model, seed, seconds, ref=None, denoise=1.0, codes=True):
    m = MODELS[model]
    wf = {
        'unet': {'class_type': 'UNETLoader', 'inputs': {'unet_name': m['unet'], 'weight_dtype': 'default'}},
        'sampling': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['unet', 0], 'shift': 3}},
        'clip': {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': 'qwen_0.6b_ace15.safetensors',
                                                            'clip_name2': 'qwen_4b_ace15.safetensors', 'type': 'ace', 'device': 'default'}},
        'vae': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'ace_1.5_vae.safetensors'}},
        'text': {'class_type': 'TextEncodeAceStepAudio1.5', 'inputs': {
            'clip': ['clip', 0], 'tags': p['tags'], 'lyrics': p.get('lyrics', '[Instrumental]'), 'seed': seed,
            'bpm': p['bpm'], 'duration': float(seconds), 'timesignature': p.get('timesignature', '4'),
            'language': p.get('language', 'en'), 'keyscale': p['keyscale'], 'generate_audio_codes': codes,
            'cfg_scale': 2.0, 'temperature': 0.85, 'top_p': 0.9, 'top_k': 0, 'min_p': 0.0}},
        'neg': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['text', 0]}},
        'latent': {'class_type': 'EmptyAceStep1.5LatentAudio', 'inputs': {'seconds': float(seconds), 'batch_size': 1}},
        'sampler': {'class_type': 'KSampler', 'inputs': {
            'model': ['sampling', 0], 'positive': ['text', 0], 'negative': ['neg', 0], 'latent_image': ['latent', 0],
            'seed': seed, 'steps': m['steps'], 'cfg': m['cfg'], 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': denoise}},
        'decode': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['sampler', 0], 'vae': ['vae', 0]}},
        'save': {'class_type': 'SaveAudio', 'inputs': {'audio': ['decode', 0], 'filename_prefix': f'ace_step/{stem(p, model, seed, ref, denoise)}'}},
    }
    if ref:   # 빈 잠재 대신 참조 곡을 인코딩한 잠재에서 출발한다
        wf['ref'] = {'class_type': 'LoadAudio', 'inputs': {'audio': ref}}
        wf['latent'] = {'class_type': 'VAEEncodeAudio', 'inputs': {'audio': ['ref', 0], 'vae': ['vae', 0]}}
    return wf


def stem(p, model, seed, ref=None, denoise=1.0):
    return f'{p["id"]}_{model}_s{seed}' + (f'_ref_d{round(denoise * 100)}' if ref else '')


def upload(path):
    """참조 곡을 ComfyUI input/ 으로 올리고 LoadAudio 가 쓸 파일 이름을 돌려준다."""
    path = Path(path)
    b = uuid.uuid4().hex
    head = (f'--{b}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n')
    body = head.encode() + path.read_bytes() + f'\r\n--{b}--\r\n'.encode()
    req = urllib.request.Request(URL + '/upload/image', data=body, headers={'Content-Type': f'multipart/form-data; boundary={b}'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())['name']


def combo_options(spec):
    """object_info 의 입력 정의에서 고를 수 있는 값 목록 (고르는 입력이 아니면 None)."""
    t = spec[0] if isinstance(spec, list) and spec else None
    if isinstance(t, list):
        return t
    if t == 'COMBO' and len(spec) > 1:
        return spec[1].get('options')
    return None


def check_nodes(prompts, model, seconds, ref=None):
    """보낼 노드 입력 이름 · 고르는 값(키 · 박자 등)이 서버의 ComfyUI 와 맞는지 먼저 본다 — 하나라도 틀리면 GPU 를 쓰기 전에 멈춘다."""
    info = http('/object_info', timeout=120)
    bad = []
    for p in prompts:
        for node in workflow(p, model, 0, seconds, ref).values():
            spec = info.get(node['class_type'])
            if not spec:
                bad.append(f'{node["class_type"]}: 서버에 없는 노드')
                continue
            known = {**spec['input'].get('required', {}), **spec['input'].get('optional', {})}
            for k, v in node['inputs'].items():
                if k not in known:
                    bad.append(f'{node["class_type"]}.{k}: 없는 입력 (있는 것: {sorted(known)})')
                elif not isinstance(v, list) and (opts := combo_options(known[k])) is not None and v not in opts:
                    bad.append(f'{p["id"]}: {node["class_type"]}.{k}={v!r} 는 고를 수 없는 값 (예: {opts[:8]})')
    if bad:
        sys.exit('서버와 맞지 않는다:\n  ' + '\n  '.join(dict.fromkeys(bad)))


def run(p, model, seed, seconds, out, ref=None, denoise=1.0, codes=True):
    name = stem(p, model, seed, ref, denoise)
    if (out / f'{name}.flac').exists():
        print(f'  -- 있음 {name}')
        return
    t0 = time.time()
    try:
        r = http('/prompt', {'prompt': workflow(p, model, seed, seconds, ref, denoise, codes), 'client_id': uuid.uuid4().hex})
    except urllib.error.HTTPError as e:   # 400 이면 ComfyUI 가 어느 입력이 틀렸는지 본문에 적어 준다
        return f'{name}: /prompt {e.code} {e.read().decode("utf-8", "replace")[:800]}'
    pid = r['prompt_id']
    while True:
        h = http(f'/history/{pid}').get(pid)
        if h and h.get('status', {}).get('completed'):
            break
        if h and h.get('status', {}).get('status_str') == 'error':
            return f'{name}: {json.dumps(h["status"], ensure_ascii=False)[:800]}'
        time.sleep(3)
    files = [a for o in h['outputs'].values() for a in o.get('audio', [])]
    for a in files:
        q = urllib.parse.urlencode({'filename': a['filename'], 'subfolder': a.get('subfolder', ''), 'type': a.get('type', 'output')})
        (out / f'{name}.flac').write_bytes(http(f'/view?{q}', timeout=300))
    took = round(time.time() - t0, 1)
    meta = {**p, 'model': model, 'unet': MODELS[model]['unet'], 'steps': MODELS[model]['steps'], 'seed': seed,
            'seconds': seconds, 'ref': ref, 'denoise': denoise, 'audio_codes': codes, 'took_sec': took, 'generator': 'ACE-Step 1.5 XL (MIT)', 'created': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (out / f'{name}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ok {name} ({took}초)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompts', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--model', default='turbo', choices=list(MODELS))
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--seeds', default='1', help='쉼표로 여러 개 (곡마다 시드 수만큼 만든다)')
    ap.add_argument('--only', default='', help='쉼표로 고른 id 만')
    ap.add_argument('--ref', help='출발점으로 쓸 참조 곡 (audio-to-audio)')
    ap.add_argument('--denoise', type=float, default=1.0, help='--ref 와 함께 — 낮을수록 참조 곡에 가깝다')
    ap.add_argument('--no-codes', action='store_true', help='언어 모델의 오디오 코드(곡 설계) 생성을 끈다')
    a = ap.parse_args()
    prompts = json.loads(Path(a.prompts).read_text(encoding='utf-8'))
    if a.only:
        keep = set(a.only.split(','))
        prompts = [p for p in prompts if p['id'] in keep]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ref = upload(a.ref) if a.ref else None
    check_nodes(prompts, a.model, a.seconds, ref)
    seeds = [int(s) for s in a.seeds.split(',')]
    print(f'==> {len(prompts)}곡 × 시드 {len(seeds)}개 · {a.model} · {a.seconds}초' + (f' · 참조 {ref} denoise {a.denoise}' if ref else '') + f' → {out}')
    failed = [f for p in prompts for s in seeds if (f := run(p, a.model, s, a.seconds, out, ref, a.denoise, not a.no_codes))]   # 한 곡이 실패해도 나머지는 만든다
    for f in failed:
        print('  xx ' + f, file=sys.stderr)
    if failed:
        sys.exit(f'{len(failed)}곡 실패')


if __name__ == '__main__':
    main()
