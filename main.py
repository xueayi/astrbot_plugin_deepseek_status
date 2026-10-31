"""AstrBot plugin for DeepSeek's official status page."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import aiohttp

from astrbot.api import AstrBotConfig, logger, star
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

from .status import API_ROOT, format_changes, format_current, snapshot

PLUGIN_NAME = "astrbot_plugin_deepseek_status"


class Main(star.Star):
    """Poll DeepSeek's current status and push changes to one group."""

    def __init__(self, context: star.Context, config: AstrBotConfig) -> None:
        super().__init__(context, config)
        self.config = config
        self.state_path = (
            Path(get_astrbot_plugin_data_path()) / PLUGIN_NAME / "state.json"
        )
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    @filter.on_astrbot_loaded()
    async def on_loaded(self, *args, **kwargs) -> None:
        """Start polling after AstrBot's platforms are ready."""
        if self.config.get("enabled", True) and not self._task:
            self._task = asyncio.create_task(self._poll_loop())

    async def terminate(self) -> None:
        """Stop the polling task on plugin unload."""
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        interval = max(60, int(self.config.get("poll_interval_seconds", 60)))
        while not self._stop.is_set():
            try:
                await self.check_once()
            except Exception as exc:
                logger.error(
                    f"[{PLUGIN_NAME}] Poll failed: {type(exc).__name__}: {exc!r}"
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _fetch(self) -> tuple[dict, dict]:
        timeout = aiohttp.ClientTimeout(total=25)
        proxy = self.config.get("proxy") or None
        end = int(time.time())
        params = {"start_at_seconds": end - 2 * 86400, "end_at_seconds": end}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{API_ROOT}/summary/active", proxy=proxy) as resp:
                resp.raise_for_status()
                active = (await resp.json())["data"]
            async with session.get(
                f"{API_ROOT}/change/list", params=params, proxy=proxy
            ) as resp:
                resp.raise_for_status()
                history = (await resp.json())["data"]
        return active, history

    async def check_once(self) -> str:
        """Fetch, push and persist one status snapshot.

        Returns:
            One of ``initial``, ``changed`` or ``unchanged``.

        Raises:
            ValueError: If the target session or API response is invalid.
        """
        async with self._lock:
            target = str(self.config.get("target_session", "")).strip()
            if not target or ":GroupMessage:" not in target:
                raise ValueError(
                    "Configure target_session as platform:GroupMessage:group_id"
                )
            active, history = await self._fetch()
            current, events = snapshot(active, history)
            previous = None
            if self.state_path.exists():
                previous = json.loads(self.state_path.read_text(encoding="utf-8"))
            if previous is None:
                message = format_current(active)
                result = "initial"
            else:
                seen = previous.get("fingerprints", {})
                changed = [
                    event
                    for event in events
                    if seen.get(str(event["change_id"]))
                    != current[str(event["change_id"])]
                ]
                message = format_changes(changed) if changed else ""
                result = "changed" if changed else "unchanged"
            if message:
                sent = await self.context.send_message(
                    target, MessageChain().message(message)
                )
                if not sent:
                    raise ValueError(f"No AstrBot platform for {target}")
                logger.info(f"[{PLUGIN_NAME}] Pushed {result} status to {target}")
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps({"fingerprints": current}), encoding="utf-8")
            temp.replace(self.state_path)
            return result

    @filter.command_group("dsstatus")
    def dsstatus(self):
        """DeepSeek status commands."""

    @dsstatus.command("status")
    async def status_command(self, event: AstrMessageEvent):
        """Reply with the current official status."""
        try:
            active, _ = await self._fetch()
            yield event.plain_result(format_current(active))
        except Exception as exc:
            logger.error(f"[{PLUGIN_NAME}] Status query failed: {exc}")
            yield event.plain_result("DeepSeek 官方状态查询失败，请稍后重试。")
