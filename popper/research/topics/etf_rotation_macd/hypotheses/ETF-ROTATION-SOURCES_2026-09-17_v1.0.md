# ETF轮动阶段2原始来源记录 v1.0

> 核查日期：2026-09-17。对应[理论与证伪v1.0](ETF-ROTATION-THEORY_v1.0.md)。

[方法选择] 只用原作者研究页面/论文摘要作为机制背景与方法依据。本轮不下载或导入外部收益数据、不精读论文全文、不依据外部结果选择本项目参数。来源等级B指可追溯原始研究，不能代替本项目经济证据。

| ID | 原始来源与版本 | 本轮实际读取范围 | 支持的命题 | 不支持的外推 |
|---|---|---|---|---|
| S1 | Jegadeesh & Titman，NBER WP7159（1999），发表于Journal of Finance（2001）；[论文页面](https://www.nber.org/papers/w7159)，DOI 10.3386/w7159 | 搜索返回的原始论文页摘要；直接open失败 | 股票横截面动量存在竞争解释，行为解释需谨慎 | 中国ETF、20/60日/波动扣分、5000元集合竞价可获相同效果 |
| S2 | Moskowitz, Ooi & Pedersen，Time Series Momentum，Journal of Financial Economics（2012）；[作者机构研究页](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum) | 研究页说明；页面成功打开 | 自身历史收益预测与横截面排序是不同问题 | 该研究直接检验DIF>DEA，或证明其优于MA20 |
| S3 | Hong, Lim & Stein，NBER WP6553（1998），发表于Journal of Finance（2000）；[论文页面](https://www.nber.org/papers/w6553)，DOI 10.3386/w6553 | 搜索返回原始论文页摘要；直接open失败 | 信息扩散是一类可讨论的动量机制解释 | 本项目ETF资金流或信息扩散已被识别 |
| S4 | Sullivan, Timmermann & White，UCSD Discussion Paper97-31（1997），作者SSRN登记摘要；[原始摘要](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=65140) | 搜索返回的作者摘要；直接open为403 | 技术交易规则须考虑候选规则全集与数据窥探；样本内最佳不保证后续表现 | 某Bootstrap数值、块长或收益阈值可以直接用于本项目 |

[已观察事实｜B] S1讨论动量收益的竞争解释，对行为解释持谨慎结论。本项目据此保留竞争机制，不将价格延续直接解释为信息吸收。[原始摘要](https://www.nber.org/papers/w7159)。

[已观察事实｜B] S2区分基于自身历史收益的时间序列动量与基于相对表现的横截面动量。本项目据此拆分排名与趋势问题；其研究设计并非MA/MACD状态的本地比较。[原始研究页](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)。

[已观察事实｜B] S3将信息扩散作为股票动量机制的研究问题。把该机制延伸到ETF指数与资金配置只是本项目研究假设。[原始摘要](https://www.nber.org/papers/w6553)。

[已观察事实｜B] S4摘要说明利用Reality Check处理技术规则集合中的数据窥探，并报告其样本内最佳规则未在后续样本保持优势。本项目仅引用检验纪律。[原始摘要](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=65140)。

[已知限制] 文献摘要核查不能代替全文方法复现或中国ETF样本验证。网页内容可变，本文件保存访问日期、文献身份、短摘要与读取限制；网页哈希未归档。本地文件SHA-256只证明本记录身份，不证明远程内容不可变。

## 本地权威来源

[已观察事实｜A] 本轮直接读取框架第20—26节、阶段1合并基线/闭环、冻结章程v1.2、工程规格v0.1/v0.2及初始库存前部；直接读取独立MACD核心并重核ETF核心/MACD核心/配置三项哈希。工程观察的公式与默认暖机来自这些本地材料，不来自文献。

[方法选择] 本轮具体输入与输出身份见[阶段2清单](../decisions/PHASE2_MANIFEST_2026-09-17_v1.0.json)。历史冻结协议、阶段1清单/结果与原始数据保持原样，README与项目记忆是可更新索引，不纳入冻结哈希集合。
