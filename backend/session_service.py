"""
session_service.py — 被试分组与任务序列

为什么需要它（导师 2026-06-16 反馈 "conditions … directly comparable"）：
原先条件由前端 URL 参数 ?condition=A 决定，缺省落 A。这有两个问题：
分配不随机、两组人数不平衡；而且被试自己能看到并改这个参数。

分组用 **区组随机化（block randomisation）**而不是纯随机：纯随机在 n=40 时
出现 24:16 这类失衡的概率不低，失衡会直接削弱统计检验力。区组随机化在每
个 block 内保证两组等量，同时保留组内顺序的随机性。

台账 append-only：每次分配写一行，进程重启后从台账重建计数，不会因为重启
把已分配的人再算一遍或丢掉平衡状态。
"""
from __future__ import annotations

import json
import os
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from storage import data_file

ASSIGNMENT_LOG = data_file("assignments.jsonl")

CONDITIONS = ("A", "B")

# 响应选项的左右顺序，与条件正交做平衡。
#
# 为什么要平衡：Accept 固定在左侧会带来轻微的首位优势，而接受率是本研究的
# 头号因变量。固定顺序本身**不会**混淆组间比较——它对两组是相同的常数，只
# 影响绝对水平。平衡化买到的不是"能检验位置效应"（每格 10 人，检验没有功效，
# 报无显著差异反而是弱证据），而是让位置效应被打散而非系统性累积，且答辩时
# "顺序做了平衡"是一句到此为止的答案。
#
# 同一被试内**始终一致**：三个情境、四个电器都用同一个顺序。每张卡都变会
# 让界面像在乱跳，并把被试的注意力从内容引到布局上。
OPTION_ORDERS = ("accept_first", "reject_first")

# 四个格子各一个，因此区组仍是 4：A/左、A/右、B/左、B/右。
# n=40 → 10 个区组 → 恰好 20A/20B，且每个条件内部 10 左 10 右。
CELLS = tuple((c, o) for c in CONDITIONS for o in OPTION_ORDERS)
BLOCK_SIZE = len(CELLS)

# 固定任务序列 —— 两个条件完全一致。
#
# 为什么固定而不是让被试自选场景：原先前端是一个自由下拉框，还含 `live`
# （拉当天真实电价）。不同被试会看到不同的价格曲线，隔天再跑的人看到的又
# 不一样，两组之间的差异就无法归因于解释方式。实验期间序列写死、排除 live。
#
# 为什么所有人同一个顺序而不做拉丁方：顺序效应此时对两组是**相同**的常数，
# 因此不会混淆组间比较；而 n≈40 拆成多个顺序会让每格样本过小。代价是无法
# 估计顺序效应本身——已在论文 Limitations 记录。
TASK_SEQUENCE = ["S3", "S1", "S2"]

_lock = Lock()


def _ensure_trailing_newline() -> None:
    """
    追加前确保台账以换行结尾。

    如果上一次写入被中断留下半截行（末尾没有换行），直接 append 会把新记录接
    在半截行后面，拼成一行无效 JSON——解析时被跳过，于是**这个被试分了组却没
    被记账**，后续区组平衡随之错位。模拟中已复现：40 次分配只记下 39 条。
    """
    if not ASSIGNMENT_LOG.exists():
        return
    try:
        with ASSIGNMENT_LOG.open("rb") as fh:
            if fh.seek(0, 2) == 0:          # 空文件
                return
            fh.seek(-1, 2)
            if fh.read(1) == b"\n":
                return
    except OSError:
        return
    with ASSIGNMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n")


def _read_counts() -> dict[str, int]:
    """从 append-only 台账重建各条件已分配人数。文件不存在＝全零。"""
    counts = {c: 0 for c in CONDITIONS}
    if not ASSIGNMENT_LOG.exists():
        return counts
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # 半截行（写入时被中断）跳过并继续，不让它污染计数
                continue
            c = rec.get("condition")
            if c in counts:
                counts[c] += 1
    return counts


def _read_cell_counts() -> dict[tuple[str, str], int]:
    """按 (条件, 选项顺序) 统计台账。

    2026-09-12 之前的记录没有 option_order 字段；它们按当时的实现一律是
    Accept 在左，因此补成 accept_first 而不是丢弃——丢弃会让区组配额从
    错误的基数重新开始。
    """
    counts: dict[tuple[str, str], int] = {c: 0 for c in CELLS}
    if not ASSIGNMENT_LOG.exists():
        return counts
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cell = (rec.get("condition"), rec.get("option_order", "accept_first"))
            if cell in counts:
                counts[cell] += 1
    return counts


def _next_cell(cell_counts: dict[tuple[str, str], int]) -> tuple[str, str]:
    """
    区组随机化：在当前区组内，从尚未配满的格子中随机取一个。
    一个格子＝(条件, 选项顺序)，区组填满后自动进入下一区组。
    """
    total = sum(cell_counts.values())
    filled_blocks = total // BLOCK_SIZE
    quota = filled_blocks + 1              # 每个格子在每个区组里各占一个名额

    available = [c for c in CELLS if cell_counts.get(c, 0) < quota]
    if not available:                      # 理论上不该发生；退化为纯随机而不是静默出错
        available = list(CELLS)
    return random.choice(available)


def _pilot_cell(n_assigned: int) -> tuple[str, str] | None:
    """
    定性访谈专用：按 PILOT_CELL_SEQUENCE 给第 n 个人指定格子，用完后回到区组随机化。

    格式 "A:accept_first,B:accept_first,..."。只由 start-pilot.ps1 设置（独立 DATA_DIR），
    正式实验的部署从不设置它，因此正式分组路径不受影响。

    为什么需要：访谈 n=6、每组 3 人。区组大小是 4，六个人里第二个区组只用两格，
    有 1/3 的概率两格同条件，变成 4:2。按人挑条件更糟——研究者会按"这个人看得懂图"
    去分。事先写死顺序，两样问题都没有。只决定谁看哪一版，不改变任何人看到的内容。
    """
    raw = os.environ.get("PILOT_CELL_SEQUENCE", "").strip()
    if not raw:
        return None
    seq = []
    for part in raw.split(","):
        cond, _, order = part.strip().partition(":")
        if cond not in CONDITIONS or order not in OPTION_ORDERS:
            raise ValueError(f"PILOT_CELL_SEQUENCE: bad entry {part!r}")
        seq.append((cond, order))
    return seq[n_assigned] if n_assigned < len(seq) else None


def _find_existing(prolific_pid: str) -> dict | None:
    """已经分过组的 Prolific ID 直接返回原分配。见 assign_session 的幂等说明。"""
    if not prolific_pid or not ASSIGNMENT_LOG.exists():
        return None
    found = None
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("prolific_pid") == prolific_pid:
                found = rec          # 取最早那条之外的都不该存在；保底取最后一条
                break
    return found


def assign_session(prolific_pid: str | None = None) -> dict:
    """
    分配一个被试会话。返回 participant_id / condition / option_order / task_sequence。

    **幂等**：同一个 Prolific ID 再次请求时返回原来的分配，不新分。原因有二——
    一是被试刷新页面就会换组，这会把人暴露在两个条件下并直接毁掉他的数据；
    二是每次请求都写一条台账会虚增计数，把区组平衡算错。实测中 React 严格模式
    在开发环境下双调用 effect，一次页面加载就产生了两条记录。

    participant_id 不使用 Prolific ID 本身作为主键：Prolific ID 是可回溯到
    个人的标识符，实验日志里只存我们自己生成的匿名 id，Prolific ID 单独存在
    分配台账里用于发钱，两者分开。
    """
    with _lock:
        if prolific_pid:
            existing = _find_existing(prolific_pid)
            if existing:
                return {
                    "participant_id": existing["participant_id"],
                    "condition": existing["condition"],
                    # 老记录没有这个字段，按当时的实现补 accept_first。
                    "option_order": existing.get("option_order", "accept_first"),
                    "task_sequence": list(TASK_SEQUENCE),
                }

        cell_counts = _read_cell_counts()
        condition, option_order = (_pilot_cell(sum(cell_counts.values()))
                                   or _next_cell(cell_counts))
        participant_id = "p_" + secrets.token_hex(6)

        record = {
            "participant_id": participant_id,
            "condition": condition,
            "option_order": option_order,
            "prolific_pid": prolific_pid or "",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "seq": sum(cell_counts.values()) + 1,
        }
        _ensure_trailing_newline()
        with ASSIGNMENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()          # 立刻落盘：分了组却没记账，会造成永久失衡

    return {
        "participant_id": participant_id,
        "condition": condition,
        "option_order": option_order,
        "task_sequence": list(TASK_SEQUENCE),
    }


def assignment_summary() -> dict:
    """给研究者看的分组进度，不暴露给被试。"""
    counts = _read_counts()
    cells = _read_cell_counts()
    return {
        "counts": counts,
        "cells": {f"{c}/{o}": n for (c, o), n in sorted(cells.items())},
        "total": sum(counts.values()),
        "block_size": BLOCK_SIZE,
    }
