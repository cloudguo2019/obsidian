# HD-ANCHOR-001 阶段11 Python环境勘误

> [已观察事实｜A] 勘误日期：2026-09-14（Asia/Shanghai）。本文件只更正阶段11报告及清单对本机Python环境可用性的判断，不改变任何策略、数据、样本、账户、绩效或研究结论。

## 一、被更正的陈述

[已观察事实｜A] `PHASE11_FORMAL_REPORT_2026-09-14.md`第十二节和`stage11_formal_report_manifest_v1.0_prelock.json`的`stage11_environment_check`把专用Python 3.11.9环境记为“基础解释器缺失、虚拟环境不能启动”。该判断发生在受限沙箱内，进程启动返回`Access is denied`/`Unable to create process`，当时被错误解释为解释器文件缺失。

[方法选择] 阶段11报告和v1.0清单已经冻结，不覆盖原文件；本勘误对环境字段形成唯一后续覆盖。阶段11的经济结果、哈希绑定、研究决策和证据上限不受影响。

## 二、沙箱外核验结果

- [已观察事实｜A] 基础解释器`C:/Users/cg/AppData/Local/Programs/Python/Python311/python.exe`存在，可运行，版本为Python 3.11.9；SHA-256为`5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec`。
- [已观察事实｜A] 该解释器Windows Authenticode状态为`Valid`，签名主体为Python Software Foundation。
- [已观察事实｜A] 虚拟环境入口`C:/Users/cg/AppData/Local/venvs/high-dividend-bond-py311/Scripts/python.exe`存在，可运行，版本为Python 3.11.9；SHA-256为`21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082`。
- [已观察事实｜A] 虚拟环境依赖实测为AkShare 1.18.94、pandas 3.0.5、PyArrow 25.0.1，与冻结运行记录和依赖锁一致。
- [计算结果｜A] 使用该虚拟环境重新执行阶段8合成测试，31/31通过。
- [计算结果｜A] 使用该虚拟环境重新执行`validate_stage8_formal_l2_outputs.py`，冻结正式L2产物完整性验证通过：96条登记路径、92条完成、4条P21 `NOT_RUN`、77,640行逐日账户、483行窗口、207个Bootstrap区间，最大日期2025-09-09，历史伪锁定未开启。
- [计算结果｜A] 阶段11只读报告验证通过：阶段11的6个绑定及阶段8—10三个清单的47个实际文件绑定一致。

## 三、正确结论与后续边界

[计算结果｜A] Python 3.11冻结环境当前健康，无需重新安装、修复或变更依赖。问题是沙箱执行权限，而不是环境损坏。

[方法选择] 后续在本机运行该环境必须使用已批准的沙箱外执行权限；不得把权限差异登记为依赖或代码变化。任何重新回测仍必须使用新输出路径、保留原冻结结果，并取得对准确区间、配置集合和运行次数的明确授权。

