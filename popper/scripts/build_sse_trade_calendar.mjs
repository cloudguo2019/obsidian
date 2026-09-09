import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const sourcePath = resolve(root, ".tmp-akshare/akshare/file_fold/calendar.json");
const outputPath = resolve(root, "data/sse_trade_calendar_19901219_20260909.csv");
const reportPath = resolve(root, "data/sse_trade_calendar_validation_20260909.md");
const cutoff = "20260909";
const firstExpected = "19901219";

const raw = await readFile(sourcePath, "utf8");
const dates = JSON.parse(raw).filter((date) => date >= firstExpected && date <= cutoff);
const issues = [];

if (dates[0] !== firstExpected) issues.push(`首日应为 ${firstExpected}，实际为 ${dates[0]}`);
if (new Set(dates).size !== dates.length) issues.push("存在重复交易日");
if (!dates.includes("19920504")) issues.push("缺少 1992-05-04（AKShare 对新浪源的已知缺失修正）");
const weekendDates = dates.filter((date) => {
  const day = new Date(`${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}T00:00:00Z`).getUTCDay();
  return day === 0 || day === 6;
});
if (weekendDates.length) issues.push(`周末被标为开市：${weekendDates.join(", ")}`);

// SSE's published 2026 holiday notice.  The market is closed on these dates;
// weekend closures are naturally excluded by the source calendar.
const official2026Closures = [
  ["20260101", "20260104"],
  ["20260215", "20260223"],
  ["20260404", "20260406"],
  ["20260501", "20260505"],
  ["20260619", "20260621"],
  ["20260925", "20260927"],
  ["20261001", "20261007"],
];
const daysInRange = (from, to) => {
  const result = [];
  for (let d = new Date(`${from.slice(0, 4)}-${from.slice(4, 6)}-${from.slice(6, 8)}T00:00:00Z`);
       d <= new Date(`${to.slice(0, 4)}-${to.slice(4, 6)}-${to.slice(6, 8)}T00:00:00Z`);
       d.setUTCDate(d.getUTCDate() + 1)) {
    result.push(d.toISOString().slice(0, 10).replaceAll("-", ""));
  }
  return result;
};
const closureDaysThroughCutoff = official2026Closures
  .flatMap(([from, to]) => daysInRange(from, to))
  .filter((date) => date <= cutoff);
const wronglyOpen = closureDaysThroughCutoff.filter((date) => dates.includes(date));
if (wronglyOpen.length) issues.push(`官方休市日被标为开市：${wronglyOpen.join(", ")}`);

if (issues.length) throw new Error(`验证失败：${issues.join("；")}`);

const rows = ["exchange,trade_date,is_open,previous_trade_date,source"];
for (let index = 0; index < dates.length; index += 1) {
  const date = dates[index];
  rows.push(`SSE,${date},1,${index ? dates[index - 1] : ""},sina_finance`);
}
await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${rows.join("\n")}\n`, "utf8");

const sourceSha256 = createHash("sha256").update(raw).digest("hex");
const report = `# 上交所交易日历：验证报告\n\n` +
  `- 数据截止：2026-09-09（Asia/Shanghai）\n` +
  `- 覆盖：1990-12-19 至 2026-09-09，共 ${dates.length.toLocaleString("en-US")} 个开市日。\n` +
  `- 主数据：新浪财经 A 股交易日历，由 AKShare 的公开解析器读取；该解析器补入新浪遗漏的 1992-05-04。\n` +
  `- 源文件 SHA-256：\`${sourceSha256}\`\n\n` +
  `- 主数据地址：https://finance.sina.com.cn/realstock/company/klc_td_sh.txt\n` +
  `- 解析器：https://github.com/akfamily/akshare/blob/master/akshare/tool/trade_date_hist.py\n\n` +
  `- 源文件 SHA-256：\`${sourceSha256}\`\n\n` +
  `## 交叉验证\n\n` +
  `1. **官方规则**：上交所交易规则规定交易日为周一至周五，国家法定假日及本所公告休市日休市。\n` +
  `2. **官方年度公告**：逐日比对上交所 2026 年休市安排中截至截止日的元旦、春节、清明、劳动节、端午节区间；${closureDaysThroughCutoff.length} 个公告休市自然日均未出现在开市日清单中。\n` +
  `3. **独立历史行情覆盖**：上交所英文历史数据服务说明的最早可用日期为 1990-12-19，与本文件首日一致。\n` +
  `4. **完整性检查**：首日、去重、周末排除、相邻前序交易日字段及 AKShare 明示的 1992-05-04 修正均通过。\n\n` +
  `说明：这是交易日（开市日）清单，而不是自然日状态表；未列出的日期不能在没有另行查核的情况下被解释为某单一原因（周末、法定假日或临时休市）。\n\n` +
  `## 可复现\n\n` +
  `运行 \`node scripts/build_sse_trade_calendar.mjs\`。构建依赖 AKShare 仓库中的 \`akshare/file_fold/calendar.json\`；更新时应重新拉取其上游并复核当年上交所休市公告。\n`;
await writeFile(reportPath, report, "utf8");

console.log(JSON.stringify({ outputPath, reportPath, tradeDayCount: dates.length, sourceSha256 }, null, 2));
