"""绿化管护业务规则：防重登记、状态流转、防治登记与历史保护都收在这里。

设计约定（对应业务诉求）：
- 「管护区域 + 管护周期」唯一标识同一批次管护：同一批次无论点几次提交，只生效一条。
- 同一管护区域同一周期只允许存在一条在办记录；历史记录永不被新提交覆盖。
- 管护编号由后端按序号生成，登记时只按字段名整体落库，避免编号与管护人员错位。
- 病虫害防治登记后管护状态流转为「已管护」，防治说明随记录持久化。
- 已管护、待补植视为已结束记录，只允许查看，不允许再执行动作或被覆盖。
"""
from __future__ import annotations

import threading
from typing import Any

from app.store import store

MODULE = "greening"
REQUIRED_FIELDS = ["管护区域", "植被类型"]
# 登记表单可提交的全部业务字段，按名字整体存取，杜绝串行错位。
FORM_FIELDS = [
    "管护区域",
    "植被类型",
    "修剪频次",
    "浇水周期",
    "管护人员",
    "管护周期",
]
DISPLAY_FIELDS = [
    "管护编号",
    "管护区域",
    "植被类型",
    "修剪频次",
    "浇水周期",
    "病虫害防治",
    "管护人员",
    "管护状态",
]

STATUS_PENDING = "待管护"
STATUS_DOING = "管护中"
STATUS_DONE = "已管护"
STATUS_REPLANT = "待补植"
STATUS_ORDER = [STATUS_PENDING, STATUS_DOING, STATUS_DONE, STATUS_REPLANT]
# 已结束的状态：只读，不再接受任何动作，也不允许被新提交覆盖。
CLOSED_STATUSES = [STATUS_DONE, STATUS_REPLANT]
ACTIVE_STATUSES = [STATUS_PENDING, STATUS_DOING]

# 简单正向流转；「病虫害防治」直接把管护收尾为已管护。
ACTION_RULES = {
    "安排管护": STATUS_DOING,
    "开始管护": STATUS_DOING,
    "病虫害防治": STATUS_DONE,
    "登记补植": STATUS_REPLANT,
}

# 串行化登记与状态流转，防止并发双击产生重复记录。
_lock = threading.RLock()


def _clean(values: dict[str, Any], field: str) -> str:
    return str(values.get(field) or "").strip()


class GreeningService:
    # ------------------------------------------------------------------ 查询
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
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("管护编号", "")) or key in str(row.get("管护区域", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    # ------------------------------------------------------------------ 登记
    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """登记一条管护。

        返回 (记录, 错误或提示信息, 是否命中已有记录)。命中同区域同周期的在办记录时
        幂等返回原记录，不再新增编号；命中已结束记录时拒绝，保护历史周期。
        """
        missing = [field for field in REQUIRED_FIELDS if not _clean(values, field)]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}", False

        area = _clean(values, "管护区域")
        period = _clean(values, "管护周期")

        with _lock:
            duplicate = self._find_by_area_period(area, period)
            if duplicate is not None:
                if duplicate.get("status") in CLOSED_STATUSES:
                    return (
                        None,
                        f"管护区域「{area}」在{period or '本周期'}已存在"
                        f"{duplicate.get('status')}记录（{duplicate.get('管护编号')}），"
                        "历史管护周期不可覆盖，请更换管护周期后再登记",
                        False,
                    )
                # 在办记录：重复提交只生效一次，直接把原记录返回给前端。
                return (
                    duplicate,
                    f"该管护区域本周期已有在办记录 {duplicate.get('管护编号')}，重复提交未重复建档",
                    True,
                )

            rows = store.rows(MODULE)
            entry: dict[str, Any] = {
                "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1
            }
            entry["管护编号"] = self._next_code(rows)
            for field in FORM_FIELDS:
                entry[field] = _clean(values, field)
            # 防治说明在登记时尚未填写，给空串占位而不是丢弃字段。
            entry["病虫害防治"] = ""
            entry["status"] = STATUS_PENDING
            entry["pending"] = True
            entry["abnormal"] = False
            entry["管护状态"] = STATUS_PENDING
            rows.append(entry)
            return entry, "绿化管护已登记", False

    # ------------------------------------------------------------------ 动作
    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        with _lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"绿化管护 {entry_id} 不存在或已归档"
            if entry.get("status") in CLOSED_STATUSES:
                return None, f"{entry.get('管护编号')} 已结束（{entry.get('status')}），记录已归档不可改动"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于绿化管护可执行范围"

            if action == "病虫害防治":
                note = _clean(values, "病虫害防治") or _clean(values, "防治说明")
                if not note:
                    return None, "请先填写病虫害防治说明再提交登记"
                entry["病虫害防治"] = note

            target = ACTION_RULES[action]
            entry["status"] = target
            entry["管护状态"] = target
            entry["pending"] = target not in CLOSED_STATUSES
            entry["abnormal"] = False
            return entry, f"绿化管护已{action}"

    # ------------------------------------------------------------------ 内部
    def _find_by_area_period(
        self, area: str, period: str
    ) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("管护区域", "")).strip() != area:
                continue
            if str(row.get("管护周期", "")).strip() != period:
                continue
            return row
        return None

    @staticmethod
    def _next_code(rows: list[dict[str, Any]]) -> str:
        max_seq = 0
        for row in rows:
            code = str(row.get("管护编号", ""))
            digits = code.rsplit("-", 1)[-1]
            if digits.isdigit():
                max_seq = max(max_seq, int(digits))
        return f"GREE-{max_seq + 1:04d}"
