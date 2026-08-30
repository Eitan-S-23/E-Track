#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真实 GCC 产物闭合 P2-6 线程态、测量链和中断栈上界。"""

from __future__ import annotations

from dataclasses import dataclass
import bisect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache" / "p2-6-stack-closure"
TMP = ROOT / ".cache" / "p2-6-test-tmp"
STACK_LIMIT = 8192
HARDWARE_FRAME = 32 + 72 + 4

OBJDUMP = shutil.which("arm-none-eabi-objdump")


def select_build(env_name: str, candidates: tuple[str, ...]) -> Path:
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured).resolve()
    for candidate in candidates:
        path = ROOT / ".cache" / candidate
        if path.exists():
            return path
    return ROOT / ".cache" / candidates[0]


PROD_BUILD = select_build(
    "P2_6_PROD_STACK_BUILD",
    ("p2-6-cmake-prod-stack-final", "p2-6-cmake-prod-stack-r2"),
)
TEST_BUILD = select_build(
    "P2_6_TEST_STACK_BUILD",
    ("p2-6-cmake-test-stack-final", "p2-6-cmake-test-stack-r2"),
)
NVIC_LOG = Path(os.environ.get(
    "P2_6_NVIC_LOG",
    ROOT / ".cache" / "p2-6-jlink-gdb" / "nvic-runtime-production.log",
)).resolve()
STARTUP_LOG = Path(os.environ.get(
    "P2_6_STARTUP_SCAN_LOG",
    ROOT / ".cache" / "p2-6-gdb" / "startup-stack-scan-summary.log",
)).resolve()


def command_env() -> dict[str, str]:
    result = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        result[key] = str(TMP)
    result["PYTHONPYCACHEPREFIX"] = str(ROOT / ".cache" / "p2-6-pycache")
    return result


def run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=command_env(),
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
    return completed.stdout + completed.stderr


def normalized_path(value: str) -> str:
    return value.replace("\\", "/").replace("//", "/").lower()


class AnalysisError(RuntimeError):
    pass


class CallGraphCycleError(AnalysisError):
    def __init__(self, cycle: list[Node]) -> None:
        self.cycle = cycle
        super().__init__(
            "调用图存在环: " + " -> ".join(item.name for item in cycle)
        )


@dataclass(frozen=True)
class FunctionIdentity:
    raw: str
    normalized: str
    key: str
    parameters: str
    clone_families: tuple[str, ...]
    clone_instances: tuple[str, ...]


def _clone_family(value: str) -> str:
    match = re.fullmatch(r"\.(isra|constprop|part)(?:\.\d+)?", value)
    if not match:
        raise AnalysisError(f"不支持的 GCC clone 标识: {value!r}")
    return match.group(1)


def _top_level_boundary(value: str, end: int) -> int:
    angle = 0
    paren = 0
    square = 0
    brace = 0
    boundary = 0
    for index, character in enumerate(value[:end]):
        if character == "<":
            angle += 1
        elif character == ">" and angle:
            angle -= 1
        elif character == "(":
            paren += 1
        elif character == ")" and paren:
            paren -= 1
        elif character == "[":
            square += 1
        elif character == "]" and square:
            square -= 1
        elif character == "{":
            brace += 1
        elif character == "}" and brace:
            brace -= 1
        elif (character.isspace() and not any(
                (angle, paren, square, brace))):
            boundary = index + 1
    return boundary


def function_identity(name: str) -> FunctionIdentity:
    raw = name
    value = re.sub(r"\s+", " ", name.strip())
    if not value:
        raise AnalysisError("函数标识为空")
    value = value.replace("(anonymous namespace)::", "{anonymous}::")

    bracket_clones: list[str] = []
    while True:
        match = re.search(r"\s*\[clone\s+([^]]+)\]\s*$", value)
        if not match:
            break
        clone = match.group(1).strip()
        _clone_family(clone)
        bracket_clones.append(clone)
        value = value[:match.start()].rstrip()
    bracket_clones.reverse()

    value = re.sub(r"\s+\[with\s+.*\]\s*$", "", value).rstrip()
    stack: list[int] = []
    pairs: list[tuple[int, int]] = []
    for index, character in enumerate(value):
        if character == "(":
            stack.append(index)
        elif character == ")":
            if not stack:
                raise AnalysisError(f"函数标识括号不平衡: {raw!r}")
            start = stack.pop()
            if not stack:
                pairs.append((start, index))
    if stack:
        raise AnalysisError(f"函数标识括号不平衡: {raw!r}")

    parameters = ""
    if pairs:
        start, end = pairs[-1]
        tail = value[end + 1:].strip()
        if tail and not re.fullmatch(
                r"(?:(?:const|volatile|noexcept|[&]{1,2})\s*)+", tail):
            raise AnalysisError(f"函数标识尾部无法解释: {raw!r}")
        prefix = value[:start].strip()
        parameters = value[start:end + 1]
    else:
        prefix = value

    operators = list(re.finditer(
        r"(?<![A-Za-z0-9_])operator(?=$|[^A-Za-z0-9_])", prefix
    ))
    token_start = _top_level_boundary(
        prefix, operators[-1].start() if operators else len(prefix)
    )
    callable_name = re.sub(r"\s+", " ", prefix[token_start:].strip())
    if not callable_name or not re.search(r"[A-Za-z_~]", callable_name):
        raise AnalysisError(f"函数标识没有可提取 callable: {raw!r}")

    direct_clones: list[str] = []
    while True:
        match = re.search(
            r"\.(isra|constprop|part)(?:\.\d+)?$", callable_name
        )
        if not match:
            break
        clone = match.group(0)
        direct_clones.insert(0, clone)
        callable_name = callable_name[:match.start()].rstrip()
    if not callable_name or callable_name in (")", "cpp)"):
        raise AnalysisError(f"函数标识没有可提取 callable: {raw!r}")

    # GCC and .su spell the same lambda differently. Collapse only the
    # compiler-generated lambda scope; object/source uniqueness remains the
    # fail-closed discriminator when resolving the entry.
    callable_name = re.sub(
        r"(?:\{lambda(?:\([^{}]*\))?(?:#\d+)?\}|"
        r"<lambda(?:\([^<>]*\))?>)",
        "{lambda}",
        callable_name,
    )
    if (_top_level_boundary(callable_name, len(callable_name)) and
            "operator" not in callable_name):
        raise AnalysisError(f"函数 callable 含未解释空格: {raw!r}")

    clones = tuple(direct_clones + bracket_clones)
    return FunctionIdentity(
        raw=raw,
        normalized=value,
        key=callable_name,
        parameters=parameters,
        clone_families=tuple(_clone_family(item) for item in clones),
        clone_instances=clones,
    )


def function_key(name: str) -> str:
    return function_identity(name).key


@dataclass(frozen=True, order=True)
class Node:
    address: int
    name: str

    @property
    def key(self) -> str:
        return function_key(self.name)


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    operands: str
    text: str


@dataclass(frozen=True)
class Edge:
    target: Node
    tail: bool
    origin: str


@dataclass(frozen=True)
class SuEntry:
    su_file: str
    object_name: str
    compilation_source: str
    source: str
    line: int
    function: str
    size: int
    qualifier: str
    identity: FunctionIdentity | None
    identity_error: str

    @property
    def key(self) -> str:
        if self.identity is None:
            raise AnalysisError(self.identity_error)
        return self.identity.key


@dataclass(frozen=True)
class MapRange:
    start: int
    size: int
    section: str
    object_name: str

    def contains(self, address: int) -> bool:
        return self.start <= address < self.start + self.size


class ElfAnalysis:
    def __init__(self, build: Path) -> None:
        self.build = build
        self.elf = build / "app-gcc" / "X-Track-App-GCC.elf"
        self.map_file = build / "app-gcc" / "X-Track-App-GCC.map"
        self.commands_file = build / "compile_commands.json"
        for path in (self.elf, self.map_file, self.commands_file):
            if not path.exists():
                raise AnalysisError(f"缺少构建证据: {path}")

        self.disassembly = run([OBJDUMP, "-d", "-C", str(self.elf)])
        self.sections = run([OBJDUMP, "-h", str(self.elf)])
        self.vector_dump = run([
            OBJDUMP, "-s", "-j", ".isr_vector", str(self.elf),
        ])
        self.map_text = self.map_file.read_text(encoding="utf-8", errors="replace")
        self.nodes, self.instructions = self._parse_disassembly()
        self.starts = sorted(self.nodes)
        self.map_ranges = self._parse_map_ranges()
        self.compile_sources = self._parse_compile_sources()
        self.su_entries = self._parse_su_entries()
        self.invalid_su_identities = [
            {
                "su_file": entry.su_file,
                "object": entry.object_name,
                "compilation_source": entry.compilation_source,
                "source": entry.source,
                "line": entry.line,
                "function": entry.function,
                "reason": entry.identity_error,
            }
            for entry in self.su_entries if entry.identity is None
        ]
        self.direct_edges, self.indirect_sites = self._parse_edges()
        self._frame_cache: dict[Node, tuple[int, str]] = {}
        self.clone_mappings: dict[int, dict[str, object]] = {}
        self.object_resolutions: dict[str, dict[str, object]] = {}

    def _parse_disassembly(self) -> tuple[dict[int, Node], dict[Node, list[Instruction]]]:
        nodes: dict[int, Node] = {}
        instructions: dict[Node, list[Instruction]] = {}
        current: Node | None = None
        for line in self.disassembly.splitlines():
            header = re.match(r"^([0-9a-fA-F]+) <(.+)>:$", line)
            if header:
                current = Node(int(header.group(1), 16), header.group(2))
                nodes[current.address] = current
                instructions[current] = []
                continue
            if current is None or "\t" not in line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            address_match = re.match(r"\s*([0-9a-fA-F]+):", parts[0])
            if not address_match:
                continue
            mnemonic = parts[-2].strip()
            operands = parts[-1].strip()
            if not mnemonic or not re.match(r"^[a-z][a-z0-9.]*$", mnemonic):
                continue
            instructions[current].append(Instruction(
                int(address_match.group(1), 16), mnemonic, operands, line.strip()
            ))
        if not nodes:
            raise AnalysisError("objdump 未解析到任何函数")
        return nodes, instructions

    def _parse_map_ranges(self) -> list[MapRange]:
        ranges: list[MapRange] = []
        pending_section = ""
        for line in self.map_text.splitlines():
            section_only = re.match(r"^\s+(\.[^\s]+)\s*$", line)
            if section_only:
                pending_section = section_only.group(1)
                continue
            full = re.match(
                r"^\s+(\.[^\s]+)\s+0x([0-9a-fA-F]+)\s+"
                r"0x([0-9a-fA-F]+)\s+(\S+)", line,
            )
            if full:
                section = full.group(1)
                start = int(full.group(2), 16)
                size = int(full.group(3), 16)
                object_name = full.group(4)
            else:
                continuation = re.match(
                    r"^\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(\S+)",
                    line,
                )
                if not continuation:
                    continue
                section = pending_section
                start = int(continuation.group(1), 16)
                size = int(continuation.group(2), 16)
                object_name = continuation.group(3)
            if size and (".obj" in object_name or ".a(" in object_name):
                ranges.append(MapRange(start, size, section, object_name))
        if not ranges:
            raise AnalysisError("map 未解析到输入段范围")
        return ranges

    def _parse_compile_sources(self) -> dict[str, str]:
        try:
            commands = json.loads(self.commands_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AnalysisError(f"compile_commands.json 无法解析: {exc}") from exc
        result: dict[str, str] = {}
        build = self.build.resolve()
        for command in commands:
            output = command.get("output")
            source = command.get("file")
            if not output or not source:
                continue
            output_path = Path(output).resolve()
            try:
                relative = output_path.relative_to(build).as_posix()
            except ValueError:
                continue
            object_name = normalized_path(relative)
            source_name = normalized_path(str(Path(source).resolve()))
            previous = result.get(object_name)
            if previous is not None and previous != source_name:
                raise AnalysisError(
                    f"编译对象映射到多个源文件: {object_name}: "
                    f"{previous!r}, {source_name!r}"
                )
            result[object_name] = source_name
        if not result:
            raise AnalysisError("compile_commands.json 没有输出对象映射")
        return result

    def _parse_su_entries(self) -> list[SuEntry]:
        entries: list[SuEntry] = []
        for path in self.build.rglob("*.su"):
            relative = path.resolve().relative_to(self.build.resolve()).as_posix()
            object_name = normalized_path(relative[:-3] + ".obj")
            compilation_source = self.compile_sources.get(object_name, "")
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split("\t")
                if len(fields) != 3:
                    continue
                location = re.match(r"^(.*):(\d+):(\d+):(.*)$", fields[0])
                if not location:
                    continue
                function = location.group(4).strip()
                try:
                    identity = function_identity(function)
                    identity_error = ""
                except AnalysisError as exc:
                    identity = None
                    identity_error = str(exc)
                entries.append(SuEntry(
                    normalized_path(relative),
                    object_name,
                    compilation_source,
                    normalized_path(location.group(1)),
                    int(location.group(2)),
                    function,
                    int(fields[1]),
                    fields[2].strip(),
                    identity,
                    identity_error,
                ))
        if not entries:
            raise AnalysisError(f"构建目录没有 .su 数据: {self.build}")
        return entries

    def owner(self, address: int) -> Node | None:
        index = bisect.bisect_right(self.starts, address) - 1
        return self.nodes[self.starts[index]] if index >= 0 else None

    def _parse_edges(self) -> tuple[dict[Node, list[Edge]], dict[Node, list[Instruction]]]:
        direct: dict[Node, list[Edge]] = {node: [] for node in self.nodes.values()}
        indirect: dict[Node, list[Instruction]] = {node: [] for node in self.nodes.values()}
        for node, instructions in self.instructions.items():
            for instruction in instructions:
                target_match = re.match(r"^([0-9a-fA-F]+)\s+<", instruction.operands)
                if instruction.mnemonic in ("bl", "bl.w", "blx"):
                    if target_match:
                        target = self.owner(int(target_match.group(1), 16) & ~1)
                        if target is None:
                            raise AnalysisError(f"直接调用目标无法归属: {instruction.text}")
                        direct[node].append(Edge(target, False, instruction.text))
                    elif instruction.mnemonic == "blx":
                        indirect[node].append(instruction)
                elif instruction.mnemonic in ("b", "b.n", "b.w"):
                    if target_match:
                        target = self.owner(int(target_match.group(1), 16) & ~1)
                        if target is not None and target != node:
                            direct[node].append(Edge(target, True, instruction.text))
                    elif instruction.operands not in ("lr", "pc"):
                        indirect[node].append(instruction)
                elif (instruction.mnemonic == "bx" and
                      instruction.operands not in ("lr", "pc")):
                    indirect[node].append(instruction)
        return direct, indirect

    def map_range(self, node: Node) -> MapRange | None:
        matches = [item for item in self.map_ranges if item.contains(node.address)]
        return min(matches, key=lambda item: item.size) if matches else None

    def source_hint(self, node: Node) -> str:
        item = self.map_range(node)
        if item is None:
            return ""
        value = normalized_path(item.object_name)
        marker = "/e-track/"
        if marker in value:
            value = value.split(marker, 1)[1]
        elif "x_track_app_gcc.dir/" in value:
            value = value.split("x_track_app_gcc.dir/", 1)[1]
        value = re.sub(r"\.obj$", "", value)
        return value

    def _object_matches(self, object_name: str, hint: str) -> bool:
        normalized = normalized_path(object_name)
        suffix = normalized_path(hint)
        return (not suffix or normalized == suffix or
                normalized.endswith("/" + suffix))

    def _nodes_for_key(self, key: str) -> list[Node]:
        matches = []
        for node in self.nodes.values():
            try:
                identity = function_identity(node.name)
            except AnalysisError:
                continue
            if identity.key == key:
                matches.append(node)
        return matches

    def find(self, key: str, object_suffix: str = "") -> Node:
        matches = []
        for node in self._nodes_for_key(key):
            item = self.map_range(node)
            object_name = item.object_name if item else ""
            if not self._object_matches(object_name, object_suffix):
                continue
            matches.append(node)
        if len(matches) != 1:
            detail = []
            for node in matches:
                item = self.map_range(node)
                detail.append({
                    "address": hex(node.address),
                    "function": node.name,
                    "object": item.object_name if item else "",
                    "source_hint": self.source_hint(node),
                })
            raise AnalysisError(
                f"函数选择不唯一 key={key!r} object={object_suffix!r}: {detail}"
            )
        return matches[0]

    def resolve_common_object(
        self,
        label: str,
        function_keys: tuple[str, ...],
    ) -> str:
        cached = self.object_resolutions.get(label)
        if cached is not None:
            return str(cached["selected"])
        candidates: dict[str, list[str]] = {}
        normalized_sets: list[set[str]] = []
        originals: dict[str, str] = {}
        for key in function_keys:
            objects = []
            for node in self._nodes_for_key(key):
                item = self.map_range(node)
                if item is None:
                    continue
                normalized = normalized_path(item.object_name)
                originals.setdefault(normalized, item.object_name)
                objects.append(normalized)
            unique = sorted(set(objects))
            candidates[key] = [originals[item] for item in unique]
            normalized_sets.append(set(unique))
        common = set.intersection(*normalized_sets) if normalized_sets else set()
        if len(common) != 1:
            raise AnalysisError(
                f"{label} 对象归属无法唯一解析: candidates={candidates}, "
                f"common={sorted(common)}"
            )
        selected_normalized = next(iter(common))
        selected = originals[selected_normalized]
        compilation_source = self.compile_sources.get(selected_normalized, "")
        if not compilation_source:
            raise AnalysisError(
                f"{label} 对象没有 compile_commands 源绑定: {selected}"
            )
        self.object_resolutions[label] = {
            "functions": list(function_keys),
            "candidates": candidates,
            "selected": selected,
            "compilation_source": compilation_source,
        }
        return selected

    def _prologue_frame(self, node: Node) -> int:
        total = 0
        for instruction in self.instructions[node]:
            text = instruction.operands
            if instruction.mnemonic in ("push", "stmdb") and "sp!" in text or \
                    instruction.mnemonic == "push":
                registers = re.search(r"\{([^}]+)\}", text)
                if registers:
                    total += 4 * len([part for part in registers.group(1).split(",")
                                     if part.strip()])
            elif instruction.mnemonic == "vpush":
                registers = re.search(r"\{d(\d+)-d(\d+)\}", text)
                if registers:
                    total += 8 * (int(registers.group(2)) -
                                  int(registers.group(1)) + 1)
                else:
                    raise AnalysisError(f"无法解析 vpush: {instruction.text}")
            elif instruction.mnemonic.startswith("sub") and text.startswith("sp"):
                immediate = re.search(r"#(\d+)", text)
                if not immediate:
                    raise AnalysisError(f"动态 SP 调整无法闭合: {instruction.text}")
                total += int(immediate.group(1))
        return total

    def frame(self, node: Node) -> tuple[int, str]:
        cached = self._frame_cache.get(node)
        if cached is not None:
            return cached
        identity = function_identity(node.name)
        item = self.map_range(node)
        object_name = normalized_path(item.object_name) if item else ""
        object_entries = [entry for entry in self.su_entries
                          if entry.object_name == object_name]
        candidates = [entry for entry in object_entries
                      if entry.identity is not None and
                      entry.identity.key == identity.key]
        selected: list[SuEntry] = []
        if identity.clone_families:
            exact = [entry for entry in candidates
                     if entry.identity is not None and
                     entry.identity.clone_families == identity.clone_families]
            if len(exact) == 1:
                selected = exact
            elif len(exact) > 1:
                raise AnalysisError(
                    f"clone .su 精确映射不唯一: {node.name}: "
                    f"{self._su_details(exact)}"
                )
            else:
                base = [entry for entry in candidates
                        if entry.identity is not None and
                        not entry.identity.clone_families]
                if len(base) != 1:
                    raise AnalysisError(
                        f"clone .su 基函数映射不是唯一项: {node.name}: "
                        f"exact={self._su_details(exact)} "
                        f"base={self._su_details(base)}"
                    )
                selected = base
            entry = selected[0]
            expected_source = self.compile_sources.get(object_name, "")
            if (not expected_source or
                    entry.compilation_source != expected_source or
                    entry.object_name != object_name):
                raise AnalysisError(
                    f"clone .su 跨源或跨对象: {node.name}: "
                    f"map_object={item.object_name if item else ''!r} "
                    f"expected_source={expected_source!r} "
                    f"entry={self._su_details(selected)}"
                )
            self.clone_mappings[node.address] = {
                "elf_address": f"0x{node.address:08X}",
                "elf_function": node.name,
                "elf_key": identity.key,
                "elf_clone_families": list(identity.clone_families),
                "elf_clone_instances": list(identity.clone_instances),
                "map_object": item.object_name if item else "",
                "compilation_source": entry.compilation_source,
                "su_file": entry.su_file,
                "su_object": entry.object_name,
                "su_source": entry.source,
                "su_line": entry.line,
                "su_function": entry.function,
                "su_clone_families": list(
                    entry.identity.clone_families if entry.identity else ()
                ),
                "bytes": entry.size,
            }
        else:
            selected = [entry for entry in candidates
                        if entry.identity is not None and
                        not entry.identity.clone_families]

        if selected:
            if any(entry.qualifier != "static" for entry in selected):
                raise AnalysisError(
                    f"动态栈条目: {node.name}: " +
                    ", ".join(entry.qualifier for entry in selected)
                )
            size = max(entry.size for entry in selected)
            source = ".su:" + ",".join(sorted({
                entry.source for entry in selected
            }))
        else:
            if object_name in self.compile_sources or (
                    item and "x_track_app_gcc.dir" in object_name):
                invalid = [entry for entry in object_entries
                           if entry.identity is None]
                raise AnalysisError(
                    f"项目函数缺少唯一 .su 条目: {node.name} "
                    f"object={item.object_name if item else ''} "
                    f"candidates={self._su_details(candidates)} "
                    f"invalid_in_object={self._su_details(invalid)}"
                )
            size = self._prologue_frame(node)
            source = "objdump-prologue"
        self._frame_cache[node] = (size, source)
        return size, source

    @staticmethod
    def _su_details(entries: list[SuEntry]) -> list[dict[str, object]]:
        return [{
            "su_file": entry.su_file,
            "object": entry.object_name,
            "compilation_source": entry.compilation_source,
            "source": entry.source,
            "line": entry.line,
            "function": entry.function,
            "clone_families": list(
                entry.identity.clone_families if entry.identity else ()
            ),
            "size": entry.size,
            "identity_error": entry.identity_error,
        } for entry in entries]

    def vector_words(self) -> list[int]:
        raw = bytearray()
        for line in self.vector_dump.splitlines():
            match = re.match(r"^\s*[0-9a-fA-F]+\s+(.+)$", line)
            if not match:
                continue
            for group in match.group(1).split():
                if re.fullmatch(r"[0-9a-fA-F]{8}", group):
                    raw.extend(bytes.fromhex(group))
                else:
                    break
        return [int.from_bytes(raw[index:index + 4], "little")
                for index in range(0, len(raw) - 3, 4)]


def add_resolver(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
    resolved: set[Node],
    node: Node,
    targets: list[Node],
    expected_sites: int,
) -> None:
    sites = analysis.indirect_sites[node]
    if len(sites) != expected_sites:
        raise AnalysisError(
            f"{node.name} 间接调用点数量漂移: {len(sites)} != {expected_sites}"
        )
    resolved.add(node)
    for site in sites:
        tail = site.mnemonic == "bx"
        for target in targets:
            graph[node].append(Edge(target, tail, site.text + " [resolved]"))


def reachable(graph: dict[Node, list[Edge]], root: Node) -> set[Node]:
    seen: set[Node] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(edge.target for edge in graph.get(node, []))
    return seen


def assert_closed(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
    root: Node,
    resolved: set[Node],
) -> set[Node]:
    nodes = reachable(graph, root)
    unknown = []
    for node in sorted(nodes):
        if analysis.indirect_sites[node] and node not in resolved:
            unknown.append(
                f"{node.name}: " +
                " | ".join(site.text for site in analysis.indirect_sites[node])
            )
        analysis.frame(node)
    if unknown:
        raise AnalysisError("存在未定界间接调用:\n" + "\n".join(unknown))

    visiting: list[Node] = []
    visited: set[Node] = set()

    def visit(node: Node) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycle = visiting[start:] + [node]
            raise CallGraphCycleError(cycle)
        if node in visited:
            return
        visiting.append(node)
        for edge in graph.get(node, []):
            if edge.target in nodes:
                visit(edge.target)
        visiting.pop()
        visited.add(node)

    visit(root)
    return nodes


def maximum_path(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
    root: Node,
) -> tuple[int, list[tuple[Node, int, str]]]:
    memo: dict[Node, tuple[int, list[tuple[Node, int, str]]]] = {}

    def solve(node: Node) -> tuple[int, list[tuple[Node, int, str]]]:
        if node in memo:
            return memo[node]
        frame, _ = analysis.frame(node)
        best = frame
        best_path = [(node, frame, "entry")]
        for edge in graph.get(node, []):
            child_total, child_path = solve(edge.target)
            total = max(frame, child_total) if edge.tail else frame + child_total
            if total > best:
                best = total
                kind = "tail" if edge.tail else "call"
                best_path = [(node, frame, kind)] + child_path
        memo[node] = (best, best_path)
        return memo[node]

    return solve(root)


def unique_sample_call_path(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
    resolved: set[Node],
    wrapper: Node,
    scanner: Node,
) -> tuple[
        int,
        list[tuple[Node, int, str]],
        dict[str, object],
]:
    call_order: list[dict[str, object]] = []
    sample_sites: list[tuple[int, int, Instruction]] = []
    for instruction_index, instruction in enumerate(
            analysis.instructions[wrapper]):
        if instruction.mnemonic not in ("bl", "bl.w", "blx"):
            continue
        target_match = re.match(
            r"^([0-9a-fA-F]+)\s+<", instruction.operands
        )
        if target_match is None:
            continue
        target = analysis.owner(int(target_match.group(1), 16) & ~1)
        if target is None:
            raise AnalysisError(
                f"采样包装函数直接调用目标无法归属: {instruction.text}"
            )
        call_order_index = len(call_order)
        call_order.append({
            "instruction_index": instruction_index,
            "address": f"0x{instruction.address:08X}",
            "instruction": instruction.text,
            "target_address": f"0x{target.address:08X}",
            "target": target.name,
        })
        if target == scanner:
            sample_sites.append(
                (instruction_index, call_order_index, instruction)
            )

    if len(sample_sites) != 1:
        raise AnalysisError(
            f"{wrapper.name} 的 StackInfo 采样调用点不唯一: "
            f"count={len(sample_sites)} calls={call_order}"
        )

    instruction_index, call_order_index, instruction = sample_sites[0]
    assert_closed(analysis, graph, scanner, resolved)
    scanner_total, scanner_path = maximum_path(analysis, graph, scanner)
    wrapper_frame, _ = analysis.frame(wrapper)
    total = wrapper_frame + scanner_total
    path = [
        (wrapper, wrapper_frame, f"call@0x{instruction.address:08X}"),
        *scanner_path,
    ]
    return total, path, {
        "instruction_index": instruction_index,
        "call_order_index": call_order_index,
        "address": f"0x{instruction.address:08X}",
        "instruction": instruction.text,
        "direct_call_order": call_order,
    }


def copy_direct_graph(analysis: ElfAnalysis) -> dict[Node, list[Edge]]:
    return {node: list(edges) for node, edges in analysis.direct_edges.items()}


def measurement_graph(
    analysis: ElfAnalysis,
) -> tuple[dict[Node, list[Edge]], set[Node]]:
    graph = copy_direct_graph(analysis)
    resolved: set[Node] = set()
    tlsf_object = "lv_tlsf.c.obj"
    memory_object = "lv_mem.c.obj"
    walk = analysis.find("lv_tlsf_walk_pool", tlsf_object)
    walker = analysis.find("lv_mem_walker", memory_object)
    block_next = analysis.find("block_next", tlsf_object)
    assert_func = analysis.find("__assert_func")

    add_resolver(analysis, graph, resolved, walk, [walker], 1)

    # lv_tlsf_walk_pool calls block_next only under the same !block_is_last
    # predicate asserted inside block_next.  The selected lv_mem_walker callback
    # only updates the monitor object, so it cannot invalidate that predicate.
    source = (ROOT / "Simulator/LVGL.Simulator/lvgl/src/misc/lv_tlsf.c").read_text(
        encoding="utf-8", errors="replace"
    )
    walk_invariant = re.search(
        r"while\s*\(\s*block\s*&&\s*!block_is_last\(block\)\s*\)\s*\{"
        r".*?block\s*=\s*block_next\(block\)\s*;\s*\}",
        source,
        re.S,
    )
    if not walk_invariant or "tlsf_assert(!block_is_last(block));" not in source:
        raise AnalysisError("TLSF monitor traversal invariant drifted")
    if analysis.direct_edges[walker] or analysis.indirect_sites[walker]:
        raise AnalysisError("lv_mem_walker callback is no longer a leaf")

    assert_edges = [edge for edge in graph[block_next]
                    if edge.target == assert_func]
    if len(assert_edges) != 1:
        raise AnalysisError(
            f"block_next assert edge count drifted: {len(assert_edges)} != 1"
        )
    graph[block_next] = [edge for edge in graph[block_next]
                         if edge.target != assert_func]
    return graph, resolved


def core_graph(analysis: ElfAnalysis, kind: str) -> tuple[
        dict[Node, list[Edge]], set[Node], Node]:
    graph = copy_direct_graph(analysis)
    resolved: set[Node] = set()
    hal_object = "USER/HAL/HAL_OTA_Package.cpp.obj"
    package_object = "Libraries/OTA/ota_package.c.obj"
    patch_object = "Libraries/OTA/ota_patch.c.obj"
    lzma_object = analysis.resolve_common_object(
        "lzma",
        ("LzmaDec_Allocate", "LzmaDec_FreeProbs"),
    )
    header_object = "boot/src/boot_fw_header.c.obj"

    package_read = analysis.find("package_read", hal_object)
    candidate_prepare = analysis.find("candidate_prepare", hal_object)
    candidate_program = analysis.find("candidate_program", hal_object)
    candidate_read = analysis.find("candidate_read", hal_object)
    workspace_acquire = analysis.find("workspace_acquire", hal_object)
    workspace_release = analysis.find("workspace_release", hal_object)
    boot_validate = analysis.find("boot_fw_header_validate_ex", header_object)
    lzma_allocate = analysis.find("LzmaDec_Allocate", lzma_object)
    lzma_allocate_probs = analysis.find("LzmaDec_AllocateProbs2", lzma_object)
    lzma_free_probs = analysis.find("LzmaDec_FreeProbs", lzma_object)

    if kind == "full":
        root = analysis.find("ota_package_apply_full", package_object)
        stream_append = analysis.find("stream_append", package_object)
        candidate_image_read = analysis.find("candidate_image_read", package_object)
        arena_alloc = analysis.find("arena_alloc", package_object)
        arena_free = analysis.find("arena_free", package_object)
        add_resolver(analysis, graph, resolved, root, [
            package_read, candidate_prepare, candidate_program, candidate_read,
            workspace_acquire, workspace_release,
        ], 8)
    elif kind == "patch":
        root = analysis.find("ota_patch_apply", patch_object)
        stream_append = analysis.find("stream_append", patch_object)
        candidate_image_read = analysis.find("candidate_image_read", patch_object)
        write_candidate = analysis.find("write_candidate_chunk", patch_object)
        arena_alloc = analysis.find("arena_alloc", patch_object)
        arena_free = analysis.find("arena_free", patch_object)
        base_read = analysis.find("base_read", hal_object)
        add_resolver(analysis, graph, resolved, root, [
            package_read, base_read, candidate_prepare, candidate_program,
            candidate_read, workspace_acquire, workspace_release,
        ], 9)
        add_resolver(analysis, graph, resolved, write_candidate,
                     [candidate_program, candidate_read], 2)
    else:
        raise ValueError(kind)

    add_resolver(analysis, graph, resolved, stream_append, [package_read], 1)
    add_resolver(analysis, graph, resolved, candidate_image_read,
                 [candidate_read], 1)
    add_resolver(analysis, graph, resolved, boot_validate,
                 [candidate_image_read], 3)
    add_resolver(analysis, graph, resolved, lzma_allocate,
                 [arena_alloc, arena_free], 2)
    add_resolver(analysis, graph, resolved, lzma_allocate_probs,
                 [arena_alloc], 1)
    add_resolver(analysis, graph, resolved, lzma_free_probs,
                 [arena_free], 1)
    return graph, resolved, root


def prefix_graph(
    analysis: ElfAnalysis,
    kind: str,
    core: dict[Node, list[Edge]],
    core_root: Node,
    resolved: set[Node] | None = None,
) -> tuple[dict[Node, list[Edge]], Node]:
    graph = {node: list(edges) for node, edges in core.items()}
    main = analysis.find("main", "USER/main.cpp.obj")
    timer = analysis.find("lv_timer_handler", "lv_timer.c.obj")
    on_timer = analysis.find("Page::FirmwareUpdate::onWorkTimer",
                             "FirmwareUpdate.cpp.obj")
    work = analysis.find("Page::FirmwareUpdate::RunWorkStep",
                         "FirmwareUpdate.cpp.obj")
    apply = analysis.find("OtaUpdate::Session::Apply", "OtaUpdate.cpp.obj")
    if kind == "full":
        hal_apply = analysis.find("HAL::OTA_PackageApplyStaging",
                                  "HAL_OTA_Package.cpp.obj")
    else:
        hal_apply = analysis.find("HAL::OTA_PatchApplyStaging",
                                  "HAL_OTA_Package.cpp.obj")

    forced = (
        (main, timer, False),
        (timer, on_timer, False),
        (on_timer, work, True),
        (work, apply, False),
        (apply, hal_apply, False),
        (hal_apply, core_root, False),
    )
    for source, target, tail in forced:
        if source == timer:
            if len(analysis.indirect_sites[source]) != 1:
                raise AnalysisError("lv_timer_handler 间接回调点数量漂移")
            registration = (ROOT / "USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp").read_text(
                encoding="utf-8", errors="replace"
            )
            if "lv_timer_create(onWorkTimer, 12, this)" not in registration:
                raise AnalysisError("OTA workTimer 未注册到 onWorkTimer")
            if resolved is not None:
                resolved.add(source)
        else:
            matches = [edge for edge in analysis.direct_edges[source]
                       if edge.target == target and edge.tail == tail]
            if not matches:
                raise AnalysisError(
                    f"冻结外层边不存在或调用类型漂移: {source.name} -> {target.name}"
                )
        graph[source] = [Edge(target, tail, "frozen OTA prefix")]
    return graph, main


def parse_jlink_memory(path: Path) -> dict[int, int]:
    if not path.exists():
        raise AnalysisError(f"缺少运行态 NVIC 日志: {path}")
    memory: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"^(?:J-Link>)?([0-9A-Fa-f]{8})\s*=\s*"
            r"((?:[0-9A-Fa-f]{8}(?:\s+|$))+)", line.strip(),
        )
        if not match:
            continue
        address = int(match.group(1), 16)
        for offset, word in enumerate(match.group(2).split()):
            value = int(word, 16)
            for byte_index in range(4):
                memory[address + offset * 4 + byte_index] = (
                    value >> (byte_index * 8)
                ) & 0xFF
    return memory


def word(memory: dict[int, int], address: int) -> int:
    try:
        return sum(memory[address + index] << (index * 8) for index in range(4))
    except KeyError as exc:
        raise AnalysisError(f"运行态日志缺少地址 0x{address:08X}") from exc


def interrupt_resolvers(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
) -> set[Node]:
    resolved: set[Node] = set()
    timer_object = "Platform/Core/timer.c.obj"
    serial_object = "Platform/Core/HardwareSerial.cpp.obj"
    display_object = "Platform/HAL/HAL_Display.cpp.obj"
    button_object = "Libraries/ButtonEvent/ButtonEvent.cpp.obj"
    encoder_object = "USER/HAL/HAL_Encoder.cpp.obj"
    tone_player_object = "USER/App/Utils/TonePlayer/TonePlayer.cpp.obj"
    audio_object = "USER/HAL/HAL_Audio.cpp.obj"
    usb_core_object = "usb_drivers/src/usbd_core.c.obj"
    usb_int_object = "usb_drivers/src/usbd_int.c.obj"
    usb_sdr_object = "usb_drivers/src/usbd_sdr.c.obj"
    msc_object = analysis.resolve_common_object(
        "usb_msc_class",
        ("class_init_handler", "class_clear_handler"),
    )
    disk_object = "Libraries/USB_MSC/msc_diskio.cpp.obj"
    sdio_object = "Libraries/SdFat/src/SdCard/SdioCard_AT32.cpp.obj"

    tone = analysis.find("Tone_TimerHandler", "Platform/Core/Tone.cpp.obj")
    hal_timer = analysis.find("HAL_TimerInterrputUpdate", "USER/HAL/HAL.cpp.obj")
    display_done = analysis.find("disp_send_finish_callback",
                                 "Platform/lv_port/lv_port_disp.cpp.obj")
    add_resolver(analysis, graph, resolved,
                 analysis.find("TMR1_OVF_TMR10_IRQHandler", timer_object),
                 [tone], 2)
    add_resolver(analysis, graph, resolved,
                 analysis.find("TMR4_GLOBAL_IRQHandler", timer_object),
                 [hal_timer], 1)
    add_resolver(analysis, graph, resolved,
                 analysis.find("DMA1_Channel3_IRQHandler", display_object),
                 [display_done], 1)
    add_resolver(analysis, graph, resolved,
                 analysis.find("HardwareSerial::IRQHandler", serial_object),
                 [], 1)

    button_targets = [analysis.find(name, encoder_object) for name in (
        "Encoder_PushHandler", "Encoder_AHandler", "Encoder_BHandler",
    )]
    add_resolver(
        analysis,
        graph,
        resolved,
        analysis.find("ButtonEvent::EventMonitor", button_object),
        button_targets,
        10,
    )
    add_resolver(
        analysis,
        graph,
        resolved,
        analysis.find("TonePlayer::Update", tone_player_object),
        [analysis.find("HAL::Audio_Init()::{lambda}::_FUN", audio_object)],
        2,
    )

    class_target_names = (
        "class_init_handler", "class_clear_handler", "class_setup_handler",
        "class_ept0_tx_handler", "class_ept0_rx_handler", "class_in_handler",
        "class_out_handler", "class_sof_handler", "class_event_handler",
    )
    class_by_name = {
        name: analysis.find(name, msc_object) for name in class_target_names
    }
    class_targets = list(class_by_name.values())
    for name, object_name, count in (
        ("usbd_core_in_handler", usb_core_object, 2),
        ("usbd_core_out_handler", usb_core_object, 2),
        ("usbd_device_request", usb_sdr_object, 5),
        ("usbd_interface_request", usb_sdr_object, 1),
        ("usbd_endpoint_request", usb_sdr_object, 2),
    ):
        add_resolver(analysis, graph, resolved,
                     analysis.find(name, object_name), class_targets, count)

    for name, target_name in (
        ("usbd_enumdone_handler", "class_clear_handler"),
        ("usbd_incomisoout_handler", "class_event_handler"),
        ("usbd_incomisioin_handler", "class_event_handler"),
        ("usbd_reset_handler", "class_event_handler"),
        ("usbd_sof_handler", "class_sof_handler"),
        ("usbd_suspend_handler", "class_event_handler"),
        ("usbd_wakeup_handler", "class_event_handler"),
    ):
        add_resolver(
            analysis,
            graph,
            resolved,
            analysis.find(name, usb_int_object),
            [class_by_name[target_name]],
            1,
        )

    sdio_read = analysis.find("SdioCardEX::readBlocks", sdio_object)
    sdio_write = analysis.find("SdioCardEX::writeBlocks", sdio_object)
    sdio_sync = analysis.find("SdioCardEX::syncBlocks", sdio_object)
    add_resolver(analysis, graph, resolved,
                 analysis.find("msc_disk_read", disk_object), [sdio_read], 1)
    add_resolver(analysis, graph, resolved,
                 analysis.find("msc_disk_write", disk_object), [sdio_write], 1)
    add_resolver(analysis, graph, resolved, sdio_write, [sdio_sync], 1)
    return resolved


def format_path(path: list[tuple[Node, int, str]]) -> list[dict[str, object]]:
    return [{
        "address": f"0x{node.address:08X}",
        "function": node.name,
        "frame": frame,
        "edge": edge,
    } for node, frame, edge in path]


def format_su_audited_path(
    analysis: ElfAnalysis,
    path: list[tuple[Node, int, str]],
) -> list[dict[str, object]]:
    result = []
    for node, frame, edge in path:
        actual_frame, frame_source = analysis.frame(node)
        if actual_frame != frame:
            raise AnalysisError(
                f"路径帧与 .su 解析结果不一致: {node.name}: "
                f"path={frame} actual={actual_frame}"
            )
        item = analysis.map_range(node)
        if item is None:
            raise AnalysisError(f"采样路径函数缺少 map 对象归属: {node.name}")
        object_name = normalized_path(item.object_name)
        compilation_source = analysis.compile_sources.get(object_name, "")
        if not compilation_source:
            raise AnalysisError(
                f"采样路径函数缺少编译源归属: {node.name}: "
                f"object={item.object_name}"
            )
        if not frame_source.startswith(".su:"):
            raise AnalysisError(
                f"采样路径函数未使用 .su 帧: {node.name}: {frame_source}"
            )
        su_sources = frame_source.removeprefix(".su:").split(",")
        if (len(su_sources) != 1 or
                normalized_path(su_sources[0]) != compilation_source):
            raise AnalysisError(
                f"采样路径 .su 源与编译源不唯一或不一致: {node.name}: "
                f"su={su_sources} compilation={compilation_source!r}"
            )
        result.append({
            "address": f"0x{node.address:08X}",
            "function": node.name,
            "frame": frame,
            "edge": edge,
            "frame_source": frame_source,
            "map_object": item.object_name,
            "compilation_source": compilation_source,
        })
    return result


def format_cycle(
    analysis: ElfAnalysis,
    graph: dict[Node, list[Edge]],
    cycle: list[Node],
) -> list[dict[str, object]]:
    result = []
    for index, node in enumerate(cycle):
        frame, frame_source = analysis.frame(node)
        item = analysis.map_range(node)
        next_node = cycle[index + 1] if index + 1 < len(cycle) else None
        origins = [] if next_node is None else [
            edge.origin for edge in graph.get(node, [])
            if edge.target == next_node
        ]
        result.append({
            "sequence": index,
            "address": f"0x{node.address:08X}",
            "function": node.name,
            "frame": frame,
            "frame_source": frame_source,
            "object": item.object_name if item else "",
            "source_hint": analysis.source_hint(node),
            "edge_to_next": origins,
        })
    return result


class P2SixStackClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not OBJDUMP:
            raise unittest.SkipTest("arm-none-eabi-objdump 不可用")
        OUT.mkdir(parents=True, exist_ok=True)
        TMP.mkdir(parents=True, exist_ok=True)
        cls.prod = ElfAnalysis(PROD_BUILD)
        cls.test = ElfAnalysis(TEST_BUILD)
        cls.report: dict[str, object] = {
            "production_build": str(PROD_BUILD),
            "test_build": str(TEST_BUILD),
            "nvic_log": str(NVIC_LOG),
            "startup_log": str(STARTUP_LOG),
        }

        cls.core_results: dict[str, tuple[int, list[tuple[Node, int, str]]]] = {}
        cls.core_nodes: dict[str, int] = {}
        for kind in ("full", "patch"):
            graph, resolved, root = core_graph(cls.prod, kind)
            nodes = assert_closed(cls.prod, graph, root, resolved)
            prefixed, thread_root = prefix_graph(
                cls.prod, kind, graph, root, resolved
            )
            total, path = maximum_path(cls.prod, prefixed, thread_root)
            cls.core_results[kind] = (total, path)
            cls.core_nodes[kind] = len(nodes)
            cls.report[kind] = {
                "thread_peak": total,
                "reachable_functions": len(nodes),
                "path": format_path(path),
            }

        memory = parse_jlink_memory(NVIC_LOG)
        aircr = word(memory, 0xE000ED0C)
        ccr = word(memory, 0xE000ED14)
        fpccr = word(memory, 0xE000EF34)
        systick_ctrl = word(memory, 0xE000E010)
        vtor = word(memory, 0xE000ED08)
        cls.runtime_registers = {
            "VTOR": vtor,
            "AIRCR": aircr,
            "CCR": ccr,
            "FPCCR": fpccr,
            "SysTick_CTRL": systick_ctrl,
        }

        vectors = cls.prod.vector_words()
        isr_graph = copy_direct_graph(cls.prod)
        isr_resolved = interrupt_resolvers(cls.prod, isr_graph)
        active: list[tuple[int, int, Node]] = []
        for irq in range(160):
            iser_word = word(memory, 0xE000E100 + (irq // 32) * 4)
            if not (iser_word & (1 << (irq % 32))):
                continue
            vector_index = 16 + irq
            if vector_index >= len(vectors):
                raise AnalysisError(f"启用 IRQ{irq} 超出向量表")
            handler = cls.prod.owner(vectors[vector_index] & ~1)
            if handler is None or handler.name == "Default_Handler":
                raise AnalysisError(f"启用 IRQ{irq} 没有生产 handler")
            priority = memory[0xE000E400 + irq] >> 4
            active.append((irq, priority, handler))
        if systick_ctrl & 0x3 == 0x3:
            systick = cls.prod.find("SysTick_Handler", "Platform/Core/delay.c.obj")
            active.append((-1, memory[0xE000ED23] >> 4, systick))

        by_priority: dict[int, list[dict[str, object]]] = {}
        cls.interrupt_evidence_gaps: list[dict[str, object]] = []
        for irq, priority, handler in active:
            try:
                nodes = assert_closed(
                    cls.prod, isr_graph, handler, isr_resolved
                )
                software, path = maximum_path(cls.prod, isr_graph, handler)
            except CallGraphCycleError as exc:
                cls.interrupt_evidence_gaps.append({
                    "classification": "EVIDENCE_GAP",
                    "reason": "unbounded_call_graph_cycle",
                    "irq": irq,
                    "priority": priority,
                    "handler": handler.name,
                    "handler_address": f"0x{handler.address:08X}",
                    "cycle": format_cycle(cls.prod, isr_graph, exc.cycle),
                })
                continue
            by_priority.setdefault(priority, []).append({
                "irq": irq,
                "handler": handler.name,
                "reachable_functions": len(nodes),
                "software": software,
                "path": format_path(path),
            })
        cls.interrupt_choices = []
        bounded_interrupt_budget = 0
        gap_priorities = {
            int(item["priority"]) for item in cls.interrupt_evidence_gaps
        }
        for priority in sorted(by_priority, reverse=True):
            if priority in gap_priorities:
                continue
            choice = max(by_priority[priority], key=lambda item: int(item["software"]))
            layer = HARDWARE_FRAME + int(choice["software"])
            bounded_interrupt_budget += layer
            cls.interrupt_choices.append({
                "priority": priority,
                "hardware": HARDWARE_FRAME,
                "software": choice["software"],
                "layer": layer,
                "handler": choice["handler"],
                "irq": choice["irq"],
                "path": choice["path"],
                "candidates": by_priority[priority],
            })
        cls.interrupt_budget = (
            None if cls.interrupt_evidence_gaps else bounded_interrupt_budget
        )
        cls.report["runtime_registers"] = {
            key: f"0x{value:08X}" for key, value in cls.runtime_registers.items()
        }
        cls.report["active_interrupts"] = [
            {"irq": irq, "priority": priority, "handler": handler.name}
            for irq, priority, handler in active
        ]
        cls.report["bounded_interrupt_candidates"] = {
            str(priority): candidates
            for priority, candidates in sorted(by_priority.items())
        }
        cls.report["interrupt_evidence_gaps"] = cls.interrupt_evidence_gaps
        cls.report["interrupt_layers"] = cls.interrupt_choices
        cls.report["interrupt_budget"] = cls.interrupt_budget
        cls.report["bounded_interrupt_budget"] = bounded_interrupt_budget

        measure_graph, measure_resolved = measurement_graph(cls.test)
        begin = cls.test.find("p2_6_measure_begin", "HAL_OTA_Package.cpp.obj")
        end = cls.test.find("p2_6_measure_end", "HAL_OTA_Package.cpp.obj")
        helper = cls.test.find("P2_6_StartupStackScanProbe",
                               "HAL_OTA_Package.cpp.obj")
        assert_closed(cls.test, measure_graph, begin, measure_resolved)
        assert_closed(cls.test, measure_graph, end, measure_resolved)
        assert_closed(cls.test, measure_graph, helper, measure_resolved)
        scanner = cls.test.find(
            "StackInfo_GetMaxUsageSize", "StackInfo/StackInfo.c.obj"
        )
        begin_scan_total, begin_scan_path, begin_call = unique_sample_call_path(
            cls.test, measure_graph, measure_resolved, begin, scanner
        )
        end_scan_total, end_scan_path, end_call = unique_sample_call_path(
            cls.test, measure_graph, measure_resolved, end, scanner
        )
        begin_wrapper_total, begin_wrapper_path = maximum_path(
            cls.test, measure_graph, begin
        )
        end_wrapper_total, end_wrapper_path = maximum_path(
            cls.test, measure_graph, end
        )
        helper_total, helper_path = maximum_path(cls.test, measure_graph, helper)
        cls.stack_scan_results = {
            "begin": (begin_scan_total, begin_scan_path),
            "end": (end_scan_total, end_scan_path),
        }
        cls.measurement_wrapper_results = {
            "begin": (begin_wrapper_total, begin_wrapper_path),
            "end": (end_wrapper_total, end_wrapper_path),
        }
        cls.stack_scan_overhead = max(
            begin_scan_total, end_scan_total
        )
        cls.measurement_wrapper_upper_bound = max(
            begin_wrapper_total, end_wrapper_total
        )
        cls.helper_total = helper_total
        cls.report["stack_scan_overhead"] = {
            "bytes": cls.stack_scan_overhead,
            "begin": {
                "bytes": begin_scan_total,
                "sample_call": begin_call,
                "path": format_su_audited_path(cls.test, begin_scan_path),
            },
            "end": {
                "bytes": end_scan_total,
                "sample_call": end_call,
                "path": format_su_audited_path(cls.test, end_scan_path),
            },
        }
        cls.report["measurement_wrapper_upper_bound"] = {
            "bytes": cls.measurement_wrapper_upper_bound,
            "begin": {
                "bytes": begin_wrapper_total,
                "path": format_path(begin_wrapper_path),
            },
            "end": {
                "bytes": end_wrapper_total,
                "path": format_path(end_wrapper_path),
            },
        }
        cls.report["startup_helper"] = {
            "bytes": helper_total,
            "path": format_path(helper_path),
        }

        if not STARTUP_LOG.exists():
            raise AnalysisError(f"缺少 startup 立即扫描证据: {STARTUP_LOG}")
        startup_text = STARTUP_LOG.read_text(encoding="utf-8", errors="replace")
        startup = re.search(
            r"P2_6_STARTUP_SCAN observed=(\d+) guard=(\d+) "
            r"helper_static=(\d+) stack_total=(\d+)", startup_text,
        )
        if not startup:
            raise AnalysisError("startup 立即扫描摘要格式无效")
        cls.startup_observed = int(startup.group(1))
        cls.startup_guard = int(startup.group(2))
        cls.startup_helper_reported = int(startup.group(3))
        cls.startup_total = int(startup.group(4))
        cls.report["startup_scan"] = {
            "observed": cls.startup_observed,
            "guard": cls.startup_guard,
            "helper_static": cls.startup_helper_reported,
            "stack_total": cls.startup_total,
        }

        thread_peak = max(total for total, _ in cls.core_results.values())
        if cls.interrupt_evidence_gaps:
            cls.combined = None
            cls.margin = None
        else:
            cls.combined = thread_peak + int(cls.interrupt_budget)
            cls.margin = STACK_LIMIT - cls.combined
        cls.report["combined"] = {
            "classification": (
                "EVIDENCE_GAP" if cls.interrupt_evidence_gaps else "PASS"
            ),
            "thread_peak": thread_peak,
            "interrupt_budget": cls.interrupt_budget,
            "total": cls.combined,
            "limit": STACK_LIMIT,
            "margin": cls.margin,
        }
        cls.report["classification"] = {
            "C3": (
                "EVIDENCE_GAP" if cls.interrupt_evidence_gaps else "PASS"
            ),
            "C13": (
                "EVIDENCE_GAP" if cls.interrupt_evidence_gaps else "PASS"
            ),
            "C16": (
                "EVIDENCE_GAP" if cls.interrupt_evidence_gaps else "PASS"
            ),
        }
        cls.report["object_resolution"] = {
            "production": cls.prod.object_resolutions,
            "test": cls.test.object_resolutions,
        }
        cls.report["clone_mappings"] = {
            "production": [cls.prod.clone_mappings[address]
                           for address in sorted(cls.prod.clone_mappings)],
            "test": [cls.test.clone_mappings[address]
                     for address in sorted(cls.test.clone_mappings)],
        }
        cls.report["invalid_su_identities"] = {
            "production": cls.prod.invalid_su_identities,
            "test": cls.test.invalid_su_identities,
        }
        (OUT / "stack-closure.json").write_text(
            json.dumps(cls.report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_su_is_static_and_real_release_uses_oz(self) -> None:
        for label, analysis in (("production", self.prod), ("test", self.test)):
            dynamic = [entry for entry in analysis.su_entries
                       if entry.qualifier != "static"]
            self.assertFalse(dynamic, f"{label} 出现动态栈条目: {dynamic[:5]}")
            commands = analysis.commands_file.read_text(encoding="utf-8")
            self.assertIn("-fstack-usage", commands)
            self.assertIn("-Oz", commands)
            self.assertNotIn("-flto", commands)

    def test_full_and_patch_graphs_are_closed(self) -> None:
        self.assertGreaterEqual(self.core_nodes["full"], 70)
        self.assertGreaterEqual(self.core_nodes["patch"], 80)
        self.assertGreater(self.core_results["full"][0], 0)
        self.assertGreater(self.core_results["patch"][0], 0)

    def test_runtime_nvic_group_and_exception_frame_inputs(self) -> None:
        self.assertEqual((self.runtime_registers["AIRCR"] >> 8) & 0x7, 3)
        self.assertNotEqual(self.runtime_registers["CCR"] & (1 << 9), 0)
        self.assertNotEqual(self.runtime_registers["FPCCR"] & (1 << 30), 0)
        self.assertNotEqual(self.runtime_registers["FPCCR"] & (1 << 31), 0)
        self.assertEqual(self.runtime_registers["VTOR"], 0x08010000)
        self.assertEqual(HARDWARE_FRAME, 108)

    def test_interrupt_graph_and_preemption_chain_are_closed(self) -> None:
        self.assertFalse(
            self.interrupt_evidence_gaps,
            "中断调用图存在静态闭环证据缺口: " +
            json.dumps(self.interrupt_evidence_gaps, ensure_ascii=False),
        )
        priorities = [int(item["priority"]) for item in self.interrupt_choices]
        self.assertEqual(priorities, sorted(set(priorities), reverse=True))
        self.assertEqual(priorities, [1, 0])
        self.assertGreater(int(self.interrupt_budget), HARDWARE_FRAME * 2)

    def test_measurement_call_overhead_is_quantified(self) -> None:
        self.assertEqual(
            self.stack_scan_overhead,
            max(total for total, _ in self.stack_scan_results.values()),
        )
        self.assertEqual(
            self.measurement_wrapper_upper_bound,
            max(total for total, _ in self.measurement_wrapper_results.values()),
        )
        for label in ("begin", "end"):
            scan_total, scan_path = self.stack_scan_results[label]
            wrapper_total, wrapper_path = self.measurement_wrapper_results[label]
            self.assertGreater(scan_total, 0)
            self.assertLess(scan_total, 256)
            self.assertLessEqual(scan_total, wrapper_total)
            self.assertTrue(scan_path)
            self.assertTrue(wrapper_path)

    def test_startup_immediate_scan_matches_helper_scale(self) -> None:
        self.assertEqual(self.startup_guard, 1)
        self.assertEqual(self.startup_total, STACK_LIMIT)
        self.assertEqual(self.startup_helper_reported, self.helper_total)
        self.assertGreaterEqual(self.startup_observed, self.helper_total)
        self.assertLessEqual(self.startup_observed, self.helper_total + 64)
        self.assertNotIn(self.startup_observed, (0, STACK_LIMIT))

    def test_combined_static_upper_bound_fits_contract(self) -> None:
        self.assertFalse(
            self.interrupt_evidence_gaps,
            "无法形成有效最坏中断预算，C3/C13/C16=EVIDENCE_GAP: " +
            json.dumps(self.interrupt_evidence_gaps, ensure_ascii=False),
        )
        self.assertLessEqual(int(self.combined), STACK_LIMIT)
        self.assertGreaterEqual(int(self.margin), 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        P2SixStackClosureTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
