#!/usr/bin/env bash
# Kaggle에서 원본 데이터셋을 data/raw/ 로 내려받는다.
#
# 사전 준비 (최초 1회):
#   1) pip install kaggle   (또는 uv tool install kaggle)
#   2) kaggle.com → Settings → API → "Create New Token" → kaggle.json
#   3) mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
#
# CLI를 쓸 수 없으면: 데이터셋 페이지에서 zip을 직접 받아 data/raw/ 에 풀어도 된다.
# 압축 해제 시 archive/ 폴더가 한 단계 더 생겨도 ETL이 vct_* 폴더를 자동으로 찾는다.
set -euo pipefail

DATASET="ryanluong1/valorant-champion-tour-2021-2023-data"
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw"

# 이미 받은 데이터가 있으면 덮어쓰지 않는다: 재실행해도 안전하게 (멱등)
if find "$DEST" -maxdepth 2 -type d -name 'vct_*' | grep -q .; then
  echo "이미 데이터가 있습니다: $DEST (다시 받으려면 vct_* 폴더를 지우고 실행)"
  exit 0
fi

if ! command -v kaggle >/dev/null 2>&1; then
  echo "kaggle CLI가 없습니다. 스크립트 상단의 사전 준비를 먼저 진행하세요." >&2
  exit 1
fi

mkdir -p "$DEST"
kaggle datasets download -d "$DATASET" -p "$DEST" --unzip
echo "완료: $(find "$DEST" -name '*.csv' | wc -l | tr -d ' ')개 CSV → $DEST"
