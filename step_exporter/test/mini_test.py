"""Minimal test: just check init_incremental_export doesn't crash"""
import sys
sys.path.insert(0, r'F:\git\blender2step\step_exporter')
import _step_exporter as cpp
import os

step_path = r'F:\git\blender2step\step_exporter\test_mini.step'

# Create test data
obj = {
    'name': 'TestObj',
    'vertices': [[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],
    'faces': [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
}

log_msgs = []
def log_cb(msg):
    log_msgs.append(msg)  # 只是收集消息，不print

print("BEFORE init", flush=True)
result = cpp.init_incremental_export(step_path, 1, 1000.0, 1, 1, 1, 'AP214DIS', 'MILLIMETER', 1, 0.001, log_cb)
print(f"AFTER init, result={result}", flush=True)

print("BEFORE add_object", flush=True)
result2 = cpp.add_object_to_export(obj, lambda p: None)
print(f"AFTER add_object, result={result2}", flush=True)
print(f"Collected C++ logs: {len(log_msgs)} messages", flush=True)
for m in log_msgs[-5:]:
    print(f"  LOG: {m}", flush=True)

print("BEFORE finalize", flush=True)
result3 = cpp.finalize_incremental_export()
print(f"AFTER finalize, result={result3}", flush=True)

print(f"File exists: {os.path.exists(step_path)}", flush=True)
print("ALL DONE", flush=True)