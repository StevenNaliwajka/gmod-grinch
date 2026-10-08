# Flat-colour VTF (7.2, RGB888, full mip chain) + VMT for every material in build_grinch.COLORS.
import struct, os, sys, re, ast
src = open(os.path.join(os.path.dirname(__file__), 'build_grinch.py')).read()
COLORS = ast.literal_eval(re.search(r'COLORS = (\{.*?\n\})', src, re.S).group(1))
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
def vtf(path, rgb, size=16):
    mips = []
    s = size
    while s >= 1:
        mips.append(s); s //= 2
    hdr = bytearray(80)
    struct.pack_into('<4s2II', hdr, 0, b'VTF\0', 7, 2, 80)
    struct.pack_into('<HHIHH', hdr, 16, size, size, 0x0100 | 0x0200 if False else 0, 1, 0)
    struct.pack_into('<3f', hdr, 32, *[c for c in rgb])
    struct.pack_into('<f', hdr, 48, 1.0)
    struct.pack_into('<i', hdr, 52, 2)          # IMAGE_FORMAT_RGB888
    struct.pack_into('<B', hdr, 56, len(mips))
    struct.pack_into('<i', hdr, 57, -1)         # no low-res image
    struct.pack_into('<BBH', hdr, 61, 0, 0, 1)
    px = bytes(int(round(c * 255)) for c in rgb)
    data = b''.join(px * (m * m) for m in reversed(mips))
    open(path, 'wb').write(bytes(hdr) + data)
for name, rgb in COLORS.items():
    vtf(os.path.join(out, name + '.vtf'), rgb)
    base = 'models/player/burrito/grinch_ultimatum/' + name
    if name == 'grinch_outline':
        body = f'"UnlitGeneric"\n{{\n\t"$basetexture" "{base}"\n}}\n'
    else:
        body = f'"VertexLitGeneric"\n{{\n\t"$basetexture" "{base}"\n\t"$halflambert" "1"\n}}\n'
    open(os.path.join(out, name + '.vmt'), 'w').write(body)
print('materials', len(COLORS))
