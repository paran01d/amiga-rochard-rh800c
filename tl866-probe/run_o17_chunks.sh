#!/bin/bash
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
CH=16384
for i in 0 1 2 3 4 5 6 7; do
  s=$((i*CH)); e=$((s+CH-1))
  "$PY" gen_vectors.py u11o17 --start $s --end $e -o o17_c${i}.xml >/dev/null 2>&1
  ok=0
  for try in 1 2 3; do
    if minipro -p "U11O17_ONLY" -T --logicic o17_c${i}.xml --logicic_out o17_c${i}_meas.xml >/dev/null 2>&1; then
      ok=1; break
    fi
    echo "chunk $i try $try FAILED, retrying"; sleep 3
  done
  [ $ok -eq 1 ] && echo "chunk $i OK ($s..$e)" || { echo "chunk $i GAVE UP"; }
  sleep 2
done
echo "ALL CHUNKS DONE"
