"""绿化管护业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from typing import Any

from app.store import store

MODULE = "greening"

# 台账字段：登记时逐字段按名字落库，管护编号由服务端生成，避免与管护人员等字段错位
ENTRY_FIELDS = ["管护区域", "管护周期", "植被类型", "修剪频次", "浇水周期", "管护人员"]
REQUIRED_FIELDS = ["管护区域", "管护周期", "植被类型"]

STATUS_PENDING = "待管护"
STATUS_RUNNING = "管护中"
STATUS_REPLANT = "待补植"
STATUS_DONE = "已管护"
STATUS_ORDER = [STATUS_PENDING, STATUS_RUNNING, STATUS_REPLANT, STATUS_DONE]
# 已结束的状态：能查到，但不能再改动
ENDED_STATUSES = {STATUS_DONE}

# 动作 → (允许的前置状态, 目标状态)；防治登记必须带防治说明
ACTION_RULES = {
    "安排管护": ([STATUS_PENDING], STATUS_RUNNING),
    "防治登记": ([STATUS_RUNNING], STATUS_DONE),
    "登记补植": ([STATUS_PENDING, STATUS_RUNNING], STATUS_REPLANT),
    "补植完成": ([STATUS_REPLANT], STATUS_DONE),
}

CODE_PREFIX = "GREE"
CODE_PATTERN = re.compile(r"^GREE-(\d+)$")


class GreeningService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("管护编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记一条绿化管护。

        返回 (记录, 缺少的必填字段, 是否新建)。同一管护区域在同一管护周期
        只允许存在一条记录：重复提交（连点、刷新重进）直接返回已有记录，
        不再生成新的管护编号，历史周期的记录也不会被新提交覆盖。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        area = str(values.get("管护区域")).strip()
        period = str(values.get("管护周期")).strip()
        for row in rows:
            if str(row.get("管护区域", "")).strip() == area and str(row.get("管护周期", "")).strip() == period:
                return row, [], False
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["管护编号"] = self._next_code(rows)
        for field in ENTRY_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        entry["病虫害防治"] = str(values.get("病虫害防治") or "").strip()
        entry["status"] = STATUS_PENDING
        rows.append(entry)
        self._sync_status(entry)
        return entry, [], True

    def run_action(self, entry_id: int, action: str, note: str = "") -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"绿化管护 {entry_id} 不存在或已归档"
        current = str(entry.get("status", ""))
        if current in ENDED_STATUSES:
            return None, f"绿化管护 {entry.get('管护编号', entry_id)} 已结束（{current}），仅供查询，不能再改动"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于绿化管护可执行范围"
        allowed_from, target = ACTION_RULES[action]
        if current not in allowed_from:
            return None, f"当前状态为「{current}」，不能执行「{action}」"
        if action == "防治登记":
            if not note:
                return None, "防治登记必须填写防治说明，说明会一并存入台账"
            entry["病虫害防治"] = note
        entry["status"] = target
        self._sync_status(entry)
        return entry, f"绿化管护已{action}，状态更新为「{target}」"

    @staticmethod
    def _sync_status(entry: dict[str, Any]) -> None:
        """状态单一来源：列表、详情、防治弹窗都读这两个字段，保证三处结论一致。"""
        status = str(entry.get("status", STATUS_PENDING))
        entry["管护状态"] = status
        entry["pending"] = status not in ENDED_STATUSES
        entry["abnormal"] = status == STATUS_REPLANT

    @staticmethod
    def _next_code(rows: list[dict[str, Any]]) -> str:
        serial = 0
        for row in rows:
            match = CODE_PATTERN.match(str(row.get("管护编号", "")))
            if match:
                serial = max(serial, int(match.group(1)))
        return f"{CODE_PREFIX}-{serial + 1:04d}"
