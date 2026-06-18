"""Register a custom inverted-cone icon via temporary PNG file."""
import bpy, os, struct, zlib, tempfile

_icon_previews = None
ICON_SIZE = 16


def _make_png(size=ICON_SIZE):
    """Generate a simple inverted-cone PNG and return its bytes."""
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    raw = b''
    mid = size // 2
    for y in range(size):
        raw += b'\x00'  # filter none
        frac = y / (size - 1)
        radius = int((1.0 - frac) * (mid - 2) + 2)
        for x in range(size):
            dx = x - mid
            inside = abs(dx) <= radius and 2 <= y <= size - 3
            edge = abs(dx) <= radius + 1 and abs(dx) >= radius - 1 and 1 < y < size - 2
            if inside:
                raw += struct.pack('BBBB', 102, 140, 179, 255)
            elif edge:
                raw += struct.pack('BBBB', 77, 115, 153, 255)
            elif y < 3 and abs(dx) <= radius:
                raw += struct.pack('BBBB', 140, 179, 217, 255)
            elif y >= size - 3 and abs(dx) <= radius:
                raw += struct.pack('BBBB', 128, 166, 204, 255)
            else:
                raw += struct.pack('BBBB', 0, 0, 0, 0)

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', zlib.compress(raw))
    png += chunk(b'IEND', b'')
    return png


def register():
    global _icon_previews
    png_data = _make_png()
    # Write to temp file for bpy.utils.previews.load()
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.write(png_data)
    tmp.close()
    _icon_previews = bpy.utils.previews.new()
    _icon_previews.load("inv_cone_icon", tmp.name, 'IMAGE')
    os.unlink(tmp.name)


def unregister():
    global _icon_previews
    if _icon_previews:
        bpy.utils.previews.remove(_icon_previews)
        _icon_previews = None


def get_inv_cone_icon():
    if _icon_previews:
        return _icon_previews["inv_cone_icon"].icon_id
    return 0
