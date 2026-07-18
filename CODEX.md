# Codex + Obsidian + GitHub

此目录是独立的 Obsidian Vault 和 Git 仓库。Codex 生成的报告统一放在 `reports/`，这样电脑与手机端拉取后都能直接看到。

## 官方 Obsidian CLI（Windows）

1. 使用 Obsidian 1.12.7 或更高版本。
2. 打开 **设置 → 常规 → 命令行界面**，启用并按提示注册 CLI。
3. 重启终端，在本目录验证：

```powershell
obsidian version
obsidian files total
obsidian search query="报告" path="reports" limit=5
```

Obsidian 应用需保持运行。CLI 会根据当前目录自动识别本 Vault。

## GitHub 同步

手动安全同步：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/Sync-Vault.ps1
```

脚本按 `pull --rebase → add → commit → push` 执行；没有改动时不会创建空提交。也可传入提交信息：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/Sync-Vault.ps1 -Message "report: 新报告"
```

## 手机端

1. 在手机 Obsidian 中安装并启用 **Obsidian Git** 社区插件。
2. 将 `https://github.com/cloudguo2019/obsidian.git` 克隆为 Vault；私有仓库需使用 GitHub Personal Access Token，令牌只保存在手机端，不写入仓库。
3. 插件设置中启用启动时 pull、编辑后自动 commit，并设置定时 pull/push。
4. 每次跨设备编辑前先 pull，编辑后 push；发生冲突时先保留两份内容再人工合并。

> GitHub 是这里的同步通道；官方 Obsidian CLI 负责 Codex/终端操作 Vault，本身不会代替 Git push/pull。

