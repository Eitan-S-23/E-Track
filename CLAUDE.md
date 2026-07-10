# CLAUDE.md（本项目专属指引）

> 本文件由 Claude Code 在本仓库会话时自动加载。
> 编译固件 / 验证 UI / Dialplate 等权威指引统一维护在 `AGENTS.md`，下面通过 `@AGENTS.md` 导入。
> 因此本仓库的 agent 指引只需维护 `AGENTS.md` 一份，Claude Code 与 Codex 等共用，勿在此重复编辑编译流程。

@AGENTS.md

## Claude Code 运行环境补充（AGENTS.md 未覆盖部分）

- 全局准则（中文输出、验证留痕、复用优先等）仍以 `~/.claude/CLAUDE.md` 为准。
- 路径在 bash 用正斜杠；`/tmp` 不等于 `C:\tmp`，要落到真实 Windows 路径（如 `.claude/`）。
- 从 bash 调用 `.bat`：直接 `./xxx.bat --no-pause` 即可；遇参数解析异常用 `cmd //c xxx.bat ...`。
- 从 bash 调用 `.ps1`：用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'script' -arg @('a','b')"`；`-File` 方式会把数组当成单字符串。
