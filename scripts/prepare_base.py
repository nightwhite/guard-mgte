# -*- coding: utf-8 -*-
# 把 gte-multilingual-base + new-impl 自定义代码整成可离线加载的本地目录（auto_map 改相对引用）
import json
import os
import shutil

from huggingface_hub import snapshot_download

OUT = os.environ.get("BASE_OUT", "/app/base")
KEEP = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"}

os.makedirs(OUT, exist_ok=True)
for repo in ("Alibaba-NLP/gte-multilingual-base", "Alibaba-NLP/new-impl"):
    p = snapshot_download(repo)
    for f in os.listdir(p):
        if f in KEEP or f in ("configuration.py", "modeling.py"):
            shutil.copy(os.path.join(p, f), OUT)

cfg = os.path.join(OUT, "config.json")
c = json.load(open(cfg))
c["auto_map"] = {k: v.split("--")[1] for k, v in c["auto_map"].items()}
json.dump(c, open(cfg, "w"), indent=1)
print("base ready:", sorted(os.listdir(OUT)))
