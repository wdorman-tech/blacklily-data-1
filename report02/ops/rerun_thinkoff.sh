#!/bin/sh
# The config arms were first run without --think, so every thinking-capable model spent its
# generation budget on reasoning tokens. Those runs are quarantined in runs/_invalid_thinkon.
# This reruns them with the same setting as the main arm.
cd "$(dirname "$0")/.."
PY=../.venv/Scripts/python.exe
until [ -f runs/gemma4-12b/t3/test-mapreduce-ctx16384-r1/_manifest.json ]; do sleep 20; done
for c in 2048 4096 8192 32768; do
  $PY src/run.py --task t1 --model gemma4:12b --split test --run r1 --think off --num-ctx $c
done
for c in 4096 8192 16384 32768; do
  $PY src/run.py --task t3 --model gemma4:12b --split test --run r1 --think off --variant fullpack --num-ctx $c
done
for t in t1 t3; do
  $PY src/run.py --task $t --model qwen3.5:9b-q8_0 --split test --run r1 --think off
done
echo "=== thinkoff reruns done"
