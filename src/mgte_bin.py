# -*- coding: utf-8 -*-
# 模型结构：gte-multilingual-base 底座 + 均值池化 + 9 类分类头（拦截分 = 1 - P(none)）
import torch.nn as nn
from transformers import AutoModel


class MgteFlat(nn.Module):
    def __init__(self, base, n_cls):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base, trust_remote_code=True)
        # unpad 路径按拼接总长索引 rope 表，混合长度批次必越界（IndexKernel assert），关掉走等价慢路径
        self.encoder.config.unpad_inputs = False
        hidden = self.encoder.config.hidden_size
        # head 键在发布权重里存在但已不参与判断，仅为 state_dict 对齐保留
        self.head = nn.Sequential(nn.Dropout(0.1), nn.Linear(hidden, 1))
        self.cls_head = nn.Sequential(nn.Dropout(0.1), nn.Linear(hidden, n_cls))

    def pooled(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        hs = out.last_hidden_state
        m = attention_mask.unsqueeze(-1).to(hs.dtype)
        return (hs * m).sum(1) / m.sum(1).clamp(min=1)

    def forward(self, input_ids=None, attention_mask=None, **kw):
        return {"logits": self.cls_head(self.pooled(input_ids, attention_mask))}
