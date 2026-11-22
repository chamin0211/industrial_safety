#!/usr/bin/env python3
"""학습형 하네스 차단 장치 (PLAN 9장, AGENTS.md).

Claude가 도구를 쓰기 직전에 실행되어, 규칙을 어기는 동작을 막는다.
- 파일 쓰기: 프로젝트 안에서는 허용 목록(docs/, AGENTS.md, CLAUDE.md, .claude/)만 허용
- 셸 명령: 저장소를 바꾸는 git 명령, .env 접근, 앱 코드 폴더에 쓰는 명령을 차단
"""
import json
import os
import re
import sys

PROJECT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

# Claude가 직접 써도 되는 위치 (프로젝트 기준 상대 경로)
WRITE_ALLOWED = ("docs/", ".claude/", "AGENTS.md", "CLAUDE.md")

# 셸 명령으로 쓰기를 막을 앱 코드·데이터 폴더
PROTECTED_DIRS = ("backend", "frontend", "scripts", "tests", "src", "data", "evals")

GIT_WRITE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)?"
    r"(add|commit|push|pull|fetch|merge|rebase|reset|revert|cherry-pick|checkout|switch|"
    r"restore|rm|mv|remote|tag|branch|stash|init|clone|config|am|apply|clean|submodule)\b"
)
ENV_FILE = re.compile(r"(?:^|[\s/'\"=<>])\.env(?!\.example)(?:\.[\w-]+)?(?=$|[\s'\";|&)])")
WRITE_OP = re.compile(r"(>|\btee\b|\bcp\b|\bmv\b|\brm\b|\btouch\b|\bmkdir\b|\bsed\s+-i|\bchmod\b|\bln\b)")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[학습형 하네스] {reason}",
        }
    }, ensure_ascii=False))
    sys.exit(0)


def check_file(path: str) -> None:
    if not path:
        return
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(PROJECT, path))
    if not (full == PROJECT or full.startswith(PROJECT + os.sep)):
        return  # 프로젝트 밖(메모리, 임시 폴더 등)은 이 훅의 대상이 아님
    rel = os.path.relpath(full, PROJECT)
    name = os.path.basename(rel)
    if name == ".env" or name.startswith(".env.") and name != ".env.example":
        deny(f"{rel}: .env 파일은 읽거나 쓰지 않습니다.")
    if not any(rel == a.rstrip("/") or rel.startswith(a) for a in WRITE_ALLOWED):
        deny(f"{rel}: 이 위치는 개발자가 직접 작성합니다. 코드는 대화로 보내 주세요.")


def check_bash(cmd: str) -> None:
    if GIT_WRITE.search(cmd):
        deny("저장소를 바꾸는 git 명령은 실행하지 않습니다. 명령과 설명을 알려 주고 개발자가 실행합니다.")
    if ENV_FILE.search(cmd):
        deny(".env 파일은 읽거나 쓰지 않습니다.")
    if WRITE_OP.search(cmd):
        for d in PROTECTED_DIRS:
            if re.search(rf"(?:^|[\s'\"=/]){d}/", cmd):
                deny(f"{d}/ 에 쓰는 명령은 실행하지 않습니다. 코드는 대화로 보내 주세요.")


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {}) or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        check_file(inp.get("file_path") or inp.get("notebook_path", ""))
    elif tool == "Read":
        name = os.path.basename(inp.get("file_path", ""))
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            deny(".env 파일은 읽지 않습니다.")
    elif tool == "Bash":
        check_bash(inp.get("command", ""))


if __name__ == "__main__":
    main()
