#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXTENSION_GLOB = "anthropic.claude-code-*"
INDEX_JS_RELATIVE_PATH = Path("webview") / "index.js"
BROKEN_EXPR = "$.text.trim()"
FIXED_EXPR = '($.text || "").trim()'
BACKUP_SUFFIX = ".claude-code-trim.bak"
SYMBOL_INFO = "[*]"
SYMBOL_OK = "[+]"
SYMBOL_WARN = "[!]"
SYMBOL_ITEM = "[-]"
SYMBOL_SUMMARY = "[=]"


@dataclass(frozen=True)
class ExtensionCandidate:
    root: Path
    extension_dir: Path
    index_js: Path

    @property
    def name(self) -> str:
        return self.extension_dir.name


@dataclass(frozen=True)
class ScanResult:
    candidate: ExtensionCandidate
    broken_count: int
    fixed_count: int
    backup_exists: bool

    @property
    def needs_patch(self) -> bool:
        return self.broken_count > 0

    @property
    def already_patched(self) -> bool:
        return self.broken_count == 0 and self.fixed_count > 0

    @property
    def status_label(self) -> str:
        if self.needs_patch:
            return "需要修复"
        if self.already_patched:
            return "已修复"
        return "正常"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "检测并修复 Claude Code VS Code 插件中由于不安全的 "
            "$.text.trim() 访问导致的问题。"
        )
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="检测并修复问题。这个模式会修改文件。",
    )
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="仅检测问题，不修改任何文件。",
    )
    mode_group.add_argument(
        "--rollback",
        action="store_true",
        help="使用之前生成的备份文件自动回滚。",
    )
    parser.add_argument(
        "--extensions-dir",
        action="append",
        default=[],
        help=(
            "要扫描的扩展目录。"
            "可多次传入。"
            "如果不传，则使用当前平台的默认 VS Code 扩展目录。"
        ),
    )
    return parser


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    return parser.parse_args()


def default_extension_roots() -> list[Path]:
    home = Path.home()
    system = platform.system()

    if system in {"Windows", "Darwin", "Linux"}:
        candidates = [
            home / ".vscode" / "extensions",
            home / ".vscode-insiders" / "extensions",
        ]
    else:
        candidates = [home / ".vscode" / "extensions"]

    return dedupe_paths(candidates)


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []

    for path in paths:
        expanded = path.expanduser()
        try:
            normalized = expanded.resolve(strict=False)
        except OSError:
            normalized = expanded

        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)

    return ordered


def version_key(extension_dir: Path) -> tuple[int, ...]:
    parts = extension_dir.name.split("-")
    if len(parts) < 4:
        return (0,)

    version = parts[2]
    numeric_parts: list[int] = []
    for piece in version.split("."):
        try:
            numeric_parts.append(int(piece))
        except ValueError:
            return (0,)
    return tuple(numeric_parts)


def discover_extensions(roots: Iterable[Path]) -> list[ExtensionCandidate]:
    discovered: list[ExtensionCandidate] = []

    for root in roots:
        if not root.is_dir():
            continue

        for extension_dir in root.glob(EXTENSION_GLOB):
            if not extension_dir.is_dir():
                continue

            index_js = extension_dir / INDEX_JS_RELATIVE_PATH
            if not index_js.is_file():
                continue

            discovered.append(
                ExtensionCandidate(
                    root=root,
                    extension_dir=extension_dir,
                    index_js=index_js,
                )
            )

    return sorted(
        discovered,
        key=lambda item: (str(item.root).lower(), version_key(item.extension_dir), item.name),
        reverse=True,
    )


def read_text_preserving_newlines(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        return handle.read()


def write_text_preserving_newlines(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        handle.write(content)


def scan_candidate(candidate: ExtensionCandidate) -> ScanResult:
    content = read_text_preserving_newlines(candidate.index_js)
    return ScanResult(
        candidate=candidate,
        broken_count=content.count(BROKEN_EXPR),
        fixed_count=content.count(FIXED_EXPR),
        backup_exists=backup_path_for(candidate.index_js).exists(),
    )


def backup_path_for(index_js: Path) -> Path:
    return index_js.with_name(index_js.name + BACKUP_SUFFIX)


def ensure_backup(index_js: Path) -> Path:
    backup_path = backup_path_for(index_js)
    if not backup_path.exists():
        shutil.copy2(index_js, backup_path)
    return backup_path


def rollback_candidate(candidate: ExtensionCandidate) -> Path:
    backup_path = backup_path_for(candidate.index_js)
    if not backup_path.exists():
        raise ValueError(f"{candidate.index_js} 不存在可用的备份文件。")

    shutil.copy2(backup_path, candidate.index_js)
    return backup_path


def patch_candidate(result: ScanResult) -> tuple[int, Path]:
    if not result.needs_patch:
        raise ValueError(f"{result.candidate.index_js} 当前不需要修复。")

    content = read_text_preserving_newlines(result.candidate.index_js)
    occurrences = content.count(BROKEN_EXPR)
    if occurrences == 0:
        raise RuntimeError("修复过程中目标内容已变化，未找到待替换的坏表达式。")

    backup_path = ensure_backup(result.candidate.index_js)
    patched = content.replace(BROKEN_EXPR, FIXED_EXPR)
    write_text_preserving_newlines(result.candidate.index_js, patched)

    verify_content = read_text_preserving_newlines(result.candidate.index_js)
    remaining = verify_content.count(BROKEN_EXPR)
    if remaining != 0:
        raise RuntimeError(
            f"{result.candidate.index_js} 修复校验失败；"
            f"仍有 {remaining} 处坏表达式残留。"
        )

    return occurrences, backup_path


def print_scan_report(results: list[ScanResult]) -> None:
    for result in results:
        symbol = SYMBOL_WARN if result.needs_patch else SYMBOL_OK
        print(f"{symbol} {result.status_label}: {result.candidate.name}")
        print(f"  路径: {result.candidate.index_js}")
        print(f"  坏表达式数量: {result.broken_count}")
        print(f"  已修复表达式数量: {result.fixed_count}")
        print(f"  备份文件: {'有' if result.backup_exists else '无'}")


def print_check_report(results: list[ScanResult]) -> None:
    needs_patch = [result for result in results if result.needs_patch]
    already_patched = [result for result in results if result.already_patched]
    normal = [
        result for result in results if not result.needs_patch and not result.already_patched
    ]

    print(f"\n{SYMBOL_SUMMARY} 检查摘要")
    print(f"  {SYMBOL_ITEM} 安装目录总数: {len(results)}")
    print(f"  {SYMBOL_WARN} 需要修复: {len(needs_patch)}")
    print(f"  {SYMBOL_OK} 已修复: {len(already_patched)}")
    print(f"  {SYMBOL_INFO} 正常: {len(normal)}")

    sections = [
        (f"{SYMBOL_WARN} 需要修复", needs_patch),
        (f"{SYMBOL_OK} 已修复", already_patched),
        (f"{SYMBOL_INFO} 正常", normal),
    ]

    for section_name, section_results in sections:
        if not section_results:
            continue

        print(f"\n{section_name} ({len(section_results)})")
        for result in section_results:
            detail = (
                f"坏表达式 {result.broken_count} 处，"
                f"已修复表达式 {result.fixed_count} 处，"
                f"备份 {'有' if result.backup_exists else '无'}"
            )
            print(f"{SYMBOL_ITEM} {result.candidate.name}")
            print(f"  文件: {result.candidate.index_js}")
            print(f"  详情: {detail}")


def main() -> int:
    parser = build_parser()
    args = parse_args(parser)
    if not (args.apply or args.check or args.rollback):
        if len(sys.argv) > 1:
            parser.error("传入参数时必须同时指定 --apply、--check 或 --rollback。")
        parser.print_help()
        print(f"\n{SYMBOL_INFO} 提示: 使用 --apply 才会实际修复文件。")
        return 0

    roots = (
        dedupe_paths(Path(path) for path in args.extensions_dir)
        if args.extensions_dir
        else default_extension_roots()
    )

    print(f"{SYMBOL_INFO} 正在扫描以下扩展目录:")
    for root in roots:
        print(f"  {SYMBOL_ITEM} {root}")

    candidates = discover_extensions(roots)
    if not candidates:
        print(f"{SYMBOL_WARN} 未找到 Claude Code VS Code 插件。")
        if args.extensions_dir:
            print(f"{SYMBOL_INFO} 提示: 如果插件安装在其他位置，请传入正确的 --extensions-dir。")
        return 1

    results = [scan_candidate(candidate) for candidate in candidates]
    to_patch = [result for result in results if result.needs_patch]

    if args.check:
        print_check_report(results)
        print()
        if to_patch:
            print(f"{SYMBOL_WARN} 检测到 {len(to_patch)} 个安装目录仍需修复。")
            return 2
        print(f"{SYMBOL_OK} 未发现需要修复的问题。")
        return 0

    print(f"\n{SYMBOL_SUMMARY} 共发现 {len(results)} 个 Claude Code 插件安装目录。\n")
    print_scan_report(results)

    if args.rollback:
        to_rollback = [result for result in results if result.backup_exists]
        print()
        if not to_rollback:
            print(f"{SYMBOL_WARN} 未找到可用于回滚的备份文件。")
            return 0

        rolled_back_files = 0
        for result in to_rollback:
            backup_path = rollback_candidate(result.candidate)
            rolled_back_files += 1
            print(f"{SYMBOL_OK} 已回滚 {result.candidate.name}")
            print(f"  恢复来源: {backup_path}")
            print(f"  已恢复到: {result.candidate.index_js}")

        print(f"\n{SYMBOL_OK} 处理完成，共回滚 {rolled_back_files} 个文件。")
        return 0

    if not to_patch:
        print(f"\n{SYMBOL_OK} 未发现需要修复的问题。")
        return 0

    print()
    patched_files = 0
    for result in to_patch:
        replaced, backup_path = patch_candidate(result)
        patched_files += 1
        print(f"{SYMBOL_OK} 已修复 {result.candidate.name}")
        print(f"  替换次数: {replaced}")
        print(f"  备份文件: {backup_path}")

    print(f"\n{SYMBOL_OK} 处理完成，共修复 {patched_files} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
