# -*- coding: utf-8 -*-
# 从本仓库 GitHub Release 下载模型权重（公开仓库，无需 token）
import json
import os
import urllib.request

REPO = os.environ.get("WEIGHTS_REPO", "nightwhite/guard-mgte-public")
OUT_DIR = os.environ.get("WEIGHTS_OUT", "/app/model")

rel = json.load(urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/latest"))
asset = next(a for a in rel["assets"] if a["name"] == "model.bin")
os.makedirs(OUT_DIR, exist_ok=True)
out = os.path.join(OUT_DIR, "model.bin")
urllib.request.urlretrieve(asset["browser_download_url"], out)
print("weights:", out, os.path.getsize(out))
