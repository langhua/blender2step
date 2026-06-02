import re
import math
from collections import defaultdict

def extract_shell_points(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
    all_points = {}
    for match in re.finditer(point_pattern, content):
        pid = int(match.group(1))
        try:
            x = float(match.group(2).strip())
            y = float(match.group(3).strip())
            z = float(match.group(4).strip())
            all_points[pid] = (x, y, z)
        except ValueError:
            pass

    solids = re.findall(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\([^,]*,#(\d+)\)', content)
    print(f"Found {len(solids)} solids")

    for i, (solid_id, shell_id) in enumerate(solids):
        print(f"\n{'='*60}")
        print(f"Object {i+1}: Solid #{solid_id}, Shell #{shell_id}")

        shell_match = re.search(r'#' + shell_id + r'\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]+)\)', content)
        if not shell_match:
            print("  Cannot parse shell faces")
            continue

        face_ids = re.findall(r'#(\d+)', shell_match.group(1))
        print(f"  Faces: {len(face_ids)}")

        shell_point_ids = set()
        for face_id in face_ids:
            face_block = re.search(r'#' + face_id + r'\s*=\s*ADVANCED_FACE.*?(?=#\d+\s*=)', content, re.DOTALL)
            if not face_block:
                face_block = re.search(r'#' + face_id + r'\s*=.*', content)
                if face_block:
                    rest = content[face_block.end():]
                    next_entity = re.search(r'\n#\d+\s*=', rest)
                    if next_entity:
                        face_block_text = content[face_block.start():face_block.end() + next_entity.start()]
                    else:
                        face_block_text = content[face_block.start():]
                else:
                    continue
            else:
                face_block_text = face_block.group(0)

            pids = set(int(m) for m in re.findall(r'#(\d+)', face_block_text))
            shell_point_ids.update(pids)

        shell_points = {}
        for pid in shell_point_ids:
            if pid in all_points:
                shell_points[pid] = all_points[pid]

        print(f"  Points: {len(shell_points)}")

        if not shell_points:
            continue

        z_vals = [z for x, y, z in shell_points.values()]
        min_z = min(z_vals) if z_vals else 0
        max_z = max(z_vals) if z_vals else 0
        print(f"  Z range: {min_z:.3f} to {max_z:.3f}")

        z_layers = defaultdict(list)
        for pid, (x, y, z) in shell_points.items():
            z_key = round(z / 0.01) * 0.01
            z_layers[z_key].append((x, y, z))

        sorted_z = sorted(z_layers.keys())
        print(f"  Z layers: {len(sorted_z)}")

        all_x = [x for x, y, z in shell_points.values()]
        all_y = [y for x, y, z in shell_points.values()]
        cx = (max(all_x) + min(all_x)) / 2.0
        cy = (max(all_y) + min(all_y)) / 2.0
        print(f"  Center: ({cx:.2f}, {cy:.2f})")
        print(f"  BBox: X[{min(all_x):.1f}, {max(all_x):.1f}] Y[{min(all_y):.1f}, {max(all_y):.1f}]")

        bottom_z = min_z
        bottom_levels = [z for z in sorted_z if z <= bottom_z + 3.0]
        print(f"\n  Bottom region (z <= {bottom_z + 3.0:.1f}), {len(bottom_levels)} levels:")

        for z in bottom_levels[:6]:
            verts = z_layers[z]
            dists = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y, _ in verts]
            if not dists:
                continue
            dists.sort()
            n = len(dists)
            print(f"    z={z:.2f}, n={n}, min={min(dists):.1f}, max={max(dists):.1f}")

            if n >= 40:
                p10 = dists[n // 10]
                p40 = dists[n * 4 // 10]
                p60 = dists[n * 6 // 10]
                p95 = dists[n * 95 // 100]
                ring_inner = sum(dists[n * 4 // 10:n * 6 // 10]) / max(1, n * 2 // 10)
                outer = sum(dists[n * 95 // 100:]) / max(1, n - n * 95 // 100)
                print(f"      P10={p10:.1f} P40={p40:.1f} P60={p60:.1f} P95={p95:.1f}")
                print(f"      ring_inner={ring_inner:.1f} outer={outer:.1f} width={outer-ring_inner:.1f}")

        mid_z_target = (min_z + max_z) / 2.0
        mid_z = min(sorted_z, key=lambda z: abs(z - mid_z_target))
        mid_verts = z_layers[mid_z]
        print(f"\n  Mid-height: z={mid_z:.2f}, n={len(mid_verts)}")

        if len(mid_verts) >= 16:
            num_sectors = 64
            sector_dists = [[] for _ in range(num_sectors)]
            step = 2.0 * math.pi / num_sectors
            for x, y, z in mid_verts:
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                angle = math.atan2(dy, dx)
                if angle < 0:
                    angle += 2.0 * math.pi
                idx = int(angle / step) % num_sectors
                sector_dists[idx].append(dist)

            for frac in [0.10, 0.15, 0.20, 0.25, 0.33, 0.50]:
                walls = []
                for sd in sector_dists:
                    if len(sd) < 3:
                        continue
                    sd.sort()
                    ns = len(sd)
                    inn = max(1, int(ns * frac))
                    outn = max(1, int(ns * frac))
                    ins = sum(sd[:inn]) / inn
                    outs = sum(sd[-outn:]) / outn
                    if outs > ins + 0.3:
                        walls.append(outs - ins)
                if walls:
                    walls.sort()
                    tn = max(1, len(walls) // 4)
                    t = walls[tn:-tn] if len(walls) > tn*2 else walls
                    print(f"    frac={frac:.2f}: {len(walls)}/{num_sectors} → wall={sum(t)/len(t):.2f}mm")

if __name__ == '__main__':
    extract_shell_points(r'F:\git\blender2step\step_exporter\test28.step')