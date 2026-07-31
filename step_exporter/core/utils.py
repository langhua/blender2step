"""
STEP Exporter utility functions: logging, STEP file verification, merging.
"""

import os
import re
try:
    from . import _globals as _g
except ImportError:
    import types as _types
    _g = _types.SimpleNamespace()
    _g._export_log_file = None
    _g._log_buffer = []
    _g.CPP_MODULE_LOADED = False


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
    """Remove wireframe product chain entities, keeping only solid/surface geometry.
    
    Recognizes both MANIFOLD_SOLID_BREP (closed solids) and
    SHELL_BASED_SURFACE_MODEL (open shells like parametric shell).
    
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
    
    # Step 1: Find ALL geometry roots:
    #   - MANIFOLD_SOLID_BREP (closed solids) referenced by ADVANCED_BREP_SHAPE_REPRESENTATION
    #   - SHELL_BASED_SURFACE_MODEL (open shells) referenced by MANIFOLD_SURFACE_SHAPE_REPRESENTATION
    geometry_roots = []  # list of (root_id, shape_rep_id, shape_rep_keyword)
    for eid, text in entities:
        if 'MANIFOLD_SOLID_BREP' in text:
            geometry_roots.append((eid, 'ADVANCED_BREP_SHAPE_REPRESENTATION'))
        elif 'SHELL_BASED_SURFACE_MODEL' in text:
            geometry_roots.append((eid, 'MANIFOLD_SURFACE_SHAPE_REPRESENTATION'))
    
    if not geometry_roots:
        return entities  # No geometry, keep everything
    
    keep_ids = {1, 2}  # Always keep APPLICATION_PROTOCOL_DEFINITION and APPLICATION_CONTEXT
    log_root_count = 0
    
    for root_id, shape_rep_keyword in geometry_roots:
        # Step 2: Find shape representation that references this root
        # Try specific keywords first, then fall back to any SHAPE_REPRESENTATION
        shape_rep_id = None
        for keyword in [shape_rep_keyword, 'SHAPE_REPRESENTATION']:
            if shape_rep_id:
                break
            for eid, text in entities:
                if keyword in text and root_id in entity_refs.get(eid, set()):
                    shape_rep_id = eid
                    break
        
        if shape_rep_id is None:
            log_to_file(f"[MERGE DEBUG] No shape_rep found for root #{root_id} type={shape_rep_keyword}")
            continue
        
        # Step 3: Find SHAPE_DEFINITION_REPRESENTATION that references shape_rep_id
        sdr_id = None
        for eid, text in entities:
            if 'SHAPE_DEFINITION_REPRESENTATION' in text and shape_rep_id in entity_refs.get(eid, set()):
                sdr_id = eid
                break
        
        if sdr_id is None:
            # No SDR found — still keep the geometry chain (BFS from shape_rep and root)
            log_to_file(f"[MERGE DEBUG] No SDR for root #{root_id}, BFS from shape_rep #{shape_rep_id}")
        
        # BFS from this geometry chain — always include root_id
        visited = set()
        queue = deque([root_id, shape_rep_id])
        if sdr_id:
            queue.append(sdr_id)
            # Also include PRODUCT_DEFINITION_SHAPE referenced by SDR
            for ref in entity_refs.get(sdr_id, set()):
                if ref != shape_rep_id and ref in entity_map:
                    queue.append(ref)
        
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
    
    # Debug logging
    all_entity_ids = {eid for eid, _ in entities}
    kept_count = len([eid for eid in all_entity_ids if eid in keep_ids])
    log_to_file(f"[MERGE DEBUG] _strip_wireframe_chain: {len(entities)} entities -> {kept_count} kept, roots={len(geometry_roots)}")
    
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
        log_to_file(f"[MERGE DEBUG] Processing temp file: {len(entities)} entities before strip")
        entities = _strip_wireframe_chain(entities)
        log_to_file(f"[MERGE DEBUG] After strip: {len(entities)} entities, id_shift={max_entity_id}")
        
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
