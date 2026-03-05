#!/bin/bash

echo "Fixing all remaining intptr_t definitions..."

find challenges -name "cgc_stdint.h" | while read file; do
  if grep -q "^typedef int intptr_t;$" "$file"; then
    echo "Fixing: $file"
    
    # Create backup
    cp "$file" "$file.bak"
    
    # Replace the intptr_t and uintptr_t definitions
    sed -i '/^typedef int intptr_t;$/,/^typedef unsigned int uintptr_t;$/ {
      s/^typedef int intptr_t;$/#ifdef __x86_64__\ntypedef long intptr_t;              \/\/ 64-bit: long is 64-bit\ntypedef unsigned long uintptr_t;\n#else\ntypedef int intptr_t;               \/\/ 32-bit: int is 32-bit\ntypedef unsigned int uintptr_t;\n#endif/
      /^typedef unsigned int uintptr_t;$/d
    }' "$file"
    
    # Verify the change
    if grep -q "#ifdef __x86_64__" "$file"; then
      echo "  ✓ Successfully fixed"
      rm "$file.bak"
    else
      echo "  ✗ Fix failed, restoring backup"
      mv "$file.bak" "$file"
    fi
  fi
done

echo ""
echo "Remaining files with old intptr_t:"
find challenges -name "cgc_stdint.h" -exec grep -l "^typedef int intptr_t;$" {} \; | wc -l
