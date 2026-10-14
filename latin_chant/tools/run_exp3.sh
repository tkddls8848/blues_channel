#!/usr/bin/env bash
# exp3 — exp2 가 전부 "바바 예투" 처럼 밝고 웅장하게 나와서 원인을 가른다 (turbo 만).
#   ① 원곡 참조 곡에서 언어 모델의 곡 설계도(audio codes)를 끄면 원곡에 더 붙는가
#   ② 북 · 행진 · triumphant · eastern 을 빼고 교회 전례(오르간 · 정교회 저음 합창 · 종 · Dies irae) 태그로 기독교 종말론의 울분이 나오는가
set -u
G="python tools/ace_step.py"; C=latin_chant/config; R=latin_chant/ref; O=latin_chant/runs/exp3
for d in 0.25 0.4 0.55; do
  $G --prompts $C/exp3_nocodes.json --out $O --ref $R/voland_climax_132-180.flac --seconds 48 --denoise $d --seeds 1 --no-codes
done
$G --prompts $C/exp3_codes.json --out $O --ref $R/voland_climax_132-180.flac --seconds 48 --denoise 0.25 --seeds 1
$G --prompts $C/exp3_text.json --out $O --seconds 150 --seeds 1,2
