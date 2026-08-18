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
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ASSIGNMENT_LOG = Path(__file__).parent / "assignments.jsonl"

BLOCK_SIZE = 4          # 每 4 人一个区组：2A + 2B
CONDITIONS = ("A", "B")

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


def _next_condition(counts: dict[str, int]) -> str:
    """
    区组随机化：在当前区组内，从尚未配满的条件中随机取一个。
    区组填满后自动进入下一区组。
    """
    total = sum(counts.values())
    filled_blocks, pos_in_block = divmod(total, BLOCK_SIZE)
    per_condition_per_block = BLOCK_SIZE // len(CONDITIONS)
    quota = filled_blocks * per_condition_per_block + per_condition_per_block

    available = [c for c in CONDITIONS if counts[c] < quota]
    if not available:                      # 理论上不该发生；退化为纯随机而不是静默出错
        available = list(CONDITIONS)
    return random.choice(available)


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
    分配一个被试会话。返回 participant_id / condition / task_sequence。

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
                    "task_sequence": list(TASK_SEQUENCE),
                }

        counts = _read_counts()
        condition = _next_condition(counts)
        participant_id = "p_" + secrets.token_hex(6)

        record = {
            "participant_id": participant_id,
            "condition": condition,
            "prolific_pid": prolific_pid or "",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "seq": sum(counts.values()) + 1,
        }
        _ensure_trailing_newline()
        with ASSIGNMENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()          # 立刻落盘：分了组却没记账，会造成永久失衡

    return {
        "participant_id": participant_id,
        "condition": condition,
        "task_sequence": list(TASK_SEQUENCE),
    }


def assignment_summary() -> dict:
    """给研究者看的分组进度，不暴露给被试。"""
    counts = _read_counts()
    return {"counts": counts, "total": sum(counts.values()), "block_size": BLOCK_SIZE}
