import pathlib, subprocess, sys

docs = pathlib.Path('docs/images')
docs.mkdir(parents=True, exist_ok=True)

# Create .mmd files
en_mmd = '''flowchart LR
    A["★ Fritzing ★<br/>Circuit design"] -->|"Gerber RS-274X"| B["PCB Factory<br/>Board production"]
    A -->|"PNP file"| C["pnp2cpl<br/>Format conversion"] -->|"CSV assembly list"| B
    A -->|"Gerber RS-274X"| D["FritzingToBlender<br/>Import into Blender"] --> E["★ Blender ★<br/>Enclosure design"]
    E --> F["blender2step<br/>Export STEP"] -->|STEP| K["★ FreeCAD ★<br/>Verify STEP"] -->|STEP| G["Mold factory<br/>Mass production"]
    H["★ Inkscape ★<br/>Part graphics"] -.->|SVG| A
    I["fritzing-parts-langhua<br/>Open parts library"] -.->|SVG| A
    J["★ OpenCASCADE ★<br/>STEP engine"] -.->|powers| F
    J -.->|powers| K
    style F fill:#f9a825,stroke:#333,stroke-width:2px,color:#000'''

zh_mmd = '''flowchart LR
    A["★ Fritzing ★<br/>电路设计"] -->|"Gerber RS-274X"| B["PCB 工厂<br/>电路板生产"]
    A -->|"PNP 文件"| C["pnp2cpl<br/>格式转换"] -->|"CSV 装配文件"| B
    A -->|"Gerber RS-274X"| D["FritzingToBlender<br/>导入 Blender"] --> E["★ Blender ★<br/>外壳设计"]
    E --> F["blender2step<br/>导出 STEP"] -->|STEP| K["★ FreeCAD ★<br/>验证 STEP"] -->|STEP| G["模具工厂<br/>批量生产"]
    H["★ Inkscape ★<br/>元件图形"] -.->|SVG| A
    I["fritzing-parts-langhua<br/>开源元件库"] -.->|SVG| A
    J["★ OpenCASCADE ★<br/>STEP 引擎"] -.->|支撑| F
    J -.->|支撑| K
    style F fill:#f9a825,stroke:#333,stroke-width:2px,color:#000'''

for lang, code in [('en_mmd', en_mmd), ('zh_mmd', zh_mmd)]:
    mmd_path = docs / f'toolchain_{lang}.mmd'
    mmd_path.write_text(code, encoding='utf-8')
    print(f'Wrote {mmd_path}')

print('Done. Now run: npx @mermaid-js/mermaid-cli mmdc -i docs/images/toolchain_en.mmd -o docs/images/toolchain_en.svg')

print('Done')
