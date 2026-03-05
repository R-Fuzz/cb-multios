#!/usr/bin/env python3
"""Decode the variable-length integer from the POV test"""

# The bytes from the XML: \x86\xd2\xaf\xb1\x5b
bytes_data = [0x86, 0xd2, 0xaf, 0xb1, 0x5b]

print(f"Decoding bytes: {' '.join(f'0x{b:02x}' for b in bytes_data)}")
print()

# Based on cgc_read_int() in io.c:79-95
b = bytes_data[0]
neg = b & 0x40
result = b & 0x3f

print(f"First byte: 0x{b:02x} = {b:08b}b")
print(f"  neg flag (bit 6): {neg != 0}")
print(f"  initial result (bits 0-5): {result}")
print(f"  continue flag (bit 7): {(b & 0x80) != 0}")
print()

i = 1
while (bytes_data[i-1] & 0x80):
    b = bytes_data[i]
    result = (result << 7) | (b & 0x7f)
    print(f"Byte {i}: 0x{b:02x} = {b:08b}b")
    print(f"  value bits: {b & 0x7f}")
    print(f"  result so far: {result}")
    print(f"  continue: {(b & 0x80) != 0}")
    print()
    i += 1

final_result = -result if neg else result

print(f"Final decoded value: {final_result}")
print(f"  In hex: 0x{abs(final_result):x}")
print(f"  In GB: {abs(final_result) / (1024**3):.3f} GB")
