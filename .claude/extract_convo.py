#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取 Claude Code JSONL 转录中的对话正文：人类消息完整、助手文本截断、工具仅记名。"""
import json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

path = sys.argv[1]
max_assistant = int(sys.argv[2]) if len(sys.argv) > 2 else 600

def blocks(content):
    """归一化 content 为 block 列表。"""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return []

idx = 0
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = o.get("type")
        msg = o.get("message") or {}
        role = msg.get("role") or t
        ts = (o.get("timestamp") or "")[:19]

        if t not in ("user", "assistant"):
            continue

        texts, tools, tool_results = [], [], 0
        for b in blocks(msg.get("content")):
            if not isinstance(b, dict):
                if isinstance(b, str):
                    texts.append(b)
                continue
            bt = b.get("type")
            if bt == "text":
                texts.append(b.get("text", ""))
            elif bt == "tool_use":
                tools.append(b.get("name", "?"))
            elif bt == "tool_result":
                tool_results += 1

        body = "\n".join(x for x in texts if x).strip()

        # 跳过纯工具结果的 user 行（工具回灌，非人类发言）
        is_human = (role == "user") and body and tool_results == 0 and not tools
        is_asst_text = (role == "assistant") and body

        if is_human:
            idx += 1
            print(f"\n{'='*70}\n[#{idx} 人类 {ts}]\n{'='*70}\n{body}")
        elif is_asst_text:
            shown = body if len(body) <= max_assistant else body[:max_assistant] + f"  …(+{len(body)-max_assistant}字)"
            tinfo = f"  [调用工具: {', '.join(tools)}]" if tools else ""
            print(f"\n--- 助手 {ts}{tinfo} ---\n{shown}")
        # 助手纯工具调用行（无文本）静默跳过，避免噪声
