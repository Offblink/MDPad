# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# qfluentwidgets 的 QSS/资源文件与动态子模块需显式收集
datas = [('../icon.ico', '.')] + collect_data_files('qfluentwidgets')
hiddenimports = collect_submodules('qfluentwidgets')

a = Analysis(
    ['../MDPad.pyw'],
    pathex=['..'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除环境中的无关重型包，避免被意外卷入拖慢构建
    excludes=['pygame', 'plotly', 'altair', 'narwhals', 'polars',
              'jsonschema', 'jsonschema_specifications', 'matplotlib',
              'scipy', 'pandas', 'IPython'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MDPad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../icon.ico'],
)
