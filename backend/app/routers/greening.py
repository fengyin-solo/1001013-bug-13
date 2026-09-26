"""绿化管护接口：登记管护、状态流转与病虫害防治登记。

同一管护区域同一周期重复提交只生效一次（幂等返回已有在办记录）；
已结束记录只可查询不可改动；历史管护周期不会被新提交覆盖。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.greening import DISPLAY_FIELDS, GreeningService

router = APIRouter(prefix="/api/greening", tags=["绿化管护"])

service = GreeningService()

LIST_FIELDS = DISPLAY_FIELDS
STATUSES = ["待管护", "管护中", "已管护", "待补植"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按管护编号或管护区域检索"),
    status: str | None = Query(default=None, description="待管护、管护中、已管护、待补植"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按管护编号/管护区域与状态过滤绿化管护列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出绿化管护清单：返回当前全量数据，历史已结束记录同样可查。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "greening", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条绿化管护明细（含防治说明）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"绿化管护 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条绿化管护。

    同一管护区域同一周期重复提交时幂等返回原在办记录；该周期已有结束记录时
    拒绝登记，避免历史周期被覆盖。
    """
    entry, message, duplicated = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry, duplicated=duplicated)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行安排管护、病虫害防治登记、登记补植；已结束记录与缺防治说明会被拦下。"""
    action = str(payload.values.get("action") or "").strip()
    values = {key: value for key, value in payload.values.items() if key != "action"}
    entry, message = service.run_action(entry_id, action, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
