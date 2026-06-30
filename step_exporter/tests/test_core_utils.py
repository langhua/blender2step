"""
Tests for step_exporter.core.utils — 不需要 Blender，CI 中可以直接运行。
Usage: python -m pytest step_exporter/tests/test_core_utils.py -v
"""
import os
import sys
import tempfile
import io

# 确保 step_exporter 可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from step_exporter.core import _globals
from step_exporter.core.utils import log_to_file, _verify_step_shell, _merge_step_files


class TestVerifyStepShell:
    """测试 _verify_step_shell 函数"""

    def test_empty_file(self):
        """空文件应返回 0 shells"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False) as f:
            f.write('')
            path = f.name
        try:
            count, faces = _verify_step_shell(path)
            assert count == 0
            assert faces == []
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        """不存在的文件应返回 (0, [])"""
        count, faces = _verify_step_shell('nonexistent_file_12345.step')
        assert count == 0
        assert faces == []

    def test_single_shell(self):
        """单个 CLOSED_SHELL，3 个面"""
        content = """ISO-10303-21;
HEADER;
DATA;
#1=CLOSED_SHELL('test',(#2,#3,#4));
ENDSEC;
END-ISO-10303-21;"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            count, faces = _verify_step_shell(path)
            assert count == 1
            assert faces == [3]
        finally:
            os.unlink(path)

    def test_multiple_shells(self):
        """多个 CLOSED_SHELL"""
        content = """ISO-10303-21;
HEADER;
DATA;
#1=CLOSED_SHELL('s1',(#2,#3));
#4=CLOSED_SHELL('s2',(#5,#6,#7,#8));
ENDSEC;
END-ISO-10303-21;"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            count, faces = _verify_step_shell(path)
            assert count == 2
            assert faces == [2, 4]
        finally:
            os.unlink(path)

    def test_no_closed_shell(self):
        """文件中没有 CLOSED_SHELL"""
        content = """ISO-10303-21;
HEADER;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
ENDSEC;
END-ISO-10303-21;"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            count, faces = _verify_step_shell(path)
            assert count == 0
            assert faces == []
        finally:
            os.unlink(path)


class TestLogToFile:
    """测试 log_to_file 函数"""

    def test_log_writes_to_file(self):
        """日志应写入文件对象"""
        buf = io.StringIO()
        _globals._export_log_file = buf
        _globals._log_buffer = []
        try:
            log_to_file("hello world")
            buf.seek(0)
            assert "hello world" in buf.getvalue()
        finally:
            _globals._export_log_file = None

    def test_log_buffers_when_no_file(self):
        """文件未打开时应暂存到缓冲区"""
        _globals._export_log_file = None
        _globals._log_buffer = []
        try:
            log_to_file("buffered message")
            assert "buffered message\n" in _globals._log_buffer
        finally:
            _globals._log_buffer = []

    def test_log_adds_newline(self):
        """自动补换行符"""
        buf = io.StringIO()
        _globals._export_log_file = buf
        _globals._log_buffer = []
        try:
            log_to_file("no newline")
            buf.seek(0)
            result = buf.getvalue()
            assert result.endswith("\n")
        finally:
            _globals._export_log_file = None


class TestMergeStepFiles:
    """测试 _merge_step_files 函数"""

    def _make_step(self, data_content):
        """Helper: 创建临时 STEP 文件"""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.step', delete=False)
        f.write(f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('test'),'2;1');
DATA;
{data_content}
ENDSEC;
END-ISO-10303-21;""")
        f.close()
        return f.name

    def test_merge_two_files(self):
        """合并两个 STEP 文件，验证实体 ID 重编号"""
        p1 = self._make_step("#1=CARTESIAN_POINT('',(0.,0.,0.));")
        p2 = self._make_step("#1=CARTESIAN_POINT('',(1.,1.,1.));")
        out = tempfile.mktemp(suffix='.step')
        try:
            _merge_step_files(out, [p1, p2])
            assert os.path.exists(out)
            with open(out, 'r') as f:
                content = f.read()
            # 两个实体都应存在，且 ID 不同
            assert '#1=' in content
            assert '#2=' in content
            assert 'CARTESIAN_POINT' in content
        finally:
            for p in [p1, p2, out]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_merge_single_file(self):
        """合并单个文件应正常工作"""
        p1 = self._make_step("#1=CARTESIAN_POINT('',(0.,0.,0.));")
        out = tempfile.mktemp(suffix='.step')
        try:
            _merge_step_files(out, [p1])
            assert os.path.exists(out)
            with open(out, 'r') as f:
                content = f.read()
            assert '#1=' in content
        finally:
            for p in [p1, out]:
                if os.path.exists(p):
                    os.unlink(p)
