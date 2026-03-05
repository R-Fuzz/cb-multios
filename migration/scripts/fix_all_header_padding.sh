#!/bin/bash

echo "Fixing all remaining HEADER_PADDING definitions..."

find challenges -name "cgc_malloc.h" | while read file; do
  if grep -q "^#define HEADER_PADDING 24$" "$file"; then
    echo "Fixing: $file"
    
    # Create backup
    cp "$file" "$file.bak"
    
    # Replace the HEADER_PADDING definition
    sed -i 's/^#define HEADER_PADDING 24$/#ifdef __x86_64__\n#define HEADER_PADDING 48  \/\/ 64-bit: sizeof(struct blk_t) = 48\n#else\n#define HEADER_PADDING 24  \/\/ 32-bit: sizeof(struct blk_t) = 24\n#endif/' "$file"
    
    # Verify the change
    if grep -q "#ifdef __x86_64__" "$file" && grep -q "HEADER_PADDING 48" "$file"; then
      echo "  ✓ Successfully fixed"
      rm "$file.bak"
    else
      echo "  ✗ Fix failed, restoring backup"
      mv "$file.bak" "$file"
    fi
  fi
done

echo ""
echo "Remaining files with old HEADER_PADDING:"
find challenges -name "cgc_malloc.h" -exec grep -l "^#define HEADER_PADDING 24$" {} \; | wc -l
