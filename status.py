"""Parse and format data from DeepSeek's official status page."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_URL = "https://status.deepseek.com/"
PAGE_ID = 6410630422455
API_ROOT = f"https://status.deepseek.com/api/status-page/{PAGE_ID}"

LABELS = {
    "investigating": "调查中",
    "identified": "已确认",
    "monitoring": "监控中",
    "resolved": "已解决",
    "scheduled": "已计划",
    "in_progress": "进行中",
    "completed": "已完成",
    "operational": "正常",
    "degraded": "性能下降",
    "partial_outage": "部分中断",
    "full_outage": "完全中断",
    "maintenance": "维护中",
}


def snapshot(active: dict, history: dict) -> tuple[dict[str, str], list[dict]]:
    """Return current event fingerprints and events from both official feeds.

    Args:
        active: The summary/active response data.
        history: The change/list response data.

    Returns:
        A mapping of event IDs to fingerprints and a deduplicated event list.

    Raises:
        ValueError: If the official response has an unexpected shape.
    """
    page = active.get("page")
    if not isinstance(page, dict) or page.get("page_id") != PAGE_ID:
        raise ValueError("Unexpected DeepSeek status page ID")
    if not isinstance(active.get("active_changes"), list):
        raise ValueError("Missing active_changes")
    if not isinstance(history.get("items"), list):
        raise ValueError("Missing history items")

    by_id = {}
    for item in history["items"] + active["active_changes"]:
        if isinstance(item, dict) and item.get("change_id") is not None:
            by_id[str(item["change_id"])] = item
    events = sorted(by_id.values(), key=lambda item: item.get("start_at_seconds", 0))
    fingerprints = {}
    for item in events:
        updates = item.get("updates") or []
        latest = updates[-1] if updates else {}
        fingerprints[str(item["change_id"])] = (
            f"{item.get('status', '')}:{latest.get('update_id', '')}"
        )
    return fingerprints, events


def format_current(active: dict) -> str:
    """Format the current official service status for a group message.

    Args:
        active: The summary/active response data.

    Returns:
        A Chinese plain text status message.
    """
    page = active["page"]
    current = active["active_changes"]
    component_status = {
        c["component_id"]: c.get("status", "operational")
        for event in current
        for c in event.get("affected_components", [])
        if isinstance(c, dict) and c.get("component_id")
    }
    lines = [
        "【DeepSeek 官方服务状态】",
        f"整体：{'正常运行' if not current else f'{len(current)} 个进行中事件'}",
        "组件：",
    ]
    for comp in page.get("components", []):
        status = component_status.get(comp.get("component_id"), "operational")
        lines.append(f"  {comp.get('name', '未知组件')}：{LABELS.get(status, status)}")
    if current:
        lines.append("进行中事件：")
        for event in current:
            lines.append(
                f"  {event.get('title', '未命名')}（{LABELS.get(event.get('status'), event.get('status', '未知'))}）"
            )
    lines.extend(
        [
            f"查询时间：{datetime.now(ZoneInfo('Asia/Shanghai')):%Y-%m-%d %H:%M:%S}",
            f"来源：{STATUS_URL}",
        ]
    )
    return "\n".join(lines)


def format_changes(events: list[dict]) -> str:
    """Format changed official incidents as one group message.

    Args:
        events: New or updated status page events.

    Returns:
        A Chinese plain text notification.
    """
    lines = ["【DeepSeek 官方状态更新】"]
    for event in events:
        updates = event.get("updates") or []
        latest = updates[-1] if updates else {}
        status = event.get("status", "未知")
        lines.append(
            f"{event.get('title', '未命名事件')}：{LABELS.get(status, status)}"
        )
        description = latest.get("description") or event.get("description") or ""
        if description:
            lines.append(str(description).split("\n\n")[0][:300])
        components = [c.get("name", "") for c in event.get("affected_components", [])]
        if components:
            lines.append("影响组件：" + "、".join(components))
    lines.extend(
        [
            f"查询时间：{datetime.now(ZoneInfo('Asia/Shanghai')):%Y-%m-%d %H:%M:%S}",
            f"来源：{STATUS_URL}",
        ]
    )
    return "\n".join(lines)
