#!/bin/bash
find build64/challenges -type f -executable -name "*_patched" | while read binary; do
  if nm "$binary" 2>/dev/null | grep -q 'U cgc_\(sin\|cos\|tan\|sqrt\|log\|pow\|exp\|atan2\|fabs\|remainder\|scalbn\|rint\)'; then
    basename $(dirname "$binary")
  fi
done | sort -u
