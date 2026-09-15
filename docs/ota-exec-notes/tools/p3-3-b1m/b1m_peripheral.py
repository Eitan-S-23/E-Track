#!/usr/bin/env python3
"""P3-3 B1-M 最小机制验证：PC 侧仿真外设（Windows / winrt 3.2.1 直连）。

用途：只验证「应用层能否控制 ATT 写响应」这一机制，不做完整 OTA 协议仿真。
三种策略各观测一次写：立即应答 / 延迟应答 / 不应答（到期受控释放）。

## 为什么不用 bless（本轮实测结论，证据见能力报告 §2.5）

- `bless==0.3.0`：装不上（元数据钉死 `winrt-Windows.Devices.Bluetooth==2.0.0b1`，该版本
  已不在 PyPI）。
- `bless==0.2.6`：装得上但**导不进来** —— `backends/winrt/{server,service,characteristic}.py`
  **无条件** `import bleak_winrt.*`（无版本分支），且 `service.py` 依赖的
  `bleak.backends.winrt.service` 已被 `bleak>=1.0` 移除。补齐需源码编译只有 sdist 的
  `bleak-winrt==1.2.0` 并把两代 WinRT 投影（pywinrt 1.x 与 winrt-runtime 3.2.1）混进
  同一进程，不作此变通。
- 因此本 harness 直接用 `winrt-*==3.2.1`（已安装）建 GATT server —— 即 bless 所包装的
  同一个 API 面；符号名经 `.cache/p3-3-t1b/direct_api_probe.py` 实测确认，非凭记忆书写。

## 机制实现要点

- 写处理器**不执行**任何自动应答：回调线程只取 deferral 并转交，随即返回。
- 延迟/不应答**不得**靠阻塞事件循环实现：全部 WinRT 异步等待与应答在**一条**专用
  asyncio 线程内以可取消任务完成（`asyncio.wait(FIRST_COMPLETED)` + `Event`），
  到期或受控释放时取消 sleep 任务。
- 到实验截止：释放全部挂起请求 → 停广播 → 结束本次记录的进程。

## 证据强度的已知边界（不得越界解释）

- 本文件记录「PC 侧是否发出了 `respond()`」及其时刻，**不证明**物理写是否已取消；
  中央侧是否收到 ATT 写响应只能由中央侧观测判定。
- 本文件不采集链路连接态：winrt 的 `GattLocalCharacteristic.subscribed_clients` 只在
  中央**订阅**时填充，写特征无 notify 属性时恒为空，不能当连接证据。「连接仍有效」
  以中央侧（Android logcat 的 GATT 回调）观测为准。

用法：
    python b1m_peripheral.py --strategy immediate --run-dir <项目内目录>
    python b1m_peripheral.py --strategy delayed --delay 3 --run-dir ...
    python b1m_peripheral.py --strategy withhold --window 20 --run-dir ...
    python b1m_peripheral.py --strategy ... --run-dir ... --setup-only   # 只建服务不广播
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

# 产品契约 UUID：服务 FFF0、写特征 FFF2。
# 只声明 WRITE(8)（有响应写），强制中央侧走 write-with-response，判据才成立。
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"


class Recorder:
    """单调计数 + 双落盘（文本给人看，JSONL 给机器核）。"""

    def __init__(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = run_dir
        self.t0 = time.perf_counter_ns()
        self._lock = threading.Lock()
        self._txt = (run_dir / "peripheral.log").open("w", encoding="utf-8")
        self._jsonl = (run_dir / "peripheral.jsonl").open("w", encoding="utf-8")

    def us(self) -> int:
        """PC 端单调微秒（PC 侧唯一判据时钟；与其他设备的单调钟不可直接相减）。"""
        return (time.perf_counter_ns() - self.t0) // 1000

    def log(self, event: str, **fields: Any) -> Dict[str, Any]:
        rec = {"event": event, "mono_us": self.us(), "wall": time.time(), **fields}
        line = json.dumps(rec, ensure_ascii=False, default=str)
        with self._lock:
            self._jsonl.write(line + "\n")
            self._jsonl.flush()
            kv = " ".join(f"{k}={v}" for k, v in fields.items())
            self._txt.write(f"[{rec['mono_us']:>12} us] {event} {kv}\n")
            self._txt.flush()
        return rec

    def close(self) -> None:
        self._txt.close()
        self._jsonl.close()


def _safe(value: Any) -> str:
    try:
        return str(value)
    except Exception as exc:  # noqa: BLE001
        return f"<unprintable: {type(exc).__name__}: {exc}>"


class LoopThread:
    """唯一承载 WinRT 异步操作的 asyncio 线程（延迟任务可取消，不阻塞任何事件循环）。"""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="b1m-asyncio", daemon=True)
        self._ready = threading.Event()

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=5.0)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.call_soon(self._ready.set)
        self._loop.run_forever()

    def submit(self, coro) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def call_soon(self, fn, *args) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)


class Responder:
    """写请求登记 + 按策略应答；WinRT 回调线程只做登记，绝不应答。"""

    def __init__(self, rec: Recorder, strategy: str, hold_s: float) -> None:
        self._rec = rec
        self._strategy = strategy
        self._hold_s = hold_s
        self._loop = LoopThread()
        self._lock = threading.Lock()
        self._seq = 0
        self._pending: Dict[int, asyncio.Event] = {}

    def start(self) -> None:
        self._loop.start()

    def seq(self) -> int:
        with self._lock:
            return self._seq

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    # ---- WinRT 回调线程 ----
    def on_write(self, sender: Any, args: Any) -> None:
        arrival = self._rec.us()
        deferral = args.get_deferral()
        if deferral is None:
            self._rec.log("write_no_deferral", strategy=self._strategy)
            return
        with self._lock:
            self._seq += 1
            seq = self._seq
        # 交给 asyncio 线程去 await 请求对象并按策略应答。
        self._loop.submit(self._handle(seq, sender, args, arrival, deferral))

    async def _handle(self, seq: int, sender: Any, args: Any, arrival: int, deferral: Any) -> None:
        try:
            request = await asyncio.wait_for(args.get_request_async(), timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            self._rec.log("write_request_async_error", seq=seq,
                          error=f"{type(exc).__name__}: {exc}")
            return

        option = getattr(request, "option", None)
        with_response = None
        try:
            from winrt.windows.devices.bluetooth.genericattributeprofile import GattWriteOption

            with_response = option == GattWriteOption.WRITE_WITH_RESPONSE
        except Exception as exc:  # noqa: BLE001
            self._rec.log("write_option_probe_error", error=f"{type(exc).__name__}: {exc}")

        raw = bytes(request.value or b"")
        release = asyncio.Event()
        with self._lock:
            self._pending[seq] = release

        self._rec.log(
            "write_request",
            seq=seq,
            strategy=self._strategy,
            chr_uuid=_safe(getattr(sender, "uuid", sender)),
            option=_safe(option),
            with_response=with_response,
            length=len(raw),
            payload_hex=raw[:16].hex(),
            hold_s=self._hold_s,
        )

        released = False
        timer = asyncio.ensure_future(asyncio.sleep(self._hold_s))
        waiter = asyncio.ensure_future(release.wait())
        try:
            await asyncio.wait({timer, waiter}, return_when=asyncio.FIRST_COMPLETED)
            released = waiter.done()
        finally:
            # 取消延迟任务与等待任务，避免残留。
            for task in (timer, waiter):
                if not task.done():
                    task.cancel()
        started = self._rec.us()
        try:
            request.respond()
            respond_err = None
        except Exception as exc:  # noqa: BLE001 - 应答失败本身就是要记录的观测
            respond_err = f"{type(exc).__name__}: {exc}"
        try:
            deferral.complete()
            complete_err = None
        except Exception as exc:  # noqa: BLE001
            complete_err = f"{type(exc).__name__}: {exc}"
        done = self._rec.us()
        with self._lock:
            self._pending.pop(seq, None)
        self._rec.log(
            "respond",
            seq=seq,
            strategy=self._strategy,
            released_early=released,
            arrival_us=arrival,
            held_us=done - arrival,
            respond_us=done - started,
            state_before_respond=_safe(getattr(request, "state", None)),
            respond_error=respond_err,
            complete_error=complete_err,
        )

    def release_all(self, reason: str) -> None:
        """受控释放：唤醒所有挂起项的 Event，由 asyncio 线程随即应答。"""
        with self._lock:
            events: List[asyncio.Event] = list(self._pending.values())
            pending = len(events)
        for ev in events:
            self._loop.call_soon(ev.set)
        self._rec.log("release_all", reason=reason, pending=pending)

    def stop(self) -> None:
        self._loop.stop()


class B1MPeripheral:
    """WinRT GATT server：建服务/特征、注册写处理器、起停广播。"""

    def __init__(self, rec: Recorder, name: str, responder: Responder, setup_only: bool) -> None:
        self._rec = rec
        self._name = name
        self._responder = responder
        self._setup_only = setup_only
        self._provider: Any = None
        self._char: Any = None
        self._tokens: List[Any] = []

    async def setup(self) -> None:
        from winrt.windows.devices.bluetooth.genericattributeprofile import (
            GattCharacteristicProperties,
            GattLocalCharacteristicParameters,
            GattProtectionLevel,
            GattServiceProvider,
            GattServiceProviderAdvertisingParameters,
        )
        result = await GattServiceProvider.create_async(UUID(SERVICE_UUID))
        self._provider = result.service_provider
        self._rec.log("service_provider_created", error=_safe(result.error))
        if result.error != 0 or self._provider is None:
            raise RuntimeError(f"GattServiceProvider.create_async 失败: error={result.error}")

        self._tokens.append(
            self._provider.add_advertisement_status_changed(self._on_adv_status)
        )

        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = GattCharacteristicProperties.WRITE
        params.read_protection_level = GattProtectionLevel.PLAIN
        params.write_protection_level = GattProtectionLevel.PLAIN
        # 禁止设置 static_value：WinRT 对带静态值的本地特征按只读处理，会静默丢弃
        # WRITE(8) 位（实测 props 回读 0），使中央侧在 FFF0 内找不到可写特征。

        char_result = await self._provider.service.create_characteristic_async(
            UUID(WRITE_CHAR_UUID), params
        )
        self._char = char_result.characteristic
        self._rec.log("characteristic_created",
                      error=_safe(char_result.error),
                      properties=int(self._char.characteristic_properties),
                      uuid=_safe(self._char.uuid))
        if char_result.error != 0 or self._char is None:
            raise RuntimeError(f"create_characteristic_async 失败: error={char_result.error}")

        self._tokens.append(self._char.add_write_requested(self._responder.on_write))
        self._rec.log("write_handler_registered", tokens=len(self._tokens))

        if self._setup_only:
            self._rec.log("setup_only_no_advertising")
            return

        adv = GattServiceProviderAdvertisingParameters()
        adv.is_discoverable = True
        adv.is_connectable = True
        self._provider.start_advertising_with_parameters(adv)
        self._rec.log("advertising_started", advertisement_status=self._adv_status(),
                      properties_after_advertising=self._properties())

    def _on_adv_status(self, sender: Any, args: Any) -> None:
        self._rec.log("advertisement_status_changed", status=_safe(getattr(args, "status", None)),
                      error=_safe(getattr(args, "error", None)))

    def _adv_status(self) -> str:
        try:
            return _safe(self._provider.advertisement_status)
        except Exception as exc:  # noqa: BLE001
            return f"<error: {type(exc).__name__}: {exc}>"

    def _properties(self) -> str:
        """回读特征属性（本机该 getter 会丢弃 WRITE 位，故逐次记录以便对比）。"""
        try:
            return str(int(self._char.characteristic_properties))
        except Exception as exc:  # noqa: BLE001
            return f"<error: {type(exc).__name__}: {exc}>"

    async def teardown(self) -> None:
        if self._provider is not None and not self._setup_only:
            try:
                self._provider.stop_advertising()
                # 广播状态变更是异步的：留出时间再回读，避免把停止前的读数当停止后状态。
                await asyncio.sleep(3.0)
                self._rec.log("advertising_stopped", advertisement_status=self._adv_status(),
                              properties_after_stop=self._properties())
            except Exception as exc:  # noqa: BLE001
                self._rec.log("advertising_stop_error", error=f"{type(exc).__name__}: {exc}")


def run(args: argparse.Namespace, rec: Recorder) -> int:
    if args.strategy == "immediate":
        hold = 0.0
    elif args.strategy == "delayed":
        hold = args.delay
    else:
        hold = args.window
    if args.hold_after_write is not None:
        hold = args.hold_after_write

    responder = Responder(rec, args.strategy, hold)
    responder.start()
    periph = B1MPeripheral(rec, args.name, responder, args.setup_only)

    rec.log("config", strategy=args.strategy, hold_s=hold, delay_s=args.delay,
            window_s=args.window, total_limit_s=args.total_limit, setup_only=args.setup_only,
            service_uuid=SERVICE_UUID, char_uuid=WRITE_CHAR_UUID, adapter_name=args.name)

    try:
        responder._loop.submit(periph.setup()).result(timeout=30)
    except Exception as exc:  # noqa: BLE001
        rec.log("setup_error", error=f"{type(exc).__name__}: {exc}")
        responder.stop()
        rec.log("run_end", writes_seen=0, exit_code=2)
        return 2

    writes_seen = 0
    exit_code = 0
    if args.setup_only:
        writes_seen = 0
    else:
        limit = time.monotonic() + args.total_limit
        hold_until: Optional[float] = None
        try:
            while time.monotonic() < limit:
                # 心跳：证明 PC 侧进程与时钟仍在推进（排除采集器自身卡死）。
                rec.log("heartbeat", pending=responder.pending_count())
                n = responder.seq()
                if n != writes_seen:
                    writes_seen = n
                    hold_until = time.monotonic() + hold + 5.0
                if hold_until is not None:
                    if time.monotonic() >= hold_until and responder.pending_count() == 0:
                        break
                    if time.monotonic() >= hold_until + 10.0:
                        rec.log("hold_timeout_force_exit")
                        exit_code = 4
                        break
                time.sleep(2.0)
            else:
                rec.log("total_limit_reached", limit_s=args.total_limit)
                exit_code = 5
        finally:
            responder.release_all(reason="run_end")
            for _ in range(20):
                if responder.pending_count() == 0:
                    break
                time.sleep(0.25)
            try:
                responder._loop.submit(periph.teardown()).result(timeout=15)
            except Exception as exc:  # noqa: BLE001
                rec.log("teardown_error", error=f"{type(exc).__name__}: {exc}")
                exit_code = 3
            responder.stop()
    rec.log("run_end", writes_seen=writes_seen, exit_code=exit_code)
    return exit_code


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="P3-3 B1-M 仿真外设（WinRT GATT server 直连）")
    ap.add_argument("--strategy", required=True, choices=["immediate", "delayed", "withhold"])
    ap.add_argument("--delay", type=float, default=3.0, help="延迟应答秒数（delayed 策略）")
    ap.add_argument("--window", type=float, default=20.0, help="不应答观察窗秒数（withhold 策略）")
    ap.add_argument("--total-limit", type=float, default=180.0, help="单次运行总时限（秒）")
    ap.add_argument("--name", default="B1M-ETrack", help="本验证不重命名适配器；仅记录用途")
    ap.add_argument("--run-dir", required=True, help="项目内运行目录")
    ap.add_argument("--hold-after-write", type=float, default=None,
                    help="覆盖默认持有窗口（默认 immediate=0 / delayed=N / withhold=H）")
    ap.add_argument("--setup-only", action="store_true",
                    help="只建服务与特征、注册处理器，不广播（本机 API 冒烟）")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    repo_root = Path(__file__).resolve().parents[4]
    if repo_root not in run_dir.parents:
        print(f"拒绝：运行目录必须在项目根内 {repo_root}", file=sys.stderr)
        return 2

    rec = Recorder(run_dir)
    try:
        return run(args, rec)
    except KeyboardInterrupt:
        rec.log("interrupted")
        return 130
    finally:
        rec.close()


if __name__ == "__main__":
    raise SystemExit(main())
