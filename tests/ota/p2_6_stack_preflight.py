#!/usr/bin/env python3
"""Aggregate P2-6 ELF/map/.su closure gaps without running product tests.

This module intentionally imports the parser implementation but never loads the
unittest class.  It is a static gate for the next controlled implementation
round: every independently discoverable linkage, ownership, .su, indirect-call,
cycle, and configuration problem is emitted in one deterministic report.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
closure = importlib.import_module("test_p2_6_stack_closure")


class Preflight:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.issues: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.analyses: dict[str, Any] = {}

    def issue(self, phase: str, build: str, message: str,
              detail: Any = None) -> None:
        item: dict[str, Any] = {
            "phase": phase,
            "build": build,
            "message": message,
        }
        if detail is not None:
            item["detail"] = detail
        self.issues.append(item)

    def note(self, phase: str, build: str, message: str,
             detail: Any = None) -> None:
        item: dict[str, Any] = {
            "phase": phase,
            "build": build,
            "message": message,
        }
        if detail is not None:
            item["detail"] = detail
        self.notes.append(item)

    def load(self, label: str, build: Path) -> Any | None:
        required = (
            build / "app-gcc" / "X-Track-App-GCC.elf",
            build / "app-gcc" / "X-Track-App-GCC.map",
            build / "compile_commands.json",
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            self.issue("artifacts", label, "missing required build artifacts", missing)
            return None
        try:
            analysis = closure.ElfAnalysis(build)
        except Exception as exc:  # aggregate; do not stop at first failure
            self.issue("parse", label, str(exc), {"exception": type(exc).__name__})
            return None
        self.analyses[label] = analysis
        self.note("parse", label, "ELF/map/.su parser initialized", {
            "functions": len(analysis.nodes),
            "su_entries": len(analysis.su_entries),
            "indirect_sites": sum(
                len(sites) for sites in analysis.indirect_sites.values()
            ),
        })
        return analysis

    @staticmethod
    def candidates(analysis: Any, key: str,
                   suffix: str = "") -> list[dict[str, Any]]:
        result = []
        for node in analysis._nodes_for_key(key):
            item = analysis.map_range(node)
            object_name = item.object_name if item else ""
            if suffix and not analysis._object_matches(object_name, suffix):
                continue
            result.append({
                "address": f"0x{node.address:08X}",
                "function": node.name,
                "object": object_name,
                "source_hint": analysis.source_hint(node),
            })
        return sorted(result, key=lambda item: (item["address"], item["object"]))

    def require_symbols(self, label: str, analysis: Any) -> None:
        required = (
            ("p2_6_measure_begin", "HAL_OTA_Package.cpp.obj"),
            ("p2_6_measure_end", "HAL_OTA_Package.cpp.obj"),
            ("P2_6_StartupStackScanProbe", "HAL_OTA_Package.cpp.obj"),
        ) if label == "test" else (
            ("ota_package_apply_full", "ota_package.c.obj"),
            ("ota_patch_apply", "ota_patch.c.obj"),
        )
        for key, suffix in required:
            try:
                node = analysis.find(key, suffix)
            except Exception as exc:
                self.issue("symbol", label, f"required symbol unresolved: {key}", {
                    "error": str(exc),
                    "candidates": self.candidates(analysis, key, suffix),
                })
                continue
            self.note("symbol", label, f"required symbol resolved: {key}", {
                "address": f"0x{node.address:08X}",
                "object": (analysis.map_range(node).object_name
                           if analysis.map_range(node) else ""),
            })

        if label == "test":
            raw = self.tool_text("arm-none-eabi-nm", ["-a", str(analysis.elf)])
            if raw is not None and "P2_6_StartupStackScanProbe" not in raw:
                self.issue(
                    "linkage",
                    label,
                    "test ELF does not retain P2_6_StartupStackScanProbe",
                    {"elf": str(analysis.elf)},
                )

    def ownership(self, label: str, analysis: Any) -> None:
        for name, keys in (
            ("lzma", ("LzmaDec_Allocate", "LzmaDec_FreeProbs")),
            ("usb_msc_class", ("class_init_handler", "class_clear_handler")),
        ):
            try:
                selected = analysis.resolve_common_object(name, keys)
            except Exception as exc:
                self.issue("ownership", label, f"{name} object ownership unresolved", {
                    "error": str(exc),
                    "candidates": {
                        key: self.candidates(analysis, key) for key in keys
                    },
                })
            else:
                self.note("ownership", label, f"{name} object ownership resolved",
                          {"selected": selected})

    @staticmethod
    def cycle_components(graph: dict[Any, list[Any]], nodes: set[Any]) -> list[list[Any]]:
        index = 0
        stack: list[Any] = []
        on_stack: set[Any] = set()
        indices: dict[Any, int] = {}
        low: dict[Any, int] = {}
        components: list[list[Any]] = []

        def visit(node: Any) -> None:
            nonlocal index
            indices[node] = index
            low[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for edge in graph.get(node, []):
                target = edge.target
                if target not in nodes:
                    continue
                if target not in indices:
                    visit(target)
                    low[node] = min(low[node], low[target])
                elif target in on_stack:
                    low[node] = min(low[node], indices[target])
            if low[node] != indices[node]:
                return
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1 or any(
                    edge.target == node for edge in graph.get(node, [])):
                components.append(sorted(component))

        for node in sorted(nodes):
            if node not in indices:
                visit(node)
        return components

    def analyze_scope(
        self,
        label: str,
        analysis: Any,
        scope: str,
        graph: dict[Any, list[Any]],
        root: Any,
        resolved: set[Any],
    ) -> None:
        nodes = closure.reachable(graph, root)
        unresolved = []
        frame_errors = []
        for node in sorted(nodes):
            sites = analysis.indirect_sites[node]
            if sites and node not in resolved:
                unresolved.append({
                    "function": node.name,
                    "address": f"0x{node.address:08X}",
                    "sites": [site.text for site in sites],
                })
            try:
                analysis.frame(node)
            except Exception as exc:
                frame_errors.append({
                    "address": f"0x{node.address:08X}",
                    "function": node.name,
                    "object": (analysis.map_range(node).object_name
                               if analysis.map_range(node) else ""),
                    "error": str(exc),
                })

        if unresolved:
            self.issue("indirect_calls", label,
                       f"{scope}: {len(unresolved)} reachable indirect-call sites unresolved",
                       unresolved)
        if frame_errors:
            self.issue("su_mapping", label,
                       f"{scope}: {len(frame_errors)} reachable functions lack a frame mapping",
                       frame_errors)

        components = self.cycle_components(graph, nodes)
        if components:
            formatted = []
            for component in sorted(components, key=lambda items: items[0].address):
                members = []
                member_set = set(component)
                for node in component:
                    edges = [{
                        "target": edge.target.name,
                        "origin": edge.origin,
                    } for edge in graph.get(node, []) if edge.target in member_set]
                    members.append({
                        "address": f"0x{node.address:08X}",
                        "function": node.name,
                        "edges": edges,
                    })
                formatted.append(members)
            self.issue("cycles", label,
                       f"{scope}: {len(components)} reachable call-graph cycles discovered",
                       formatted)
        else:
            self.note("scope", label, f"{scope} is statically closed", {
                "root": root.name,
                "root_address": f"0x{root.address:08X}",
                "reachable_functions": len(nodes),
                "unresolved_indirect_calls": len(unresolved),
                "frame_errors": len(frame_errors),
            })

    def production_scopes(self, analysis: Any) -> None:
        for kind in ("full", "patch"):
            try:
                graph, resolved, core_root = closure.core_graph(analysis, kind)
            except Exception as exc:
                self.issue("scope_setup", "prod", f"{kind} core graph setup failed", str(exc))
                continue
            try:
                graph, root = closure.prefix_graph(
                    analysis, kind, graph, core_root, resolved
                )
            except Exception as exc:
                self.issue("scope_setup", "prod", f"{kind} prefix graph setup failed", str(exc))
                root = core_root
            self.analyze_scope("prod", analysis, f"ota_{kind}", graph, root, resolved)

        try:
            memory = closure.parse_jlink_memory(closure.NVIC_LOG)
            vectors = analysis.vector_words()
            graph = closure.copy_direct_graph(analysis)
            resolved = closure.interrupt_resolvers(analysis, graph)
        except Exception as exc:
            self.issue("scope_setup", "prod", "interrupt graph setup failed", str(exc))
            return

        active: list[tuple[int, int, Any]] = []
        for irq in range(160):
            try:
                iser = closure.word(memory, 0xE000E100 + (irq // 32) * 4)
            except Exception as exc:
                self.issue("runtime_inputs", "prod", "NVIC enable state incomplete", str(exc))
                return
            if not (iser & (1 << (irq % 32))):
                continue
            vector_index = 16 + irq
            if vector_index >= len(vectors):
                self.issue("runtime_inputs", "prod", f"enabled IRQ{irq} exceeds vector table")
                continue
            handler = analysis.owner(vectors[vector_index] & ~1)
            if handler is None or handler.name == "Default_Handler":
                self.issue("runtime_inputs", "prod", f"enabled IRQ{irq} has no handler")
                continue
            priority = memory.get(0xE000E400 + irq, 0) >> 4
            active.append((irq, priority, handler))
        try:
            systick_ctrl = closure.word(memory, 0xE000E010)
            if systick_ctrl & 0x3 == 0x3:
                active.append((
                    -1,
                    memory.get(0xE000ED23, 0) >> 4,
                    analysis.find("SysTick_Handler", "Platform/Core/delay.c.obj"),
                ))
        except Exception as exc:
            self.issue("runtime_inputs", "prod", "SysTick state unresolved", str(exc))

        for irq, priority, handler in active:
            name = "systick" if irq == -1 else f"irq{irq}_priority{priority}"
            self.analyze_scope("prod", analysis, name, graph, handler, resolved)

    def measurement_scopes(self, analysis: Any) -> None:
        graph, resolved = closure.measurement_graph(analysis)
        for key in (
            "p2_6_measure_begin",
            "p2_6_measure_end",
            "P2_6_StartupStackScanProbe",
        ):
            try:
                root = analysis.find(key, "HAL_OTA_Package.cpp.obj")
            except Exception:
                continue
            self.analyze_scope("test", analysis, f"measurement_{key}",
                               graph, root, resolved)

    def config(self, label: str, build: Path) -> None:
        cache = build / "CMakeCache.txt"
        commands = build / "compile_commands.json"
        if not cache.exists() or not commands.exists():
            self.issue("configuration", label, "missing CMakeCache or compile_commands")
            return
        cache_text = cache.read_text(encoding="utf-8", errors="replace")
        command_text = commands.read_text(encoding="utf-8", errors="replace")
        expected_test = "P2_6_TEST_ENABLE:BOOL=ON" if label == "test" else "P2_6_TEST_ENABLE:BOOL=OFF"
        if expected_test not in cache_text:
            self.issue("configuration", label, "P2_6_TEST_ENABLE cache mismatch",
                       expected_test)
        if "-fstack-usage" not in command_text:
            self.issue("configuration", label, "-fstack-usage missing from compile commands")
        if "-Oz" not in command_text:
            self.issue("configuration", label, "-Oz missing from compile commands")
        if "-flto" in command_text:
            self.issue("configuration", label, "LTO appears in compile commands")
        if label == "test" and "-DP2_6_TEST_ENABLE=1" not in command_text:
            self.issue("configuration", label, "test compile commands lack P2_6_TEST_ENABLE")
        if label == "prod" and "-DP2_6_TEST_ENABLE=1" in command_text:
            self.issue("configuration", label, "production compile commands contain test macro")
        cmake_text = (
            ROOT / "MDK-ARM_F435/cmake-generated/CMakeLists.txt"
        ).read_text(encoding="utf-8", errors="replace")
        if "--undefined=P2_6_StartupStackScanProbe" not in cmake_text:
            self.issue("configuration", label,
                       "test-only startup probe retention option is absent")

    def tool_text(self, tool: str, args: list[str]) -> str | None:
        executable = shutil.which(tool)
        if not executable:
            self.issue("environment", "global", f"required tool unavailable: {tool}")
            return None
        env = os.environ.copy()
        tmp = ROOT / ".cache" / "p2-6a-test-tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        env.update({
            "TEMP": str(tmp), "TMP": str(tmp), "TMPDIR": str(tmp),
            "PYTHONPYCACHEPREFIX": str(ROOT / ".cache" / "p2-6a-pycache"),
        })
        try:
            result = subprocess.run([executable, *args], cwd=ROOT, env=env,
                                    check=True, capture_output=True, text=True,
                                    errors="replace")
        except (OSError, subprocess.CalledProcessError) as exc:
            self.issue("environment", "global", f"tool invocation failed: {tool}", str(exc))
            return None
        return result.stdout + result.stderr

    def run(self, builds: dict[str, Path]) -> int:
        for label, build in builds.items():
            analysis = self.load(label, build)
            self.config(label, build)
            if analysis is None:
                continue
            self.require_symbols(label, analysis)
            self.ownership(label, analysis)
            if label == "prod":
                self.production_scopes(analysis)
            else:
                self.measurement_scopes(analysis)

        self.issues.sort(key=lambda item: (
            item.get("build", ""), item.get("phase", ""), item.get("message", "")
        ))
        self.notes.sort(key=lambda item: (
            item.get("build", ""), item.get("phase", ""), item.get("message", "")
        ))
        report = {
            "schema": "p2-6-stack-preflight-v1",
            "formal_test_executed": False,
            "production_build": str(builds["prod"]),
            "test_build": str(builds["test"]),
            "issue_count": len(self.issues),
            "issues": self.issues,
            "notes": self.notes,
        }
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "P2_6_STACK_PREFLIGHT": "FAIL" if self.issues else "PASS",
            "issues": len(self.issues),
            "notes": len(self.notes),
            "report": str(self.output / "report.json"),
            "formal_test_executed": False,
        }, ensure_ascii=False))
        return 1 if self.issues else 0


def under_root(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"path outside project root: {resolved}") from exc
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod-build", type=Path,
                        default=closure.PROD_BUILD)
    parser.add_argument("--test-build", type=Path,
                        default=closure.TEST_BUILD)
    parser.add_argument("--output", type=Path,
                        default=ROOT / ".cache" / "p2-6a-stack-preflight")
    args = parser.parse_args(argv)
    builds = {
        "prod": under_root(args.prod_build),
        "test": under_root(args.test_build),
    }
    output = under_root(args.output)
    return Preflight(output).run(builds)


if __name__ == "__main__":
    raise SystemExit(main())
