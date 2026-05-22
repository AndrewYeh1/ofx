# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

# 1. Collect all resources and binaries for PaddleOCR, PaddlePaddle, and other heavy dependencies
paddle_collect = collect_all('paddle')
paddleocr_collect = collect_all('paddleocr')
paddlex_collect = collect_all('paddlex')
pyclipper_collect = collect_all('pyclipper')
lmdb_collect = collect_all('lmdb')
skimage_collect = collect_all('skimage')
imgaug_collect = collect_all('imgaug')
scipy_collect = collect_all('scipy')
safetensors_collect = collect_all('safetensors')
camelot_collect = collect_all('camelot')
cv2_collect = collect_all('cv2')
pypdfium2_collect = collect_all('pypdfium2')

# 2. Combine all data files, binaries, and hidden imports
datas = (
    paddle_collect[0] + 
    paddleocr_collect[0] + 
    paddlex_collect[0] +
    pyclipper_collect[0] + 
    lmdb_collect[0] + 
    skimage_collect[0] + 
    imgaug_collect[0] + 
    scipy_collect[0] + 
    safetensors_collect[0] +
    camelot_collect[0] +
    cv2_collect[0] +
    pypdfium2_collect[0] +
    [('resources', 'resources')] # Bundle our dark theme QSS stylesheet and icons
)

binaries = (
    paddle_collect[1] + 
    paddleocr_collect[1] + 
    paddlex_collect[1] +
    pyclipper_collect[1] + 
    lmdb_collect[1] + 
    skimage_collect[1] + 
    imgaug_collect[1] + 
    scipy_collect[1] + 
    safetensors_collect[1] +
    camelot_collect[1] +
    cv2_collect[1] +
    pypdfium2_collect[1]
)

hiddenimports = (
    paddle_collect[2] + 
    paddleocr_collect[2] + 
    paddlex_collect[2] +
    pyclipper_collect[2] + 
    lmdb_collect[2] + 
    skimage_collect[2] + 
    imgaug_collect[2] + 
    scipy_collect[2] + 
    safetensors_collect[2] +
    camelot_collect[2] +
    cv2_collect[2] +
    pypdfium2_collect[2] +
    ['scipy._cyutility']
)

# =========================================================================
# OPTIONAL: PACKAGING FOR FULLY OFFLINE RUNS (Offline Strategy)
# =========================================================================
# By default, the compiled executable will download the layout model on the 
# first run and cache it under the user's home folder. 
#
# If you want to bundle your pre-downloaded model directory so the program is 
# 100% offline and doesn't download anything on first launch, do this:
# 1. Create a folder named "models" in the root of this project.
# 2. Copy the entire ".paddlex" directory (located in C:\Users\andre\.paddlex) 
#    into "models/". (So that the path models/.paddlex/official_models/... exists).
# 3. Uncomment the line below:
#
datas.append(('models/.paddlex', 'models/.paddlex'))
# =========================================================================

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Extractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Set to True if you want a cmd console window for debugging log messages
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
    upx=True,
    upx_exclude=[],
    name='Extractor',
)
