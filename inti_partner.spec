# -*- mode: python ; coding: utf-8 -*-
block_cipher=None

import os
base_path = os.getcwd()
icon_path = os.path.join(base_path, 'intipartner.ico')

a = Analysis(
    ['inti_partner.py'],
    pathex=[],
    binaries=[],
    datas=[('inti_partner.ui','.'),('intipartner_icon.png','.'),('inti_partner_EN.qm','.'),
	('sun_spectre_color.png','.'),('sun_spectre_annot_V2.png','.'), ('sun_spectre.png','.'),
	('img_qt.ui','.'),('gong.ui','.'),('infos_txt.ui','.'),('earth.png','.'),
	('matplotlib_cache/fontlist-v330.json', 'matplotlib_cache'),
	('matplotlib_cache/fontlist-v390.json', 'matplotlib_cache')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='inti_partner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True, icon=icon_path,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='inti_partner',
)
