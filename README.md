# Claude Code VS Code 插件自动修复脚本

这个项目提供一个简单的 Python 脚本，用来检测并修复 Claude Code VS Code 插件中由于 `$.text.trim()` 空值访问引起的 WebView 渲染报错。

常见报错如下：

```text
Something went wrong
Re-launch the extension to continue.

Error rendering content: Cannot read properties of undefined (reading 'trim')
```

脚本会把插件 `webview/index.js` 中的：

```js
$.text.trim()
```

替换为：

```js
($.text || "").trim()
```

## 功能

- 自动扫描本机已安装的 Claude Code VS Code 插件
- 检测哪些版本仍然存在 `$.text.trim()` 问题
- 自动修复命中的版本
- 支持通过备份文件自动回滚
- 修复前自动备份原始文件
- 适配 Windows、macOS
- 额外兼容 VS Code Insiders 的扩展目录

## 默认扫描目录

脚本默认会扫描以下目录：

- Windows: `%USERPROFILE%\\.vscode\\extensions`
- Windows Insiders: `%USERPROFILE%\\.vscode-insiders\\extensions`
- macOS: `~/.vscode/extensions`
- macOS Insiders: `~/.vscode-insiders/extensions`

如果你的扩展安装在其他位置，也可以通过参数手动指定。

## 环境要求

- Python 3.9+

如果你的 Windows 里 `python` 命令不可用，也可以尝试：

```powershell
py -3 patch.py
```

## 使用方法

### 1. 仅检测，不修改文件

```bash
python patch.py --check
```

这个模式会扫描本机插件并输出状态，但不会真正修改任何文件。

### 2. 无参数时仅显示帮助

```bash
python patch.py
```

为了避免误修改文件，脚本在不带任何模式参数时只会输出帮助信息，不会执行修复。
如果传了 `--extensions-dir` 等参数但没有同时指定 `--apply`、`--check` 或 `--rollback`，脚本会直接报错，避免把无效命令当成成功执行。

### 3. 显式检测并修复

```bash
python patch.py --apply
```

### 4. 指定自定义扩展目录
如果你想在指定目录上执行修复，需要显式传入 `--apply`：

```bash
python patch.py --apply --extensions-dir "/path/to/extensions"
```

如果有多个目录，也可以重复传入：

```bash
python patch.py --apply --extensions-dir "/path/a" --extensions-dir "/path/b"
```

修复模式会：

1. 扫描所有 Claude Code 插件目录
2. 找出仍包含 `$.text.trim()` 的版本
3. 自动替换为 `($.text || "").trim()`
4. 在原文件旁边生成备份文件

### 5. 自动回滚到修复前版本

```bash
python patch.py --rollback
```

这个模式会查找脚本之前生成的备份文件，并把对应的 `index.js` 恢复为备份内容。

如果你同时使用了自定义扩展目录，也可以这样写：

```bash
python patch.py --rollback --extensions-dir "/path/to/extensions"
```

## 输出说明

脚本会给每个检测到的 Claude Code 插件目录显示一个状态：

- `需要修复`：仍然存在 `$.text.trim()`，脚本会进行修复
- `已修复`：当前文件中已经存在修复后的表达式，通常表示你之前已经手动修过
- `正常`：当前未检测到坏表达式，也未检测到修复表达式

同时也会显示该版本是否存在备份文件。

## 备份与回滚

每次修复前，脚本都会在原文件旁边创建一个备份文件：

```text
index.js.claude-code-trim.bak
```

如果你想自动回滚，可以直接执行：

```bash
python patch.py --rollback
```

如果你想手动回滚，也可以把备份文件恢复为原文件。

## 建议操作

修复完成后建议：

- 关闭并重新打开 VS Code
- 或执行 `Developer: Reload Window`
- 如果 Claude Code 面板已经打开，重新打开一次插件界面

## 文件说明

- [patch.py](C:\Users\22057\Documents\Code\cc-auto-patch\patch.py): 自动检测并修复脚本
