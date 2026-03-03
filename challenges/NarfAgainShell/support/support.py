# Copyright (C) 2014 Narf Industries <info@narfindustries.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import random
import string
import struct
import platform

# On 64-bit systems, cgc_size_t is unsigned long (8 bytes).
# service.c reads sizeof(cgc_size_t) bytes for file sizes.
# On 32-bit systems, cgc_size_t is 4 bytes.
# MAX_FILE_SIZE = 4096 - 2 * sizeof(cgc_size_t)
if platform.architecture()[0] == '64bit':
    SIZE_FMT = '<Q'   # 8-byte little-endian unsigned
    MAX_FILE_SIZE_COMPUTED = 4096 - 2 * 8  # = 4080
else:
    SIZE_FMT = '<I'   # 4-byte little-endian unsigned
    MAX_FILE_SIZE_COMPUTED = 4096 - 2 * 4  # = 4088

class Support(object):
    MAX_FILE_NAME_LENGTH = 16
    MAX_FILE_SIZE = MAX_FILE_SIZE_COMPUTED

    def random_alpha(self, a, b):
        return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(a, b)))

    def __init__(self):
        self.files = {}

    def get_new_filename(self):
        name = self.random_alpha(1, self.MAX_FILE_NAME_LENGTH)
        return name if name not in self.files else self.get_new_filename()

    def get_new_contents(self):
        return self.random_alpha(1, self.MAX_FILE_SIZE)

    def get_filename(self):
        keys = list(self.files.keys())
        return random.choice(keys) if keys else None

    def read_file(self, name):
        if name in self.files:
            contents = self.files[name]
            if contents.startswith('link:'):
                return self.read_file(contents[5:])
            else:
                return contents
        else:
            return None

    def write_file(self, name, contents):
        if name not in self.files:
            self.files[name] = contents
            return True
        else:
            if self.files[name].startswith('link:'):
                return self.write_file(self.files[name][5:], contents)
            else:
                self.files[name] = contents
            return True

    def link_file(self, src, dst):
        return self.write_file(src, 'link:' + dst)

    def delete_file(self, name):
        del self.files[name]

    def pad_filename(self, name):
        padded = name + '\x00' * (self.MAX_FILE_NAME_LENGTH - len(name))
        return padded.encode('latin-1')

    def make_cd(self, name):
        return struct.pack('<I', 0) + self.pad_filename(name)

    def make_read_file(self, name):
        return struct.pack('<I', 1) + self.pad_filename(name)

    def make_write_file(self, name, length, contents):
        if isinstance(contents, str):
            contents = contents.encode('latin-1')
        return struct.pack('<I', 2) + self.pad_filename(name) + \
                struct.pack(SIZE_FMT, length) + contents

    def make_ln(self, src, dst):
        if isinstance(dst, str):
            dst = dst.encode('latin-1')
        return struct.pack('<I', 3) + self.pad_filename(src) + \
                struct.pack(SIZE_FMT, len(dst)) + dst

    def make_rm(self, name):
        return struct.pack('<I', 4) + self.pad_filename(name)

    def make_quit(self):
        return struct.pack('<i', -1)
