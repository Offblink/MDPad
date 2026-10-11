# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# qfluentwidgets 的 QSS/资源文件与动态子模块需显式收集
# KaTeX 资产（公式渲染）随包分发，供预览页与导出 HTML 使用
datas = [('../icon.ico', '.'), ('../mdpad/assets', 'mdpad/assets')] + collect_data_files('qfluentwidgets')
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

# onedir：dist/MDPad/ 一个文件夹（MDPad.exe + _internal/），不再每次启动把自己
# 解包到 %TEMP%\_MEIxxxxxx。实测 onefile 每次要解 330MB、到窗口 ~10s；onedir
# 直接从磁盘加载，启动 ~2-3s，单例的第二个实例也不再先等解包。
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MDPad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MDPad',
)
