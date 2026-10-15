#!/usr/bin/env bash
# exp4 — 원곡 참조 중심 (turbo 만 · 곡 설계도 끔). exp3 에서 태그만 준 곡은 전부 "바바예투" 였고,
# 클라이맥스를 denoise 0.25–0.4 로 따라간 곡만 3점이었다. 그 근처를 더 촘촘히 보고, 곡 전체 · 절로도 넓힌다.
set -u
G="python tools/ace_step.py"; C=latin_chant/config; R=latin_chant/ref; O=latin_chant/runs/exp4
# 1) 클라이맥스 — 최소 태그로 denoise 3단, 교회 전례 태그는 가운데 값만 (태그가 얼마나 끄는지)
for d in 0.3 0.35 0.45; do
  $G --prompts $C/exp4_climax.json --only c4_min --out $O --ref $R/voland_climax_132-180.flac --seconds 48 --denoise $d --seeds 1,2 --no-codes
done
$G --prompts $C/exp4_climax.json --only c4_sac --out $O --ref $R/voland_climax_132-180.flac --seconds 48 --denoise 0.35 --seeds 1,2 --no-codes
# 2) 원곡 전체 — 흐름 그대로 한 곡
for d in 0.3 0.4; do
  $G --prompts $C/exp4_full.json --out $O --ref $R/voland_full.flac --seconds 218 --denoise $d --seeds 1 --no-codes
done
# 3) 1:15–1:35 절
for d in 0.3 0.4; do
  $G --prompts $C/exp4_verse.json --out $O --ref $R/voland_a_075-095.flac --seconds 20 --denoise $d --seeds 1 --no-codes
done
