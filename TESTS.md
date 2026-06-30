

f:\"Program Files\Blender Foundation\Blender 4.2\blender.exe" --background --python f:\        git\blender2step\step_exporter\tests\test_cone_combinations.py

* 所有 84 个案例只做参数检测（<1 秒/个）→ 约 10 秒完成
* 仅 FAIL 的案例才导出 STEP（用于 visual debug）
* 生成 HTML 报告


### 验证step物体尺寸

```
python dump_step_solids.py
```


### GitHub Actions
测试用例在GitHub Actions中运行，请查看.github/workflows/test.yml。

#### 发布 OCCT 7.8.1 Pre-built for Windows

第 1 步：在项目根目录运行打包脚本

```powershell
.\scripts\pack_occt_for_ci.ps1
```

这会生成 occt-x64-windows-release.zip（约 200MB，就是你本地的 OCCT 7.8.1）。

第 2 步：创建 GitHub Release

打开 https://github.com/langhua/blender2step/releases/new
Choose a tag → 输入 occt-v1（新建）
Release title → 填 OCCT 7.8.1 Pre-built
拖入生成的 occt-x64-windows-release.zip
点击 Publish release


第 3 步：推送代码


之后每次 CI 运行：

从 Release 下载 OCCT 7.8.1（~30 秒）
编译 .pyd（~2 分钟）
总共约 3 分钟，且版本与你本地完全一致

