import re

with open(r'f:\git\blender2step\step_exporter\test28.step', 'r') as f:
    content = f.read()

# Parse entities
entities = {}
pattern = re.compile(r'#(\d+)\s*=\s*(.+?)(?=\n#\d|\nENDSEC)', re.DOTALL)
for m in pattern.finditer(content):
    entities[int(m.group(1))] = m.group(2)

# Dangling refs
all_refs = set()
for body in entities.values():
    all_refs.update(int(x) for x in re.findall(r'#(\d+)', body))
dangling = sorted(all_refs - set(entities.keys()))
print(f"Entities: {len(entities)}, Unique refs: {len(all_refs)}")
if dangling:
    print(f"DANGLING ({len(dangling)}): {dangling[:20]}")
else:
    print("No dangling refs")

# Self-refs
self_refs = [eid for eid, body in entities.items() if eid in set(int(x) for x in re.findall(r'#(\d+)', body))]
if self_refs:
    print(f"SELF-REFS: {self_refs}")
else:
    print("No self-refs")

# Cycles  
graph = {}
for eid, body in entities.items():
    refs = set(int(x) for x in re.findall(r'#(\d+)', body))
    graph[eid] = refs & set(entities.keys())

visited = set()
def find_cycle(node, path):
    if node in path:
        idx = path.index(node)
        return path[idx:] + [node]
    if node in visited:
        return None
    visited.add(node)
    for nb in graph.get(node, set()):
        if nb == node:
            continue
        r = find_cycle(nb, path + [node])
        if r:
            return r
    return None

for eid in entities:
    if eid not in visited:
        cycle = find_cycle(eid, [])
        if cycle:
            print(f"CYCLE found: {' -> '.join(f'#{x}' for x in cycle)}")
            break
else:
    print("No cycles found")

# Check for empty entity bodies
empty = [eid for eid, body in entities.items() if not body.strip()]
if empty:
    print(f"EMPTY entities: {empty[:10]}")
