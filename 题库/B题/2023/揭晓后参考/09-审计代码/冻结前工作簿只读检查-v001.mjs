import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const blindRoot = "C:/Users/admin/OneDrive/Desktop/26国赛-单题盲解区/B-M9R2";
const reviewRoot = "C:/Users/admin/OneDrive/Desktop/26国赛/题库/B题/2023/揭晓后参考";

const workbooks = [
  { id: "Q01", relativePath: "result1.xlsx" },
  { id: "Q02", relativePath: "result2.xlsx" },
  { id: "Q03", relativePath: "工作记录/结果/Q03/第3问测线设计-v001.xlsx" },
  { id: "Q04", relativePath: "工作记录/结果/Q04/第4问测线设计-v001.xlsx" },
];

const output = {
  auditPurpose: "Freeze-time read-only workbook inventory; no recalculation or export",
  generatedAt: new Date().toISOString(),
  workbooks: [],
};

for (const item of workbooks) {
  const absolutePath = path.join(blindRoot, item.relativePath);
  const blob = await FileBlob.load(absolutePath);
  const workbook = await SpreadsheetFile.importXlsx(blob);
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table,formula",
    include: "id,name,range,values,formulas",
    maxChars: 50000,
    tableMaxRows: 12,
    tableMaxCols: 20,
    tableMaxCellChars: 120,
    options: { maxResults: 500 },
  });
  const sheets = [];
  for (const sheet of workbook.worksheets.items) {
    const used = sheet.getUsedRange();
    sheets.push({
      name: sheet.name,
      usedRange: used?.address ?? null,
      rowCount: used?.rowCount ?? 0,
      columnCount: used?.columnCount ?? 0,
    });
  }
  output.workbooks.push({
    id: item.id,
    relativePath: item.relativePath,
    sheets,
    inspectNdjson: summary.ndjson,
  });
}

const outputPath = path.join(reviewRoot, "10-审计结果", "冻结前工作簿只读检查-v001.json");
await fs.writeFile(outputPath, JSON.stringify(output, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ outputPath, workbookCount: output.workbooks.length, sheets: output.workbooks.map((w) => ({ id: w.id, sheets: w.sheets })) }, null, 2));
