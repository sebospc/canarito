"""Minimal QR code: byte mode, error correction M, versions 1 to 13 (up to 331 bytes). Enough for a
pairing URL; stdlib only, so `canarito.py pair` needs nothing installed."""
import struct
import zlib

# version -> (error correction codewords per block, [(blocks, data codewords per block), ...])
BLOCKS_M = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]),
    5: (24, [(2, 43)]), 6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]),
    9: (22, [(3, 36), (2, 37)]), 10: (26, [(4, 43), (1, 44)]), 11: (30, [(1, 50), (4, 51)]),
    12: (22, [(6, 36), (2, 37)]), 13: (22, [(8, 37), (1, 38)]),
}
ALIGNMENT = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38],
             8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58],
             13: [6, 34, 62]}


def _exp_log():
    exp, log, value = [0] * 512, [0] * 256, 1
    for i in range(255):
        exp[i], log[value] = value, i
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


EXP, LOG = _exp_log()


def _multiply(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def _reed_solomon(data, degree):
    generator = [1]
    for i in range(degree):
        next_generator = [0] * (len(generator) + 1)
        for j, coefficient in enumerate(generator):
            next_generator[j] ^= coefficient
            next_generator[j + 1] ^= _multiply(coefficient, EXP[i])
        generator = next_generator
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder.pop(0)
        remainder.append(0)
        for i in range(degree):
            remainder[i] ^= _multiply(generator[i + 1], factor)
    return remainder


def _codewords(data, version):
    ec_size, groups = BLOCKS_M[version]
    capacity = sum(count * size for count, size in groups)
    bits = "0100" + format(len(data), "08b" if version < 10 else "016b") + "".join(format(b, "08b") for b in data)
    bits += "0" * min(4, capacity * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    padded = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    padded += [(0xEC, 0x11)[i % 2] for i in range(capacity - len(padded))]
    blocks, position = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(padded[position:position + size])
            position += size
    ecs = [_reed_solomon(block, ec_size) for block in blocks]
    out = [block[i] for i in range(max(map(len, blocks))) for block in blocks if i < len(block)]
    return out + [ec[i] for i in range(ec_size) for ec in ecs]


def _bch(value, generator, bits):
    shifted = value << bits
    for i in range(shifted.bit_length() - 1, bits - 1, -1):
        if shifted >> i & 1:
            shifted ^= generator << (i - bits)
    return shifted


class _Matrix:
    def __init__(self, version):
        self.size = version * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.is_function = [[False] * self.size for _ in range(self.size)]
        size = self.size
        for i in range(size):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for x, y in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    if 0 <= x + dx < size and 0 <= y + dy < size:
                        self.set(x + dx, y + dy, max(abs(dx), abs(dy)) not in (2, 4))
        centers = ALIGNMENT[version]
        for i, cx in enumerate(centers):
            for j, cy in enumerate(centers):
                if (i, j) in ((0, 0), (0, len(centers) - 1), (len(centers) - 1, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0)
        if version >= 7:
            info = version << 12 | _bch(version, 0x1F25, 12)
            for i in range(18):
                bit = info >> i & 1 == 1
                a, b = size - 11 + i % 3, i // 3
                self.set(a, b, bit)
                self.set(b, a, bit)

    def set(self, x, y, dark):
        self.modules[y][x] = dark
        self.is_function[y][x] = True

    def draw_format(self, mask):
        data = mask  # error correction M is 00
        bits = (data << 10 | _bch(data, 0x537, 10)) ^ 0x5412
        size = self.size
        bit = lambda i: bits >> i & 1 == 1
        for i in range(6):
            self.set(8, i, bit(i))
        self.set(8, 7, bit(6))
        self.set(8, 8, bit(7))
        self.set(7, 8, bit(8))
        for i in range(9, 15):
            self.set(14 - i, 8, bit(i))
        for i in range(8):
            self.set(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set(8, size - 15 + i, bit(i))
        self.set(8, size - 8, True)

    def place(self, codewords):
        bits = [byte >> (7 - i) & 1 for byte in codewords for i in range(8)]
        index, size = 0, self.size
        for right in range(size - 1, 0, -2):
            if right <= 6:
                right -= 1
            upward = (right + 1) & 2 == 0
            for step in range(size):
                y = size - 1 - step if upward else step
                for x in (right, right - 1):
                    if not self.is_function[y][x] and index < len(bits):
                        self.modules[y][x] = bits[index] == 1
                        index += 1

    def apply_mask(self, mask):
        tests = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
                 lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
                 lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
                 lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]
        for y in range(self.size):
            for x in range(self.size):
                if not self.is_function[y][x] and tests[mask](x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self):
        size, grid, score = self.size, self.modules, 0
        for lines in (grid, [list(column) for column in zip(*grid)]):
            for line in lines:
                run = 1
                for i in range(1, size):
                    run = run + 1 if line[i] == line[i - 1] else 1
                    score += 3 if run == 5 else 1 if run > 5 else 0
        for y in range(size - 1):
            for x in range(size - 1):
                if grid[y][x] == grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1]:
                    score += 3
        dark = sum(map(sum, grid))
        return score + abs(dark * 20 - size * size * 10) // (size * size) * 10


def encode(text):
    """The QR as rows of booleans (True = dark), without the quiet zone."""
    data = text.encode()
    version = next((v for v in BLOCKS_M if len(data) <= sum(n * s for n, s in BLOCKS_M[v][1]) - (3 if v < 10 else 4)), None)
    if version is None:
        raise ValueError("text too long for a QR code")
    best = None
    for mask in range(8):
        matrix = _Matrix(version)
        matrix.place(_codewords(data, version))
        matrix.apply_mask(mask)
        matrix.draw_format(mask)
        score = matrix.penalty()
        if best is None or score < best[0]:
            best = (score, matrix.modules)
    return best[1]


def terminal(modules):
    """Two rows per text line with half blocks. Drawn as light on dark-agnostic: the quiet zone is
    printed too, and dark modules are black on a white background so any terminal scans it."""
    quiet = 2
    size = len(modules) + 2 * quiet
    grid = [[False] * size for _ in range(size)]
    for y, row in enumerate(modules):
        for x, dark in enumerate(row):
            grid[y + quiet][x + quiet] = dark
    if size % 2:
        grid.append([False] * size)
    lines = []
    for y in range(0, len(grid), 2):
        line = ""
        for x in range(size):
            top, bottom = grid[y][x], grid[y + 1][x]
            line += " " if not top and not bottom else "▀" if top and not bottom else "▄" if bottom and not top else "█"
        # Reverse video would make dark modules white; instead print black on white explicitly.
        lines.append("\x1b[30;47m" + line + "\x1b[0m")
    return "\n".join(lines)


def png(modules, scale=8, quiet=4):
    size = (len(modules) + 2 * quiet) * scale
    rows = []
    for y in range(size):
        module_y = y // scale - quiet
        row = bytearray([0])
        for x in range(size):
            module_x = x // scale - quiet
            dark = 0 <= module_y < len(modules) and 0 <= module_x < len(modules) and modules[module_y][module_x]
            row.append(0 if dark else 255)
        rows.append(bytes(row))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
