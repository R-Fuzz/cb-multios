#!/bin/bash
echo "Challenge,sin,cos,tan,sqrt,log,log10,log2,pow,exp,exp2,atan2,fabs,remainder,scalbn,rint,significand"
find build64/challenges -type f -executable -name "*_patched" | while read binary; do
  challenge=$(basename $(dirname "$binary"))
  symbols=$(nm "$binary" 2>/dev/null | grep 'U cgc_' | awk '{print $2}' | sort -u)
  
  if echo "$symbols" | grep -q 'cgc_\(sin\|cos\|tan\|sqrt\|log\|pow\|exp\|atan2\|fabs\|remainder\|scalbn\|rint\)'; then
    result="$challenge"
    for func in sin cos tan sqrt log log10 log2 pow exp exp2 atan2 fabs remainder scalbn rint significand; do
      if echo "$symbols" | grep -q "cgc_${func}$"; then
        result="$result,X"
      else
        result="$result,"
      fi
    done
    echo "$result"
  fi
done | sort
