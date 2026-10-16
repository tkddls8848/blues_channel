"""Quote, resume Veo image-to-video jobs, then edit with the supplied song.

No generation happens by default. A positive approved --budget-usd is required.
Key stays in .env or the process environment and is never written to job state.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = ''
sys.path.insert(0, str(ROOT / '.tools'))
RATES = {'veo-3.1-lite-generate-preview': Decimal('0.05'),
         'veo-3.1-fast-generate-preview': Decimal('0.10'),
         'veo-3.1-generate-preview': Decimal('0.40')}


def settings():
    values = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                values[name.strip()] = value.strip().strip('\"').strip("'")
    for name in ['GEMINI_API_KEY', 'GOOGLE_API_KEY', 'VEO_MODEL',
                 'VEO_RESOLUTION', 'VEO_MAX_BUDGET_USD']:
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def safe_error(error, key):
    return re.sub(r'AIza[A-Za-z0-9_-]+', '[REDACTED]', str(error).replace(key, '[REDACTED]') if key else str(error))


def resolve_local(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Job media must stay inside flows/')
    return path


def job_info(shot, model):
    image = resolve_local(shot['image'])
    if not image.is_file():
        raise ValueError(f"Missing image for shot {shot['id']}")
    fingerprint = hashlib.sha256((model + '\n' + json.dumps(shot, sort_keys=True) +
                                  hashlib.sha256(image.read_bytes()).hexdigest()).encode()).hexdigest()
    return image, fingerprint


def paths(model, resolution, shot_id):
    group = model.replace('-generate-preview', '') + '-' + resolution
    if RUN_ID:
        group += '-' + RUN_ID
    return (ROOT / 'runs' / group / f'shot-{shot_id}.json',
            ROOT / 'clips' / group / f'shot-{shot_id}.mp4')


def estimate(shots, model):
    return sum((RATES[model] * s['generation_seconds'] for s in shots), Decimal(0))


def quote(config, shots, model, resolution):
    for shot in shots:
        job_info(shot, model)
    summary = {'model': model, 'resolution': resolution,
               'shots': [{'id': s['id'], 'generated_seconds': s['generation_seconds'],
                          'edit_seconds': s['trim_seconds'],
                          'estimated_usd': str(RATES[model] * s['generation_seconds'])} for s in shots],
               'generated_seconds': sum(s['generation_seconds'] for s in shots),
               'edit_seconds': sum(s['trim_seconds'] for s in shots),
               'estimated_usd': str(estimate(shots, model)),
               'rate_source': 'https://ai.google.dev/gemini-api/docs/pricing',
               'generation_requests_sent': 0}
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def generate(config, shots, model, resolution, budget, env, poll_limit):
    # Budget and all local assets are checked before constructing a client.
    for shot in shots:
        job_info(shot, model)
    all_state = []
    for path in paths(model, resolution, '01')[0].parent.glob('shot-*.json'):
        all_state.append(json.loads(path.read_text(encoding='utf-8')))
    reserved = sum((Decimal(s['reserved_usd']) for s in all_state), Decimal(0))
    fresh = [s for s in shots if not paths(model, resolution, s['id'])[0].exists()]
    if budget <= 0 or reserved + estimate(fresh, model) > budget:
        raise ValueError(f'No request sent: estimated cumulative reservation ${reserved + estimate(fresh, model)} exceeds approved budget ${budget}.')
    key = env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY')
    if not key or key.startswith('replace_'):
        raise ValueError('Set GEMINI_API_KEY in flows/.env. Do not put it in CLI arguments.')
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(
        timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        for shot in shots:
            state_path, output = paths(model, resolution, shot['id'])
            image, fingerprint = job_info(shot, model)
            state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
            if state and state['fingerprint'] != fingerprint:
                raise ValueError(f"Shot {shot['id']} inputs changed. Keep the existing paid job; use a new reviewed version.")
            if state and state.get('status') == 'complete' and output.is_file():
                print(f"Shot {shot['id']}: existing local result reused; no new request.", flush=True)
                continue
            if state:
                if not state.get('operation'):
                    raise ValueError(f"Shot {shot['id']}: ambiguous/failed submission requires review; no automatic resubmission.")
                operation = client.operations.get(types.GenerateVideosOperation(name=state['operation']))
            else:
                state = {'shot': shot['id'], 'fingerprint': fingerprint, 'model': model,
                         'resolution': resolution, 'reserved_usd': str(RATES[model] * shot['generation_seconds']),
                         'status': 'submitting', 'output': str(output.relative_to(ROOT))}
                # Persist before POST. A transport error must never blindly generate again.
                write_json(state_path, state)
                print(f"Shot {shot['id']}: submitting {shot['generation_seconds']}s; estimated ${state['reserved_usd']}.", flush=True)
                operation = client.models.generate_videos(model=model,
                    source=types.GenerateVideosSource(prompt=shot['prompt'],
                        image=types.Image.from_file(location=str(image))),
                    config=types.GenerateVideosConfig(aspect_ratio='16:9', resolution=resolution,
                        duration_seconds=shot['generation_seconds'], number_of_videos=1,
                        person_generation='allow_adult', negative_prompt=shot.get('negative_prompt')))
                if not operation.name:
                    raise ValueError(f"Shot {shot['id']}: server returned no operation name; review required.")
                state.update(operation=operation.name, status='generating')
                write_json(state_path, state)
            started = time.monotonic()
            while not operation.done:
                if time.monotonic() - started > poll_limit:
                    raise TimeoutError(f"Shot {shot['id']} is still generating. Re-run the same command to poll, without a new paid request.")
                time.sleep(10)
                operation = client.operations.get(operation)
                print(f"Shot {shot['id']}: {'ready' if operation.done else 'generating'}.", flush=True)
            if operation.error:
                state.update(status='server_error', error=safe_error(operation.error, key))
                write_json(state_path, state)
                raise RuntimeError(state['error'])
            videos = getattr(operation.response, 'generated_videos', None)
            if not videos:
                state.update(status='no_video', error='Server returned no generated video. Review filters; no automatic retry.')
                write_json(state_path, state)
                raise RuntimeError(state['error'])
            output.parent.mkdir(parents=True, exist_ok=True)
            part = output.with_suffix('.part.mp4')
            client.files.download(file=videos[0].video, destination=str(part))
            if not part.is_file() or not part.stat().st_size:
                raise RuntimeError('Video download was empty; re-run to download the same operation.')
            part.replace(output)
            state.update(status='complete')
            write_json(state_path, state)
            print(f"Shot {shot['id']}: saved {output.relative_to(ROOT)}", flush=True)
    except Exception as error:
        raise RuntimeError(safe_error(error, key)) from None
    finally:
        client.close()


def render(config, model, resolution):
    shots = config['shots']
    audio = resolve_local(config['song']['audio'])
    inputs = [paths(model, resolution, s['id'])[1] for s in shots]
    missing = [str(p.relative_to(ROOT)) for p in [audio, *inputs] if not p.is_file()]
    if missing:
        raise ValueError('Missing media; no still-image fallback: ' + ', '.join(missing))
    group = model.replace('-generate-preview', '') + '-' + resolution
    if RUN_ID:
        group += '-' + RUN_ID
    folder = ROOT / 'renders' / group
    folder.mkdir(parents=True, exist_ok=True)
    normalized = []
    for shot, source in zip(shots, inputs):
        target = folder / f"edit-{shot['id']}.mp4"
        speed = float(shot.get('playback_speed', 1))
        if speed <= 0 or shot['trim_seconds'] * speed > shot['generation_seconds'] + 0.001:
            raise ValueError(f"Shot {shot['id']}: edit requires more frames than the generated source.")
        filters = f'scale=1280:720,setsar=1,setpts=(PTS-STARTPTS)/{speed},fps=24'
        sharpness = float(config.get('render_sharpen', 0))
        if not 0 <= sharpness <= 1:
            raise ValueError('Render sharpening must stay between 0 and 1.')
        if sharpness:
            filters += f',unsharp=3:3:{sharpness}:3:3:0'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
            '-t', str(shot['trim_seconds']), '-an', '-vf', filters,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', str(target)], check=True)
        normalized.append(target)
    concat = folder / 'concat.txt'
    concat.write_text(''.join(f"file '{p.name}'\n" for p in normalized), encoding='utf-8')
    duration = sum(s['trim_seconds'] for s in shots)
    if duration != config['song']['end'] - config['song']['start']:
        raise ValueError('Edited duration must match the exact song segment.')
    final = folder / f"bakkuo-{config['song']['start']}-{config['song']['end']}.mp4"
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
        '-i', str(concat), '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k', '-t', str(duration), '-movflags', '+faststart', str(final)], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration:stream=codec_type,width,height', '-of', 'json', str(final)], text=True))
    if abs(float(probe['format']['duration']) - duration) > 0.1:
        raise ValueError('Final duration differs from the planned song segment.')
    if {s['codec_type'] for s in probe['streams']} != {'video', 'audio'}:
        raise ValueError('Final requires both the generated video and original song audio.')
    write_json(folder / 'render-info.json', {'file': str(final.relative_to(ROOT)), 'probe': probe,
        'song': config['song'], 'music_climax_at_video_second': 170 - config['song']['start'],
        'source': 'Veo generated video clips; no still-image fallback'})
    print(str(final), flush=True)


def main():
    global RUN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['quote', 'generate', 'render'])
    parser.add_argument('--shots', help='Comma-separated shot IDs; defaults to all six')
    parser.add_argument('--budget-usd', type=Decimal, help='Explicit approved cumulative budget; overrides the .env cap')
    parser.add_argument('--poll-limit', type=int, default=600)
    parser.add_argument('--jobs', default='veo-jobs.json', help='Local reviewed job manifest relative to flows/')
    args = parser.parse_args()
    env = settings()
    config = json.loads(resolve_local(args.jobs).read_text(encoding='utf-8'))
    RUN_ID = config.get('run_id', '')
    if RUN_ID and not re.fullmatch(r'[A-Za-z0-9_-]+', RUN_ID):
        raise ValueError('Invalid run identifier')
    model = env.get('VEO_MODEL', 'veo-3.1-fast-generate-preview')
    resolution = env.get('VEO_RESOLUTION', '720p')
    if model not in RATES or resolution != '720p':
        raise ValueError('This reviewed cost plan supports the listed Veo 3.1 models at 720p only.')
    chosen = set(args.shots.split(',')) if args.shots else {s['id'] for s in config['shots']}
    shots = [s for s in config['shots'] if s['id'] in chosen]
    if len(shots) != len(chosen):
        raise ValueError('Unknown or empty shot selection')
    if args.command == 'quote':
        quote(config, shots, model, resolution)
    elif args.command == 'generate':
        budget = args.budget_usd if args.budget_usd is not None else Decimal(env.get('VEO_MAX_BUDGET_USD', '0'))
        generate(config, shots, model, resolution, budget, env, args.poll_limit)
    else:
        if args.shots:
            raise ValueError('Render uses all shots in the selected manifest; do not pass --shots.')
        render(config, model, resolution)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Stopped: ' + safe_error(error, settings().get('GEMINI_API_KEY', '')), file=sys.stderr)
        sys.exit(1)
