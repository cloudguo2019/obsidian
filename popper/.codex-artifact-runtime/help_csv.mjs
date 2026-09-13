import { Workbook } from "@oai/artifact-tool";

const workbook = Workbook.create();
workbook.worksheets.add("Sheet1");
const result = workbook.help("export csv", {
  search: "CSV|csv|exportCsv|toCSV",
  include: "index,examples,notes",
  maxChars: 6000,
});
console.log(result.ndjson);
