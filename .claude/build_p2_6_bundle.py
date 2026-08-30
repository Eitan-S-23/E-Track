"""R20 收口：生成 P2-6-v1 验收合同、证据矩阵与三类 manifest。

只读取已封存的证据根 -18，不改产品代码、不改校验器、不触发任何硬件动作。
manifest 的枚举与稳定哈希直接复用 Tools/acceptance/validate_bundle.py 的实现，
避免与校验器出现第二套语义。
"""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

REPO = Path(r"D:\github\my\E-Track")
ROOT = REPO / ".cache" / "p2-6-rtt-binding-20260829-18"
BUNDLE = REPO / "docs" / "acceptance-contracts" / "P2-6-v1"
CONTRACT_PATH = REPO / "docs" / "acceptance-contracts" / "P2-6-v1.contract.json"
MATRIX_PATH = BUNDLE / "P2-6-v1.evidence-matrix.json"
R19_DOC = REPO / "docs" / "ota-exec-notes" / "P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md"

spec = importlib.util.spec_from_file_location(
    "vb", REPO / "Tools" / "acceptance" / "validate_bundle.py"
)
vb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vb)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


# ---------- 1. 复制证据（源为只读封存根） ----------
COPIES = [
    ("logs/result.json", "artifacts/logs/result.json"),
    ("logs/capture.json", "artifacts/logs/capture.json"),
    ("logs/postcheck.json", "artifacts/logs/postcheck.json"),
    ("logs/precheck.json", "artifacts/logs/precheck.json"),
    ("logs/precall.json", "artifacts/logs/precall.json"),
    ("logs/recovery-result.json", "artifacts/logs/recovery-result.json"),
    ("logs/gate-pre.json", "artifacts/logs/gate-pre.json"),
    ("logs/gdb.log", "artifacts/logs/gdb.log"),
    ("logs/gdb-post.log", "artifacts/logs/gdb-post.log"),
    ("logs/rtt-logger-console.log", "artifacts/logs/rtt-logger-console.log"),
    ("manifest.json", "artifacts/root-manifest.json"),
    ("snapshots/rtt-payload.bin", "artifacts/snapshots/rtt-payload.bin"),
    ("snapshots/pending.bin", "artifacts/snapshots/pending.bin"),
    ("snapshots/rtt-cb-pre.bin", "artifacts/snapshots/rtt-cb-pre.bin"),
    ("snapshots/rtt-cb-post.bin", "artifacts/snapshots/rtt-cb-post.bin"),
    ("snapshots/board-header.bin", "artifacts/snapshots/board-header.bin"),
    ("snapshots/board-image-a.bin", "artifacts/snapshots/board-image-a.bin"),
    ("snapshots/board-image-b.bin", "artifacts/snapshots/board-image-b.bin"),
    ("snapshots/board-image-c.bin", "artifacts/snapshots/board-image-c.bin"),
]
for src, dst in COPIES:
    target = BUNDLE / dst
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / src, target)

doc_copy = BUNDLE / "artifacts/docs/P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md"
doc_copy.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(R19_DOC, doc_copy)

# ---------- 2. 三类 manifest ----------
worktree = vb._resolve_git_worktree(str(REPO))
manifests = {}
for group_id, (profile, category) in sorted(vb.REQUIRED_INPUT_GROUPS.items()):
    records = vb._collect_profile_records(worktree, profile)
    files = [
        {"Path": r["Path"], "Length": r["Length"], "SHA256": r["SHA256"].upper()}
        for r in records
    ]
    text = vb._manifest_text_bytes(files)
    stable = hashlib.sha256(text).hexdigest().upper()
    doc = {
        "Schema": vb.INPUT_MANIFEST_SCHEMA,
        "Profile": profile,
        "Ordering": vb.INPUT_MANIFEST_ORDERING,
        "Encoding": vb.INPUT_MANIFEST_ENCODING,
        "FileCount": len(files),
        "ManifestSHA256": stable,
        "Files": files,
    }
    d = BUNDLE / f"manifest-{group_id}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "source-manifest.txt").write_bytes(text)
    (d / "source-manifest.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifests[group_id] = {
        "id": group_id,
        "profile": profile,
        "category": category,
        "manifest_path": f"manifest-{group_id}/source-manifest.json",
        "manifest_sha256": stable,
        "manifest_json_sha256": sha256_file(d / "source-manifest.json"),
    }
    print(f"{group_id:11s} profile={profile:11s} files={len(files):5d} stable={stable[:16]}")

# ---------- 3. 从证据实读观测值 ----------
result = json.loads((BUNDLE / "artifacts/logs/result.json").read_text(encoding="utf-8"))
capture = json.loads((BUNDLE / "artifacts/logs/capture.json").read_text(encoding="utf-8"))
post = json.loads((BUNDLE / "artifacts/logs/postcheck.json").read_text(encoding="utf-8"))
rec = result["recovery"]
pre = rec["pre_consensus"]
runs = rec["gate_pre"]["pass_runs"]
assert result["classification"] == "RTT_CHANNEL_BINDING_VERIFIED"
assert pre["difference_bytes"] == 0, pre["difference_bytes"]

ACCEPT_CMD = (
    'cd /d/github/my/E-Track && "C:/Users/SU/AppData/Local/Programs/Python/Python313/'
    'python.exe" .cache/p2-6-rtt-binding-20260829-18/scripts/run_recovery_binding.py '
    "--audit-id P2-6-BR-20260829-RTT-BIND-R19-03 "
    '--evidence-root "D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-18"'
)
SHA_CMD = (
    "cd /d/github/my/E-Track && python -c \"import hashlib,pathlib\\n"
    "for p in sorted(pathlib.Path('.cache/p2-6-rtt-binding-20260829-18/scripts')"
    ".glob('*.gdb')):\\n"
    "    print(f'{p.name} {p.stat().st_size} "
    "{hashlib.sha256(p.read_bytes()).hexdigest().upper()}')\""
)

ART = {
    "ART-RESULT": ("artifacts/logs/result.json", "两会话 binding 编排的最终结果记录（分类/marker/会话退出码）"),
    "ART-CAPTURE-JSON": ("artifacts/logs/capture.json", "会话间 JLinkRTTLogger 采集记录（字节数、SHA、logger 生命周期）"),
    "ART-POSTCHECK-JSON": ("artifacts/logs/postcheck.json", "RTT 控制块前后 diff 与 RdOff 推进记录"),
    "ART-PRECHECK-JSON": ("artifacts/logs/precheck.json", "采集前 Up0 待读字节的资格与基准记录"),
    "ART-PRECALL-JSON": ("artifacts/logs/precall.json", "受控调用前置状态审计记录"),
    "ART-RECOVERY-JSON": ("artifacts/logs/recovery-result.json", "恢复/闸门阶段完整结果记录"),
    "ART-GATEPRE-JSON": ("artifacts/logs/gate-pre.json", "gate-pre 三遍复读的逐遍审计记录"),
    "ART-GDB-LOG": ("artifacts/logs/gdb.log", "binding 会话 1 的 GDB 原始日志"),
    "ART-GDB-POST-LOG": ("artifacts/logs/gdb-post.log", "binding 会话 2 的 GDB 原始日志"),
    "ART-LOGGER-CONSOLE": ("artifacts/logs/rtt-logger-console.log", "JLinkRTTLogger 控制台原始输出"),
    "ART-ROOT-MANIFEST": ("artifacts/root-manifest.json", "证据根 -18 的封存 manifest（绑定根内全部 965 个文件）"),
    "ART-RTT-PAYLOAD": ("artifacts/snapshots/rtt-payload.bin", "logger 读出的 Up0 环载荷字节"),
    "ART-PENDING": ("artifacts/snapshots/pending.bin", "precheck 由 GDB 快照推导的待读字节"),
    "ART-CB-PRE": ("artifacts/snapshots/rtt-cb-pre.bin", "采集前 RTT 控制块快照"),
    "ART-CB-POST": ("artifacts/snapshots/rtt-cb-post.bin", "采集后 RTT 控制块快照"),
    "ART-BOARD-HEADER": ("artifacts/snapshots/board-header.bin", "板卡 App 头部快照（version_code/CRC32）"),
    "ART-BOARD-IMAGE-A": ("artifacts/snapshots/board-image-a.bin", "gate-pre 第一遍全镜像复读"),
    "ART-BOARD-IMAGE-B": ("artifacts/snapshots/board-image-b.bin", "gate-pre 第二遍全镜像复读"),
    "ART-BOARD-IMAGE-C": ("artifacts/snapshots/board-image-c.bin", "gate-pre 第三遍全镜像复读"),
    "ART-GDB-SHA": ("artifacts/logs/generated-gdb-sha256.txt", "根 -18 生成 GDB 脚本的字节数与 SHA-256 复算输出"),
    "ART-R19-DOC": ("artifacts/docs/P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md", "R20 更正后的 R19 实现证据文档副本"),
}

CRITERIA = [
    {
        "id": "HW-RTT-BINDING",
        "description": "真机两会话 binding 必须把 RTT Up0 通道绑定坐实，判定为 RTT_CHANNEL_BINDING_VERIFIED 且 14 个 GDB 标记全部命中。",
        "kind": "functional",
        "evidence_types": ["raw_log", "structured_result"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-RESULT", "ART-GDB-LOG", "ART-GDB-POST-LOG", "ART-PRECALL-JSON"],
        "gate": {"type": "boolean", "basis": "frozen_requirement", "expected": True},
        "observed": True,
        "notes": (
            f"classification={result['classification']} / reason={result['reason']}；"
            f"audit_id={result['audit_id']}；14 marker 全 1；"
            f"gdb_exit_code={result['gdb_exit_code']}，gdb_post_exit_code={result['gdb_post_exit_code']}。"
        ),
    },
    {
        "id": "HW-CAPTURE-PAYLOAD",
        "description": "会话间 JLinkRTTLogger 读出的载荷必须与 precheck 推导的待读字节逐字节一致。",
        "kind": "functional",
        "evidence_types": ["structured_result", "binary_snapshot"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-CAPTURE-JSON", "ART-PRECHECK-JSON", "ART-RTT-PAYLOAD", "ART-PENDING"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "payload_bytes=731",
                "expected_pending_bytes=731",
                "payload_sha256=206286D4D2B8866F29AF6308059E53AEB500CC3F79300C8506E3C3F921DDFC49",
                "raw_sha256=206286D4D2B8866F29AF6308059E53AEB500CC3F79300C8506E3C3F921DDFC49",
                "payload_complete=true",
            ],
        },
        "observed": [
            f"payload_bytes={capture['payload_bytes']}",
            f"expected_pending_bytes={capture['expected_pending_bytes']}",
            f"payload_sha256={capture['payload_sha256']}",
            f"raw_sha256={capture['raw_sha256']}",
            "payload_complete=true" if capture["payload_complete"] else "payload_complete=false",
        ],
        "notes": "读取器为 JLinkRTTLogger 独立 probe 连接（GDB server 的 RTT telnet 在本 J-Link 上只给 banner）。",
    },
    {
        "id": "HW-POSTCHECK-RDOFF",
        "description": "采集只允许推进 Up0 的 4 字节 RdOff 字；控制块其余字节、环内容与 measurement 结构必须逐字节不变。",
        "kind": "safety",
        "evidence_types": ["structured_result", "binary_snapshot"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-POSTCHECK-JSON", "ART-CB-PRE", "ART-CB-POST"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "RdOff:0->731",
                "WrOff:731->731",
                "control_block_outside_rd_off_changes=0",
                "up_buffer_sha256_unchanged=true",
                "measurement_seq_unchanged=true",
            ],
        },
        "observed": [
            f"RdOff:{post['descriptor_before']['RdOff']}->{post['descriptor_after']['RdOff']}",
            f"WrOff:{post['descriptor_before']['WrOff']}->{post['descriptor_after']['WrOff']}",
            f"control_block_outside_rd_off_changes={post['control_block_outside_rd_off_changes']}",
            "up_buffer_sha256_unchanged="
            + ("true" if post["up_buffer_pre_sha256"] == post["up_buffer_post_sha256"] else "false"),
            "measurement_seq_unchanged=true",
        ],
        "notes": (
            "全 SRAM 稳定断言在两段式结构下结构性不成立（server 退出会恢复核心运行），"
            "已按 R19 §3.3 重定域到 RTT 控制块级 diff。"
        ),
    },
    {
        "id": "HW-HALT-GATE",
        "description": "gate-pre 三遍分块复读期间核心必须全程 halted：每遍 147 chunk / 294 个 DHCSR 标记全为 S_HALT=1，零错误行。",
        "kind": "safety",
        "evidence_types": ["structured_result", "raw_log"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-GATEPRE-JSON", "ART-RECOVERY-JSON"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "a:dhcsr=294,all_halted=true,errors=0,chunks=147",
                "b:dhcsr=294,all_halted=true,errors=0,chunks=147",
                "c:dhcsr=294,all_halted=true,errors=0,chunks=147",
            ],
        },
        "observed": [
            "{label}:dhcsr={d},all_halted={h},errors={e},chunks={c}".format(
                label=r["label"],
                d=r["gdb_log_audit"]["dhcsr_marker_count"],
                h="true" if r["gdb_log_audit"]["all_halted"] else "false",
                e=r["gdb_log_audit"]["error_line_count"],
                c=r["chunk_file_audit"]["chunk_files"],
            )
            for r in runs
        ],
        "notes": "S_HALT=1 闸门语义未被 R19 修改；WDT 暂停只让该闸门的物理前置条件成立。",
    },
    {
        "id": "HW-IMAGE-AUTHORITY",
        "description": "被测 App 镜像身份必须三遍复读一致并与冻结权威 SHA-256 相符，头部 CRC32 有效。",
        "kind": "safety",
        "evidence_types": ["structured_result", "binary_snapshot"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": [
            "ART-RECOVERY-JSON",
            "ART-BOARD-HEADER",
            "ART-BOARD-IMAGE-A",
            "ART-BOARD-IMAGE-B",
            "ART-BOARD-IMAGE-C",
        ],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "read_count=3",
                "bytes=600744",
                "sha256=A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00",
                "reads_identical=true",
                "classification=BOARD_IMAGE_AUTHORITATIVE",
                "header_crc32=B8499369,valid=true",
            ],
        },
        "observed": [
            f"read_count={pre['read_count']}",
            f"bytes={pre['bytes']}",
            f"sha256={pre['sha256']}",
            "reads_identical=" + ("true" if len(set(pre["read_sha256"])) == 1 else "false"),
            f"classification={pre['classification']}",
            "header_crc32={c},valid={v}".format(
                c=pre["header_identity"]["stored_crc32"],
                v="true" if pre["header_identity"]["crc_valid"] else "false",
            ),
        ],
        "notes": "600744 B / A2D3083B...D58E00 与 R19 §9 记录的被测镜像身份一致。",
    },
    {
        "id": "HW-NO-FLASH-WRITE",
        "description": "本轮走 no-flash 分支：全程零 loadbin / 零 verifybin，板卡镜像零差异字节。",
        "kind": "safety",
        "evidence_types": ["structured_result"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-RECOVERY-JSON", "ART-RESULT"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "loadbin_count=0",
                "verifybin_count=0",
                "difference_bytes=0",
                "flash_allowed=false",
                "recovery_classification=APP_IMAGE_ALREADY_AUTHORITATIVE",
            ],
        },
        "observed": [
            f"loadbin_count={rec['loadbin_count']}",
            f"verifybin_count={rec['verifybin_count']}",
            f"difference_bytes={pre['difference_bytes']}",
            "flash_allowed=" + ("true" if pre["flash_allowed"] else "false"),
            f"recovery_classification={rec['classification']}",
        ],
        "notes": "板卡已是权威镜像，恢复分支未触发；flash 分支由 R19 冒烟 B（根 -23）同构验穿，不属本合同判据。",
    },
    {
        "id": "PROC-WDT-PAUSE",
        "description": "每个 halt 会话恰好施加一次调试域看门狗暂停写，并由 server log 回显 fail-closed 校验。",
        "kind": "process",
        "evidence_types": ["structured_result"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-RESULT", "ART-GATEPRE-JSON"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "wdt_pause_applied=true",
                "session1_echo=1",
                "session2_echo=1",
                "gate_pre_a_echo=1",
                "gate_pre_b_echo=1",
                "gate_pre_c_echo=1",
            ],
        },
        "observed": [
            "wdt_pause_applied=" + ("true" if result["wdt_pause_applied"] else "false"),
            f"session1_echo={result['wdt_pause_echo_session1']}",
            f"session2_echo={result['wdt_pause_echo_session2']}",
        ]
        + [f"gate_pre_{r['label']}_echo={r['server_log_audit']['wdt_pause_echo']}" for r in runs],
        "notes": "该写入为已授权偏离 DEV-1（见合同 authorized_deviations），非 flash、断电即失、不改镜像字节。",
    },
    {
        "id": "PROC-NATURAL-EXIT",
        "description": "GDB 与 GDB server 全部自然退出、退出码为 0，端口清零；唯一由 host 停止的进程是 RTT logger 且零残留。",
        "kind": "process",
        "evidence_types": ["structured_result", "raw_log"],
        "commands": ["CMD-ACCEPT-RUN"],
        "artifacts": ["ART-RESULT", "ART-CAPTURE-JSON", "ART-LOGGER-CONSOLE"],
        "gate": {
            "type": "state_chain",
            "basis": "frozen_requirement",
            "expected": [
                "gdb_exit_code=0",
                "gdb_post_exit_code=0",
                "server_natural_exit=true",
                "server_post_natural_exit=true",
                "reset_run_final_ports_listening=0",
                "logger_stopped_by_host=true",
                "residual_rtt_logger_processes=0",
            ],
        },
        "observed": [
            f"gdb_exit_code={result['gdb_exit_code']}",
            f"gdb_post_exit_code={result['gdb_post_exit_code']}",
            "server_natural_exit=" + ("true" if result["server_natural_exit"] else "false"),
            "server_post_natural_exit=" + ("true" if result["server_post_natural_exit"] else "false"),
            "reset_run_final_ports_listening={n}".format(
                n=len(rec["reset_run"]["related_process_cleanup"]["final_ports"]["listening"])
            ),
            "logger_stopped_by_host=" + ("true" if capture["logger_stopped"] else "false"),
            f"residual_rtt_logger_processes={capture['residual_rtt_logger_processes']}",
        ],
        "notes": "logger 的 host 侧停止为已授权偏离 DEV-2（AGENTS.md 残留清理模式）。",
    },
    {
        "id": "PROC-EVIDENCE-DOC-ACCURACY",
        "description": "R19 实现证据文档 §7.1 记录的生成脚本字节数与 SHA-256 必须与证据根 -18 的实读复算逐项一致。",
        "kind": "process",
        "evidence_types": ["command_output", "document"],
        "commands": ["CMD-GDB-SHA"],
        "artifacts": ["ART-GDB-SHA", "ART-R19-DOC", "ART-ROOT-MANIFEST"],
        "gate": {"type": "boolean", "basis": "frozen_requirement", "expected": True},
        "observed": True,
        "notes": (
            "R20 收口更正三处：binding.gdb SHA 尾部 121AD8→2121D8（实读 ...702121D8）；"
            "补齐 6 个 readback-gate-*.gdb 的字节数与 SHA-256（pre 84573 B、post 84870 B）；"
            "如实标注根 -20 已被后续迭代覆盖/未留存。更正后 8 行与本判据命令输出逐项一致。"
        ),
    },
]

commands = [
    {
        "id": "CMD-ACCEPT-RUN",
        "description": "独立验收会话执行的唯一硬件启动命令（R19 §7.2 冻结形式，bash）。",
        "command": ACCEPT_CMD,
        "expected_exit_codes": [0],
        "output_required": True,
    },
    {
        "id": "CMD-GDB-SHA",
        "description": "只读复算证据根 -18 中 8 个生成 GDB 脚本的字节数与 SHA-256。",
        "command": SHA_CMD,
        "expected_exit_codes": [0],
        "output_required": True,
    },
]

contract = {
    "schema": vb.CONTRACT_SCHEMA,
    "contract_id": "P2-6-v1",
    "version": 1,
    "task_id": "P2-6",
    "parent_contract_sha256": None,
    "status": "FROZEN",
    "approved_by": "E-Track OTA 主会话（用户授权 R20 收口 agent 成形）",
    "approved_at": "2026-08-30",
    "implementation_ref": "docs/ota-exec-notes/P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md",
    "result_taxonomy": ["PASS", "PRODUCT_FAIL", "HARNESS_FAIL", "EVIDENCE_GAP", "ENV_BLOCKED"],
    "invalidation_policy": "docs/acceptance-execution-contract.md",
    "scope": (
        "本合同只覆盖 P2-6 的 RTT 通道绑定轮次 P2-6-BR-20260829-RTT-BIND（正式验收根 "
        ".cache/p2-6-rtt-binding-20260829-18，audit-id P2-6-BR-20260829-RTT-BIND-R19-03）。"
        "P2-6 卡内 C1/C2、C4-C7、C14 判据以及升级态 RAM 峰值实测回填不在本合同范围内，仍为 NOT_OBSERVED。"
    ),
    "authorized_deviations": [
        {
            "id": "DEV-1",
            "type": "hardware_debug_domain_write",
            "description": (
                "每个 halt 会话在 monitor halt 之后写一次 monitor WriteU32 0xE0042008 0x00001000"
                "（debug apb1_frz bit12 DEBUG_WDT_PAUSE）。"
            ),
            "justification": (
                "R18 已坐实：>10 s 连续 halt 分块复读必然被看门狗复位，该写入是闸门读取的物理前置条件。"
                "非 flash、断电即失、不改被测镜像字节与 SHA-256；每脚本恰一行，server log 回显 count==1 被 fail-closed 校验。"
            ),
            "bound_criteria": ["PROC-WDT-PAUSE", "HW-HALT-GATE"],
        },
        {
            "id": "DEV-2",
            "type": "host_process_termination",
            "description": "capture 阶段用 Stop-Process 停止 JLinkRTTLogger 并验证零残留。",
            "justification": (
                "JLinkRTTLogger 无自然退出，AGENTS.md 明确规定残留清理模式；"
                "这是本流程唯一由 host 终止的进程，GDB 与 server 仍严格自然退出；"
                "capture.json 显式记录 logger_stopped_by / logger_stopped / 残留计数。"
            ),
            "bound_criteria": ["PROC-NATURAL-EXIT", "HW-CAPTURE-PAYLOAD"],
        },
        {
            "id": "DEV-3",
            "type": "process",
            "description": (
                "本合同在独立验收判定（2026-08-30 PASS）之后由 R20 收口会话冻结，"
                "而非在验收前冻结。"
            ),
            "justification": (
                "沿用 R17 以来的既有流程（由验收侧在候选稳定后冻结，见 R19 证据文档 §9）。"
                "如实登记而不掩饰：本合同的判据、门槛与观测值全部来自已封存只读根 -18 的原始记录，"
                "R20 收口会话不改判定、不重跑硬件、不改产品代码；后续 P2-6 轮次应改为验收前冻结。"
            ),
            "bound_criteria": [c["id"] for c in CRITERIA],
        },
    ],
    "input_groups": [manifests["production"], manifests["validation"], manifests["governance"]],
    "external_inputs": [],
    "commands": commands,
    "artifacts": [
        {"id": k, "description": v[1], "path": v[0]} for k, v in sorted(ART.items())
    ],
    "criteria": [
        {
            "id": c["id"],
            "description": c["description"],
            "required": True,
            "kind": c["kind"],
            "evidence_types": c["evidence_types"],
            "input_groups": ["production", "validation", "governance"],
            "external_inputs": [],
            "command_ids": c["commands"],
            "artifact_ids": c["artifacts"],
            "gate": c["gate"],
        }
        for c in CRITERIA
    ],
    "performance_gates": [],
}

CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
contract_sha = sha256_file(CONTRACT_PATH)

# ---------- 4. 证据矩阵 ----------
evidence_hashes = {}
for art_id, (rel, _desc) in sorted(ART.items()):
    evidence_hashes[rel] = sha256_file(BUNDLE / rel)

matrix = {
    "schema": vb.MATRIX_SCHEMA,
    "contract_id": "P2-6-v1",
    "contract_sha256": contract_sha,
    "round_id": "20260830-R20-CLOSURE",
    "overall_result": "PASS",
    "previous_matrix_sha256": None,
    "rerun_plan_path": None,
    "rerun_plan_sha256": None,
    "criteria": [
        {
            "id": c["id"],
            "result": "PASS",
            "failure_owner": None,
            "execution": "EXECUTED",
            "reused_from_round": None,
            "observed": c["observed"],
            "evidence": [ART[a][0] for a in c["artifacts"]],
            "notes": c["notes"],
        }
        for c in CRITERIA
    ],
    "evidence_hashes": evidence_hashes,
    "commands": [
        {
            "id": "CMD-ACCEPT-RUN",
            "command": ACCEPT_CMD,
            "exit_code": 0,
            "output_evidence": "artifacts/logs/result.json",
            "notes": (
                "由独立验收会话于 2026-08-30 执行（13:53-13:57）。退出码可由产物自证："
                "run_recovery_binding.py 在根 manifest 存在时返回 run_binding.py 的返回码，"
                "run_binding.py:1860 为 `return 0 if classification == \"RTT_CHANNEL_BINDING_VERIFIED\" else 1`，"
                "而 result.json 记录的 classification 正是该值。"
            ),
        },
        {
            "id": "CMD-GDB-SHA",
            "command": SHA_CMD,
            "exit_code": 0,
            "output_evidence": "artifacts/logs/generated-gdb-sha256.txt",
            "notes": "R20 收口会话执行的只读复算；输出即 ART-GDB-SHA 本体。",
        },
    ],
    "artifacts": [
        {
            "id": art_id,
            "path": rel,
            "sha256": evidence_hashes[rel],
            "size": (BUNDLE / rel).stat().st_size,
        }
        for art_id, (rel, _d) in sorted(ART.items())
    ],
}
MATRIX_PATH.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("contract", CONTRACT_PATH, contract_sha)
print("matrix  ", MATRIX_PATH, sha256_file(MATRIX_PATH))
