import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("C:\\Users\\cg\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright");

const WORKSPACE = process.cwd();
const OUTPUT_ROOT = path.join(WORKSPACE, "output", "pdf", "CPA历年真题_2015-2025");
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const DONGAO_INDEX = "https://www.dongao.com/ziliao/zckjs_61/";

const subjects = [
  "会计",
  "审计",
  "税法",
  "经济法",
  "财务成本管理",
  "公司战略与风险管理",
];

const subjectAliases = {
  会计: ["会计"],
  审计: ["审计"],
  税法: ["税法"],
  经济法: ["经济法"],
  财务成本管理: ["财管", "财务成本管理"],
  公司战略与风险管理: ["战略", "公司战略与风险管理"],
};

const dongaoLegacyCodes = {
  会计: "kuaiji",
  审计: "shenji",
  税法: "shuifa",
  经济法: "jingjifa",
  财务成本管理: "caiguan",
  公司战略与风险管理: "zhanlue",
};

const fixedPages = {
  2020: {
    会计: "https://www.chinalawyer.co/book/cpa_exam_qa/kuaiji_2020_qa/",
    审计: "https://ecfiles.dongao.com/ec/materials/content/files/20210429/1619690092739066665.pdf",
    税法: "https://www.chinalawyer.co/book/cpa_exam_qa/cpataxlaw_2020_qa/",
    经济法: "https://www.chinalawyer.co/book/cpa_exam_qa/cpalaw_2020_qa/",
    财务成本管理: "https://www.educity.cn/cpa/2125947.html",
    公司战略与风险管理: "https://www.chinalawyer.co/book/cpa_exam_qa/cparisk_2020_qa/",
  },
  2021: {
    会计: "https://www.chinalawyer.co/book/cpa_exam_qa/kuaiji_2021_qa/",
    审计: "https://www.chinalawyer.co/book/cpa_exam_qa/audit_2021_qa/",
    税法: "https://www.chinalawyer.co/book/cpa_exam_qa/cpataxlaw_2021_qa/",
    经济法: "https://www.chinalawyer.co/book/cpa_exam_qa/cpalaw_2021_qa/",
    财务成本管理: "https://www.chinalawyer.co/book/cpa_exam_qa/costmgr_2021_qa/",
    公司战略与风险管理: "https://www.chinalawyer.co/book/cpa_exam_qa/cparisk_2021_qa/",
  },
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchText(url, options = {}, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
          ...(options.headers || {}),
        },
        signal: AbortSignal.timeout(45_000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status} ${url}`);
      return await response.text();
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await sleep(attempt * 1_000);
    }
  }
  throw lastError;
}

function stripTags(html) {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&gt;|&#62;/gi, ">")
    .replace(/&lt;|&#60;/gi, "<")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeUrl(url, base) {
  return new URL(url.replace(/^http:/i, "https:"), base).href;
}

function subjectForTitle(title) {
  for (const subject of subjects) {
    if (subjectAliases[subject].some((alias) => title.includes(alias))) return subject;
  }
  return null;
}

function legacyPdfEntries() {
  const entries = [];
  for (let year = 2015; year <= 2019; year += 1) {
    for (const subject of subjects) {
      entries.push({
        year,
        subject,
        title: `${year}年CPA《${subject}》试题及答案`,
        sourceUrl: `https://att.dongao.com/zhukuai/${year}cpa${dongaoLegacyCodes[subject]}zhenti.pdf`,
        indexUrl: "https://www.dongao.com/zckjs/xtzs/",
        sourceName: "东奥会计在线",
        sourceKind: "公开历年真题PDF（部分题目按后续教材重新表述）",
        mode: "download",
      });
    }
  }
  return entries;
}

function fixedPageEntries() {
  const entries = [];
  for (const [yearText, mapping] of Object.entries(fixedPages)) {
    const year = Number(yearText);
    for (const subject of subjects) {
      const sourceUrl = mapping[subject];
      const isDirectPdf = /\.pdf(?:\?.*)?$/i.test(sourceUrl);
      const isEducity = sourceUrl.includes("educity.cn");
      entries.push({
        year,
        subject,
        title: `${year}年CPA《${subject}》试题及参考答案`,
        sourceUrl,
        sourceName: isDirectPdf ? "东奥会计在线" : isEducity ? "希赛网" : "chinalawyer.co 公开题库",
        sourceKind: isDirectPdf ? "公开试题及答案PDF" : "公开整理版网页（本地打印为PDF）",
        mode: isDirectPdf ? "download" : "print",
        forceRefresh: true,
      });
    }
  }
  return entries;
}

async function discover2022to2025() {
  const html = await fetchText(DONGAO_INDEX);
  const entries = [];
  const itemPattern = /<p[^>]*>\s*<a[^>]+data-href="[^"]+"[^>]*>([^<]+)<\/a><\/p>\s*<a class="r_download_btn" contentid="(\d+)" categoryid="(\d+)">/g;
  for (const match of html.matchAll(itemPattern)) {
    const title = stripTags(match[1]);
    const yearMatch = title.match(/20(22|23|24|25)/);
    if (!yearMatch || !/(?:试题|考题).*(?:答案|解析)/.test(title)) continue;
    const subject = subjectForTitle(title);
    if (!subject) continue;
    const year = Number(`20${yearMatch[1]}`);
    const directUrl = (
      await fetchText(
        `https://www.dongao.com/ziliao/one?contentId=${match[2]}&categoryId=${match[3]}`,
        { headers: { referer: DONGAO_INDEX } },
      )
    ).trim();
    if (!/^https:\/\/.+\.pdf(?:\?.*)?$/i.test(directUrl)) {
      throw new Error(`Unexpected Dongao download URL for ${title}: ${directUrl}`);
    }
    entries.push({
      year,
      subject,
      title,
      sourceUrl: directUrl,
      indexUrl: DONGAO_INDEX,
      sourceName: "东奥会计在线",
      sourceKind: year === 2025 ? "考生回忆版公开PDF" : "公开试题及答案解析PDF",
      mode: "download",
    });
  }
  return entries;
}

function assertCoverage(entries) {
  const keys = new Set(entries.map((entry) => `${entry.year}-${entry.subject}`));
  const missing = [];
  for (let year = 2015; year <= 2025; year += 1) {
    for (const subject of subjects) {
      if (!keys.has(`${year}-${subject}`)) missing.push(`${year}-${subject}`);
    }
  }
  if (missing.length) throw new Error(`Missing coverage: ${missing.join(", ")}`);
  if (keys.size !== 66) throw new Error(`Expected 66 unique year-subject pairs, got ${keys.size}`);
}

function outputFile(entry) {
  return path.join(OUTPUT_ROOT, String(entry.year), `${entry.year}_CPA_${entry.subject}_真题及参考答案.pdf`);
}

async function downloadPdf(entry) {
  const response = await fetch(entry.sourceUrl, {
    headers: {
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
      referer: entry.indexUrl || entry.sourceUrl,
    },
    signal: AbortSignal.timeout(90_000),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status} ${entry.sourceUrl}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.subarray(0, 4).toString() !== "%PDF") {
    throw new Error(`Downloaded content is not a PDF: ${entry.title}`);
  }
  await fs.writeFile(outputFile(entry), bytes);
}

async function printArticle(page, entry) {
  console.log(`TRY  ${entry.year} ${entry.subject} <- ${entry.sourceUrl}`);
  const rawHtml = await fetchText(entry.sourceUrl);
  const sanitizedHtml = rawHtml
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, "")
    .replace(/<link\b[^>]*rel=["']?(?:preload|prefetch)[^>]*>/gi, "");
  const htmlWithBase = sanitizedHtml.replace(/<head([^>]*)>/i, `<head$1><base href="${entry.sourceUrl}">`);
  await page.setContent(htmlWithBase, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForSelector("#content, .ecv2_detail_text.detail_content, .jxbox", { state: "attached", timeout: 30_000 });
  await page.evaluate(({ sourceUrl, fallbackTitle, sourceName }) => {
    const main = document.querySelector("#content .container") || document.querySelector(".ecv2_detail_text.detail_content") || document.querySelector(".jxbox") || document.querySelector("#content");
    if (!main) throw new Error("Article body not found");
    const clone = main.cloneNode(true);
    clone.querySelectorAll("script, noscript, iframe, video, audio, form, button, input, .upAndown, .share, .news-precisionMarketing-mod, .precisionMarketing-CommonPop, .jx").forEach((node) => node.remove());
    clone.querySelectorAll("img").forEach((img) => {
      const candidate = img.getAttribute("src") || img.getAttribute("data-original") || img.getAttribute("data-src");
      if (!candidate) {
        img.remove();
        return;
      }
      try {
        img.setAttribute("src", new URL(candidate, sourceUrl).href);
      } catch {
        img.remove();
      }
      img.removeAttribute("width");
      img.removeAttribute("height");
      img.removeAttribute("style");
    });
    clone.querySelectorAll("a[href]").forEach((anchor) => {
      try {
        anchor.setAttribute("href", new URL(anchor.getAttribute("href"), sourceUrl).href);
      } catch {
        anchor.removeAttribute("href");
      }
    });
    const title = document.querySelector("#content > h1")?.textContent?.trim() || document.querySelector("h1")?.textContent?.trim() || fallbackTitle;
    document.head.innerHTML = `
      <meta charset="utf-8">
      <title>${title.replace(/[<&]/g, "")}</title>
      <style>
        @page { size: A4; margin: 16mm 14mm 18mm; }
        * { box-sizing: border-box; }
        body { margin: 0; color: #111; font: 14px/1.65 "Microsoft YaHei", "SimSun", sans-serif; }
        h1 { margin: 0 0 8px; font-size: 22px; line-height: 1.35; text-align: center; }
        .source { margin: 0 0 18px; padding-bottom: 10px; color: #555; font-size: 10px; border-bottom: 1px solid #bbb; word-break: break-all; }
        p { margin: 7px 0; orphans: 3; widows: 3; }
        table { width: 100% !important; max-width: 100%; border-collapse: collapse; page-break-inside: auto; }
        tr { page-break-inside: avoid; page-break-after: auto; }
        td, th { padding: 5px 6px !important; border: 1px solid #888 !important; vertical-align: top; }
        img { display: block; max-width: 100%; height: auto; margin: 8px auto; page-break-inside: avoid; }
        a { color: inherit; text-decoration: none; }
      </style>`;
    document.body.innerHTML = "";
    const heading = document.createElement("h1");
    heading.textContent = title;
    const source = document.createElement("p");
    source.className = "source";
    source.textContent = `来源：${sourceName}｜原始页面：${sourceUrl}｜本地整理日期：2026-09-13`;
    document.body.append(heading, source, clone);
  }, { sourceUrl: entry.sourceUrl, fallbackTitle: entry.title, sourceName: entry.sourceName });
  await page.evaluate(async () => {
    await document.fonts.ready;
    const images = Array.from(document.images);
    await Promise.all(images.map((img) => img.complete ? null : new Promise((resolve) => {
      img.addEventListener("load", resolve, { once: true });
      img.addEventListener("error", resolve, { once: true });
      setTimeout(resolve, 5_000);
    })));
  });
  await page.pdf({
    path: outputFile(entry),
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: '<div style="width:100%;font-size:8px;color:#666;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: { top: "16mm", right: "14mm", bottom: "18mm", left: "14mm" },
  });
}

async function sha256(filePath) {
  const bytes = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function main() {
  await fs.mkdir(OUTPUT_ROOT, { recursive: true });
  for (let year = 2015; year <= 2025; year += 1) {
    await fs.mkdir(path.join(OUTPUT_ROOT, String(year)), { recursive: true });
  }

  const discovered = [
    ...legacyPdfEntries(),
    ...fixedPageEntries(),
    ...(await discover2022to2025()),
  ];
  const unique = new Map();
  for (const entry of discovered) unique.set(`${entry.year}-${entry.subject}`, entry);
  const entries = [...unique.values()].sort((a, b) => a.year - b.year || subjects.indexOf(a.subject) - subjects.indexOf(b.subject));
  assertCoverage(entries);

  const browser = await chromium.launch({
    executablePath: EDGE,
    headless: true,
    args: ["--no-first-run", "--disable-features=msEdgeFirstRunExperience", "--disable-extensions"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultNavigationTimeout(60_000);

  try {
    for (const entry of entries) {
      const target = outputFile(entry);
      let complete = false;
      try {
        const current = await fs.readFile(target);
        complete = current.subarray(0, 4).toString() === "%PDF" && current.length > 10_000;
      } catch {}
      if (complete && entry.mode === "download" && !entry.forceRefresh) {
        console.log(`SKIP ${entry.year} ${entry.subject}`);
        continue;
      }
      if (entry.mode === "download") await downloadPdf(entry);
      else await printArticle(page, entry);
      console.log(`OK   ${entry.year} ${entry.subject}`);
    }
  } finally {
    await browser.close();
  }

  const rows = [];
  const sums = [];
  for (const entry of entries) {
    const filePath = outputFile(entry);
    const stat = await fs.stat(filePath);
    const hash = await sha256(filePath);
    const relative = path.relative(OUTPUT_ROOT, filePath).replaceAll("\\", "/");
    rows.push(`| ${entry.year} | ${entry.subject} | [${relative}](${encodeURI(relative)}) | ${entry.sourceKind} | [来源](${entry.indexUrl || entry.sourceUrl}) | ${(stat.size / 1024 / 1024).toFixed(2)} MB |`);
    sums.push(`${hash}  ${relative}`);
  }

  const readme = `# CPA 历年真题（2015—2025）\n\n` +
    `本目录按中国注册会计师全国统一考试专业阶段六科整理，共 11 年 × 6 科 = 66 份。\n\n` +
    `## 来源口径\n\n` +
    `- 2015—2019：东奥会计在线公开的历年真题 PDF；文件中部分题目注明按后续教材重新表述。\n` +
    `- 2020—2021：chinalawyer.co 公开题库为主；2020 年审计采用东奥公开 PDF，2020 年财管采用希赛网公开页面。网页资料为便于离线使用，本地打印成 PDF。\n` +
    `- 2022—2025：东奥会计在线公开的试题及答案解析 PDF；2025 年明确为考生回忆版。\n` +
    `- 中注协说明考试启用后的完整试题、参考答案与评分标准通常按工作秘密管理，因此这些资料不应当称为“中注协官方完整原卷”。来源入口可见中注协备考助手的“往年部分真题”。\n` +
    `- 税法、经济法、会计准则等会随年度变化；旧题主要用于题型、命题方式和迁移训练，作答规则以目标考季大纲和现行法规为准。\n\n` +
    `## 文件清单\n\n` +
    `| 年份 | 科目 | 文件 | 版本 | 公开来源 | 大小 |\n|---:|---|---|---|---|---:|\n` +
    rows.join("\n") + "\n";
  await fs.writeFile(path.join(OUTPUT_ROOT, "README.md"), readme, "utf8");
  await fs.writeFile(path.join(OUTPUT_ROOT, "SHA256SUMS.txt"), sums.join("\n") + "\n", "utf8");
  console.log(`DONE ${entries.length} PDFs -> ${OUTPUT_ROOT}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
