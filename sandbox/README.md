## 本地测试夹具

这个目录用于在仓库内直接验证 `patch.py` 的扫描、修复和回滚逻辑，不依赖你机器上的真实 Claude Code 插件。

### 目录说明

- `extensions-root/anthropic.claude-code-1.2.3/`
  - `webview/index.js` 含有坏表达式 `$.text.trim()`
  - 用于验证 `--check` 能识别 `需要修复`
- `extensions-root/anthropic.claude-code-1.2.4/`
  - `webview/index.js` 已经是修复后的表达式
  - 同目录下带有 `index.js.claude-code-trim.bak`
  - 用于验证 `已修复` 状态和 `--rollback`
- `extensions-root/anthropic.claude-code-1.2.5/`
  - `webview/index.js` 不包含坏表达式，也不包含修复表达式
  - 用于验证 `正常` 状态
- `extensions-root/anthropic.claude-code-1.2.6/`
  - 故意不提供 `webview/index.js`
  - 用于确认扫描逻辑会忽略不完整安装目录

### 常用命令

```bash
python3 patch.py --check --extensions-dir ./sandbox/extensions-root
python3 patch.py --apply --extensions-dir ./sandbox/extensions-root
python3 patch.py --rollback --extensions-dir ./sandbox/extensions-root
```

### 预期现象

- 初始状态下：
  - `1.2.3` 显示 `需要修复`
  - `1.2.4` 显示 `已修复`
  - `1.2.5` 显示 `正常`
- 执行 `--apply` 后：
  - `1.2.3` 变为 `已修复`，并生成备份文件
- 执行 `--rollback` 后：
  - 有备份的版本会恢复为备份内容
