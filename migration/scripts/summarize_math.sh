#!/bin/bash
echo "=== Math Function Usage Summary from maths64.S ==="
echo ""
echo "Function usage counts across all binaries in build64/:"
echo ""

for func in sin cos tan sqrt log log10 log2 pow exp exp2 atan2 fabs remainder scalbn rint significand; do
  count=$(find build64/challenges -type f -executable -name "*_patched" -exec nm {} 2>/dev/null \; | grep "U cgc_${func}$" | wc -l)
  printf "%-15s: %3d binaries\n" "cgc_$func" "$count"
done | sort -t: -k2 -rn

echo ""
echo "Total unique challenges using maths64.S functions:"
find build64/challenges -type f -executable -name "*_patched" | while read binary; do
  if nm "$binary" 2>/dev/null | grep -q 'U cgc_\(sin\|cos\|tan\|sqrt\|log\|pow\|exp\|atan2\|fabs\|remainder\|scalbn\|rint\)'; then
    basename $(dirname "$binary")
  fi
done | sort -u | wc -l
