# -*- coding: utf-8 -*-
"""下载并检查 AAL 脑图谱 NIfTI 数据的头部信息与体素统计（含字节序检测）。"""
import struct
import requests
import os
from collections import Counter

NII_URL = "https://raw.githubusercontent.com/fieldtrip/fieldtrip/master/template/atlas/aal/ROI_MNI_V4.nii"
TXT_URL = "https://raw.githubusercontent.com/fieldtrip/fieldtrip/master/template/atlas/aal/ROI_MNI_V4.txt"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

nii_path = os.path.join(DATA_DIR, "ROI_MNI_V4.nii")
txt_path = os.path.join(DATA_DIR, "ROI_MNI_V4.txt")

def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print("已存在:", path)
        return
    print("下载:", url)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    print("保存:", path, os.path.getsize(path), "bytes")

download(NII_URL, nii_path)
download(TXT_URL, txt_path)

with open(nii_path, "rb") as f:
    blob = f.read()

# 字节序检测：sizeof_hdr 应为 348
if struct.unpack_from("<i", blob, 0)[0] == 348:
    endian = "<"
elif struct.unpack_from(">i", blob, 0)[0] == 348:
    endian = ">"
else:
    # 可能是 gzip
    raise ValueError("无法识别 NIfTI 字节序，前4字节=%r" % blob[:4])

print("字节序:", "little" if endian == "<" else "big")

dim = struct.unpack_from(endian + "8h", blob, 40)
datatype = struct.unpack_from(endian + "h", blob, 70)[0]
bitpix = struct.unpack_from(endian + "h", blob, 72)[0]
vox_offset = struct.unpack_from(endian + "f", blob, 108)[0]
pixdim = struct.unpack_from(endian + "8f", blob, 76)

print("dim:", dim)
print("datatype:", datatype, "bitpix:", bitpix)
print("vox_offset:", vox_offset)
print("pixdim:", pixdim)

dt_map = {2: "B", 4: "h", 8: "i", 16: "f", 512: "H", 768: "I", 256: "b", 1024: "q", 1280: "Q"}
code = dt_map.get(datatype)
if code is None:
    raise ValueError("不支持的 datatype: %s" % datatype)

nx, ny, nz = dim[1], dim[2], dim[3]
raw = blob[int(vox_offset):]
n = nx * ny * nz
vals = struct.unpack_from(endian + "%d%s" % (n, code), raw)

c = Counter(vals)
labels = sorted(k for k in c if k != 0)
print("总网格体素:", n)
print("非零(脑)体素:", sum(v for k, v in c.items() if k != 0))
print("不同标签数(含0):", len(c))
print("标签范围:", labels[0] if labels else None, "..", labels[-1] if labels else None)

with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
    names = [ln.strip() for ln in f if ln.strip()]
print("标签名数量:", len(names))
for i, nm in enumerate(names[:12]):
    print(" ", i + 1, nm)
print("...")
for i, nm in enumerate(names[-12:], len(names) - 11):
    print(" ", i, nm)
