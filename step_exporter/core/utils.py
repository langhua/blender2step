"""
STEP Exporter utility functions: logging, STEP file verification, merging.
"""

import os
import re
from . import _globals as _g


def log_to_file(msg):
    """输出到日志文件和console（同步输出）"""
    if not msg.endswith("\n"):
        msg = msg + "\n"
    
    # 始终输出到console
    print(msg, end='')
    
    # 同时写入step日志文件
    if _g._export_log_file and not _g._export_log_file.closed:
        _g._export_log_file.write(msg)
        _g._export_log_file.flush()
    else:
        # 文件未打开，暂存到缓冲区
        _g._log_buffer.append(msg)


def _verify_step_shell(filepath):
    """快速验证 STEP 文件中的 CLOSED_SHELL 面数，用于诊断导出问题。
    返回 (shell_count, face_counts_list) 或 (0, []) 如果文件不存在."""
    if not os.path.exists(filepath):
        return 0, []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 查找所有 CLOSED_SHELL 定义: #N=CLOSED_SHELL('name',(#F1,#F2,...));
        shells = re.findall(r'#\d+\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]*)\)', content)
        face_counts = []
        for s in shells:
            faces = [x.strip() for x in s.split(',') if x.strip().startswith('#')]
            face_counts.append(len(faces))
        return len(shells), face_counts
    except Exception:
        return 0, []


def _strip_wireframe_chain(entities):
    """Remove wireframe product chain entities, keeping only solid geometry.
    
    Each temp file has: wireframe product (#1~#22 approx) + solid product (#23+).
    Strategy: find MANIFOLD_SOLID_BREP → follow to ADVANCED_BREP_SHAPE_REPRESENTATION
    → follow to SHAPE_DEFINITION_REPRESENTATION → keep product chain from there.
    Remove everything else except shared context (#1 APPLICATION_PROTOCOL_DEFINITION,
    #2 APPLICATION_CONTEXT).
    
    Returns filtered list of (id, entity_text) tuples.
    """
    from collections import deque
    
    if len(entities) < 2:
        return entities
    
    # Build id→text map and reference map
    entity_map = {}
    entity_refs = {}
    for eid, text in entities:
        entity_map[eid] = text
        entity_refs[eid] = {int(x) for x in re.findall(r'#(\d+)', text)}
    
    # Step 1: Find the solid root (MANIFOLD_SOLID_BREP)
    solid_brep_id = None
    for eid, text in entities:
        if 'MANIFOLD_SOLID_BREP' in text:
            solid_brep_id = eid
            break
    
    if solid_brep_id is None:
        return entities  # No solid, keep everything
    
    # Step 2: Find ADVANCED_BREP_SHAPE_REPRESENTATION that references solid_brep_id
    advanced_brep_id = None
    for eid, text in entities:
        if 'ADVANCED_BREP_SHAPE_REPRESENTATION' in text and solid_brep_id in entity_refs.get(eid, set()):
            advanced_brep_id = eid
            break
    
    if advanced_brep_id is None:
        return entities
    
    # Step 3: Find SHAPE_DEFINITION_REPRESENTATION that references advanced_brep_id
    sdr_id = None
    pds_id = None
    for eid, text in entities:
        if 'SHAPE_DEFINITION_REPRESENTATION' in text and advanced_brep_id in entity_refs.get(eid, set()):
            sdr_id = eid
            # Extract referenced PRODUCT_DEFINITION_SHAPE id (the ref that is NOT advanced_brep_id)
            refs = entity_refs[eid] - {advanced_brep_id}
            if refs:
                pds_id = min(refs)  # Typically the lower-numbered ref is PDS
            break
    
    if sdr_id is None:
        return entities
    
    # Step 4: Follow product chain from PRODUCT_DEFINITION_SHAPE
    # PDS → PRODUCT_DEFINITION → (PRODUCT_DEFINITION_FORMATION, PRODUCT_DEFINITION_CONTEXT)
    # PDF → PRODUCT → PRODUCT_CONTEXT
    # Also: PRODUCT_RELATED_PRODUCT_CATEGORY
    keep_ids = {1, 2}  # Always keep APPLICATION_PROTOCOL_DEFINITION and APPLICATION_CONTEXT
    
    # BFS to collect all reachable entities from solid side
    visited = set()
    queue = deque([sdr_id, advanced_brep_id])
    if pds_id:
        queue.append(pds_id)
    
    while queue:
        eid = queue.popleft()
        if eid in visited:
            continue
        if eid not in entity_map:
            continue
        visited.add(eid)
        keep_ids.add(eid)
        for ref in entity_refs[eid]:
            if ref not in visited:
                queue.append(ref)
    
    return [(eid, text) for eid, text in entities if eid in keep_ids]


def _merge_step_files(output_path, temp_files):
    """将多个 STEP 文件合并为一个，重新编号实体 ID"""
    
    header = None
    all_data_sections = []
    max_entity_id = 0
    
    # 实体 ID 匹配: #12345=... 
    entity_re = re.compile(r'^#(\d+)\s*=(.*)$')
    
    def _renumber_refs(text, shift):
        r"""Renumber entity references #\d+ in text, respecting STEP single-quote strings.
        Only replaces #\d+ outside of quoted strings."""
        result = []
        in_string = False
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "'":
                in_string = not in_string
                result.append(ch)
                i += 1
            elif not in_string and ch == '#' and i + 1 < n and text[i + 1].isdigit():
                j = i + 1
                while j < n and text[j].isdigit():
                    j += 1
                ref_id = int(text[i + 1:j])
                result.append('#')
                result.append(str(ref_id + shift))
                i = j
            else:
                result.append(ch)
                i += 1
        return ''.join(result)
    
    for filepath in temp_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分离 HEADER 和 DATA
        parts = content.split('DATA;')
        if len(parts) < 2:
            raise ValueError(f"Invalid STEP file: {filepath}")
        
        data_part = parts[1]
        ends_index = data_part.rfind('ENDSEC;')
        if ends_index == -1:
            raise ValueError(f"No ENDSEC found in {filepath}")
        
        data_content = data_part[:ends_index].strip()
        
        if header is None:
            header = parts[0] + 'DATA;'
        
        all_data_sections.append(data_content)
    
    # 收集所有实体，重新编号
    merged_entities = []
    for section in all_data_sections:
        entities = []
        current_entity = None
        current_id = None
        
        for line in section.replace('\r', '').split('\n'):
            m = entity_re.match(line.strip())
            if m:
                if current_entity is not None:
                    entities.append((current_id, current_entity))
                current_id = int(m.group(1))
                current_entity = line.strip()
            else:
                if current_entity is not None:
                    current_entity += '\n' + line.strip()
        
        if current_entity is not None:
            entities.append((current_id, current_entity))
        
        # Strip wireframe product chain (dummy vertex, if any) from each temp file
        entities = _strip_wireframe_chain(entities)
        
        id_shift = max_entity_id
        
        for old_id, entity_text in entities:
            new_id = old_id + id_shift
            max_entity_id = max(max_entity_id, new_id)
            
            eq_pos = entity_text.find('=')
            entity_text = f'#{new_id}' + entity_text[eq_pos:]
            
            rest = entity_text[eq_pos + 1:]
            rest = _renumber_refs(rest, id_shift)
            entity_text = entity_text[:eq_pos + 1] + rest
            
            merged_entities.append((new_id, entity_text))
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for _, entity in merged_entities:
            if not entity.endswith(';'):
                entity += ';'
            f.write(entity + '\n')
        f.write('ENDSEC;\nEND-ISO-10303-21;\n')


def _merge_log_files(output_dir, output_path):
    """将同目录下其他 .step.log 文件中的 [STEP Exporter] 行合并到主日志文件"""
    
    if not _g._export_log_file or _g._export_log_file.closed:
        return
    
    try:
        log_dir = os.path.dirname(output_path)
        main_log_basename = os.path.basename(output_path) + ".log"
        
        for fname in sorted(os.listdir(log_dir)):
            if fname == main_log_basename:
                continue
            if not fname.endswith('.step.log') and not fname.endswith('.step.log.temp'):
                continue
            
            log_path = os.path.join(log_dir, fname)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    content = lf.read()
                step_lines = re.findall(r'\[STEP Exporter\].*', content)
                if step_lines:
                    _g._export_log_file.write(f"\n--- Merged from {fname} ---\n")
                    for line in step_lines:
                        if not line.endswith('\n'):
                            line += '\n'
                        _g._export_log_file.write(line)
                    _g._export_log_file.flush()
            except Exception:
                pass
    except Exception:
        pass
