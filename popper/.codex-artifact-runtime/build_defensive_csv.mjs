import fs from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { Workbook } from "@oai/artifact-tool";

const outputPath = "C:\\Users\\cg\\Desktop\\Nietzsche\\obsidian\\popper\\a股防守型上涨股票_2026-09-11.csv";
const previewPath = "C:\\Users\\cg\\Desktop\\Nietzsche\\obsidian\\popper\\.codex-artifact-runtime\\a股防守型上涨股票_2026-09-11_preview.png";

const nodes = [
  ["银行", "sw_yx"],
  ["公用事业", "sw_gysy"],
  ["医药生物", "sw_yysw"],
  ["食品饮料", "sw_spyl"],
  ["通信服务", "sw2_730100"],
  ["铁路公路", "sw2_420900"],
  ["个护用品", "sw2_770100"],
];

function runPowerShell(script) {
  const result = spawnSync("pwsh.exe", ["-NoProfile", "-NonInteractive", "-Command", script], {
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error(`PowerShell failed (${result.status}): ${result.stderr || result.stdout}`);
  }
  return result.stdout.trim();
}

const nodeLiteral = nodes
  .map(([label, node]) => `@{label='${label}';node='${node}'}`)
  .join(",");

const primaryScript = `
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$nodes=@(${nodeLiteral})
$out=@()
foreach($entry in $nodes){
  $url='http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=100&sort=changepercent&asc=0&node='+$entry.node+'&symbol=&_s_r_a=init'
  $data=$null
  foreach($attempt in 1..3){
    try{
      $data=(Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15 -Headers @{Referer='http://vip.stock.finance.sina.com.cn/';'User-Agent'='Mozilla/5.0'}).Content | ConvertFrom-Json
      if($data.Count -gt 0){break}
    }catch{if($attempt -eq 3){throw}}
  }
  foreach($row in $data){
    if([double]$row.changepercent -gt 0 -and $row.name -notmatch 'ST|退'){
      $row | Add-Member -NotePropertyName defensive_category -NotePropertyValue $entry.label
      $row | Add-Member -NotePropertyName source_node -NotePropertyValue $entry.node
      $out += $row
    }
  }
}
@($out) | ConvertTo-Json -Depth 5 -Compress
`;

const primaryRows = JSON.parse(runPowerShell(primaryScript));
if (!Array.isArray(primaryRows) || primaryRows.length < 70 || primaryRows.length > 100) {
  throw new Error(`Unexpected primary row count: ${primaryRows?.length}`);
}

const unique = new Map();
for (const row of primaryRows) unique.set(String(row.code), row);
const rows = [...unique.values()];

for (const requiredCode of ["601288", "601398", "601939", "601988"]) {
  if (!unique.has(requiredCode)) throw new Error(`Missing required bank code ${requiredCode}`);
}

function marketSymbol(code) {
  if (/^[689]/.test(code)) return `${code.startsWith("9") || code.startsWith("8") ? "bj" : "sh"}${code}`;
  return `sz${code}`;
}

const symbols = rows.map((r) => marketSymbol(String(r.code))).join(",");
const secondaryScript = `
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$url='http://qt.gtimg.cn/q=${symbols}'
(Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20 -Headers @{Referer='https://gu.qq.com/';'User-Agent'='Mozilla/5.0'}).Content
`;
const quoteText = runPowerShell(secondaryScript);

const secondary = new Map();
for (const match of quoteText.matchAll(/v_([a-z]+\d+)="([^"]*)";/g)) {
  const fields = match[2].split("~");
  if (fields.length < 47) continue;
  secondary.set(fields[2], {
    symbol: match[1],
    name: fields[1],
    close: Number(fields[3]),
    previousClose: Number(fields[4]),
    timestamp: fields[30],
    changeAmount: Number(fields[31]),
    changePercent: Number(fields[32]),
    turnover: Number(fields[38]),
    floatMarketCapYi: Number(fields[44]),
    totalMarketCapYi: Number(fields[45]),
  });
}

const coreCodes = new Set([
  "601939", "601988", "601328", "601288", "601398",
  "600803", "600900", "600025", "600795", "600021", "600023", "001286", "003816", "600483", "600236",
  "601728", "600941", "600050",
  "000429", "001965", "600350",
  "603288", "600887", "600298",
]);

const categoryOrder = new Map([
  ["银行", 1], ["公用事业", 2], ["通信服务", 3], ["铁路公路", 4],
  ["食品饮料", 5], ["医药生物", 6], ["个护用品", 7],
]);
const tierOrder = new Map([["核心防守", 1], ["一般防守", 2], ["仅行业属性", 3]]);

const meta = {
  银行: {
    type: "高股息金融",
    reason: "存贷与支付等基础金融需求稳定，成熟银行通常具备较高股息和较低估值",
    risk: "净息差收窄、资产质量、地产及地方债暴露、分红变化",
  },
  公用事业: {
    type: "必需公用服务",
    reason: "电力、燃气、供热等需求相对刚性，部分资产现金流和分红稳定",
    risk: "电价机制、燃料成本、来水来风、资本开支及新能源题材波动",
  },
  医药生物: {
    type: "刚需医疗",
    reason: "医疗需求受经济周期影响相对较小，但个股防守性取决于盈利和估值",
    risk: "集采降价、研发失败、产品集中、亏损和高估值回撤",
  },
  食品饮料: {
    type: "必选消费",
    reason: "食品、乳品和调味品具备重复消费特征，需求波动通常低于可选消费",
    risk: "消费疲弱、原料成本、渠道库存、品牌竞争及估值回撤",
  },
  通信服务: {
    type: "基础通信服务",
    reason: "基础通信需求和订阅现金流稳定，三大运营商兼具规模与分红属性",
    risk: "资本开支、资费竞争、技术迭代；非运营商个股可能高波动",
  },
  铁路公路: {
    type: "交通基础设施",
    reason: "收费公路和铁路资产具有持续通行需求，成熟项目现金流可预测性较强",
    risk: "车流量、收费政策、扩建资本开支和债务成本",
  },
  个护用品: {
    type: "日常消费",
    reason: "个人护理用品具有较高复购率，但小市值公司股价未必低波动",
    risk: "渠道竞争、营销费用、原材料价格及小市值波动",
  },
};

function exchange(code) {
  if (code.startsWith("6")) return "上海证券交易所";
  if (code.startsWith("0") || code.startsWith("3")) return "深圳证券交易所";
  return "北京证券交易所";
}

function classify(row, quote) {
  const code = String(row.code);
  const change = Number(row.changepercent);
  const turnover = Number(row.turnoverratio);
  const marketCapYi = Number(row.mktcap) / 10000;
  const flags = [];
  if (change >= 9.5) flags.push("接近或达到涨停");
  else if (change >= 5) flags.push("当日涨幅不低于5%");
  if (turnover >= 8) flags.push("换手率不低于8%");
  if (marketCapYi < 30) flags.push("总市值低于30亿元");

  if (flags.length) {
    return { tier: "仅行业属性", fit: "较低", basis: `所属行业有防守属性，但${flags.join("、")}` };
  }
  if (coreCodes.has(code)) {
    return { tier: "核心防守", fit: "较高", basis: "成熟大市值或基础设施龙头，且当日交易特征相对温和" };
  }
  return { tier: "一般防守", fit: "中等", basis: "行业需求相对稳定，但公司规模、盈利稳定性或股价波动弱于核心标的" };
}

function verify(row, quote) {
  if (!quote) return "未取得腾讯复核行情";
  const p1 = Number(row.trade);
  const c1 = Number(row.changepercent);
  const t1 = Number(row.turnoverratio);
  const m1 = Number(row.mktcap) / 10000;
  const checks = [
    Math.abs(p1 - quote.close) <= 0.011,
    Math.abs(c1 - quote.changePercent) <= 0.031,
    Math.abs(t1 - quote.turnover) <= 0.051,
    Number.isFinite(quote.totalMarketCapYi) && Math.abs(m1 - quote.totalMarketCapYi) / Math.max(m1, 1) <= 0.005,
  ];
  return checks.every(Boolean) ? "一致（收盘价/涨幅/换手/总市值）" : "存在差异，已保留新浪主源值";
}

const enriched = rows.map((row) => {
  const code = String(row.code).padStart(6, "0");
  const quote = secondary.get(code);
  const cls = classify(row, quote);
  const info = meta[row.defensive_category];
  const extraRisk = cls.tier === "仅行业属性" ? `；当日交易特征偏进攻，不宜仅因行业标签视为低波动标的` : "";
  const sourceUrl = `https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=100&sort=changepercent&asc=0&node=${row.source_node}&symbol=&_s_r_a=init`;
  const symbol = marketSymbol(code);
  return {
    数据日期: "2026-09-11",
    行情口径: "收盘",
    证券代码: code,
    行情代码: symbol.toUpperCase(),
    股票名称: row.name,
    交易所: exchange(code),
    防守类别: info.type,
    行业范围: row.defensive_category,
    防守层级: cls.tier,
    低波动防守适配: cls.fit,
    收盘价元: Number(Number(row.trade).toFixed(2)),
    涨跌额元: Number(Number(row.pricechange).toFixed(2)),
    涨跌幅百分比: Number(Number(row.changepercent).toFixed(2)),
    换手率百分比: Number(Number(row.turnoverratio).toFixed(2)),
    总市值亿元: Number((Number(row.mktcap) / 10000).toFixed(2)),
    分层依据: cls.basis,
    防守逻辑: info.reason,
    主要风险: `${info.risk}${extraRisk}`,
    交叉核验: verify(row, quote),
    行情时间: quote?.timestamp || row.ticktime || "",
    主行情来源: sourceUrl,
    复核来源: `https://qt.gtimg.cn/q=${symbol}`,
    筛选口径: "收盘涨幅>0；覆盖银行、公用事业、医药生物、食品饮料、通信服务、铁路公路和个护用品；剔除ST及退市标的；按规模与当日涨幅、换手分层",
  };
});

enriched.sort((a, b) =>
  tierOrder.get(a.防守层级) - tierOrder.get(b.防守层级) ||
  categoryOrder.get(a.行业范围) - categoryOrder.get(b.行业范围) ||
  b.涨跌幅百分比 - a.涨跌幅百分比 ||
  a.证券代码.localeCompare(b.证券代码)
);

const headers = Object.keys(enriched[0]);
function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}
const csvText = [
  headers.map(csvCell).join(","),
  ...enriched.map((row) => headers.map((h) => csvCell(row[h])).join(",")),
].join("\r\n") + "\r\n";

const workbook = await Workbook.fromCSV(csvText, { sheetName: "防守型上涨股" });
const sheet = workbook.worksheets.getItem("防守型上涨股");
const used = sheet.getUsedRange();
used.format.font = { name: "Arial", size: 10 };
sheet.getRange(`A1:W1`).format = {
  fill: "#1F4E78",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
};
sheet.freezePanes.freezeRows(1);
sheet.getRange(`K2:O${enriched.length + 1}`).format.horizontalAlignment = "right";
sheet.getRange(`A1:W${enriched.length + 1}`).format.verticalAlignment = "center";
sheet.getRange("A:A").format.columnWidth = 12;
sheet.getRange("B:B").format.columnWidth = 8;
sheet.getRange("C:J").format.columnWidth = 13;
sheet.getRange("K:O").format.columnWidth = 12;

const inspect = await workbook.inspect({
  kind: "table",
  range: `防守型上涨股!A1:W${enriched.length + 1}`,
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 23,
  maxChars: 10000,
});

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

const preview = await workbook.render({
  sheetName: "防守型上涨股",
  range: `A1:O18`,
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
await fs.writeFile(outputPath, `\uFEFF${csvText}`, "utf8");

const counts = enriched.reduce((acc, row) => {
  acc[row.防守层级] = (acc[row.防守层级] || 0) + 1;
  return acc;
}, {});
const verifyCounts = enriched.reduce((acc, row) => {
  acc[row.交叉核验] = (acc[row.交叉核验] || 0) + 1;
  return acc;
}, {});

console.log(JSON.stringify({
  outputPath,
  rowCount: enriched.length,
  counts,
  verifyCounts,
  firstRows: enriched.slice(0, 8).map((r) => ({ code: r.证券代码, name: r.股票名称, tier: r.防守层级, change: r.涨跌幅百分比 })),
  inspection: inspect.ndjson,
  errorScan: errors.ndjson,
}, null, 2));
