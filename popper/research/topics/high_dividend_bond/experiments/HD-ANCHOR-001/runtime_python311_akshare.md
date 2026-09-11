# HD-ANCHOR-001 Python 3.11与AkShare运行环境

> [已观察事实｜A] 安装日期：2026-09-10（Asia/Shanghai）。本环境只用于数据采集与交叉核验，未运行策略回测或打开锁定集。

[已观察事实｜A] Python 3.11.9 64位安装包来自`https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe`；文件大小26,216,840字节，MD5为`e8dcd502e34932eebcaf1be056d5cbcd`，与Python.org 3.11.9发布页一致。

[已观察事实｜A] 安装包SHA-256为`5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde`；Windows Authenticode状态为`Valid`，签名主体为`Python Software Foundation`。

[已观察事实｜A] 解释器安装于`C:/Users/cg/AppData/Local/Programs/Python/Python311/python.exe`，版本输出为`Python 3.11.9`；研究虚拟环境入口为`C:/Users/cg/AppData/Local/venvs/high-dividend-bond-py311/Scripts/python.exe`。

[已观察事实｜A] AkShare固定为1.18.94，Pandas固定为3.0.5，PyArrow固定为25.0.1；完整依赖版本见[`requirements-akshare-python311.lock.txt`](../../requirements-akshare-python311.lock.txt)。

[方法选择｜C] Python 3.11.9是Python.org为3.11系列提供传统Windows完整安装程序的最后一个常规bugfix版本；后续3.11安全修订不再用本轮传统安装包口径自动替换，以避免复现环境漂移。

[已知限制｜B] AkShare是数据接口库而不是交易所原始档案。使用时必须同时记录接口、上游网站、参数、获取时间和原始快照哈希。

