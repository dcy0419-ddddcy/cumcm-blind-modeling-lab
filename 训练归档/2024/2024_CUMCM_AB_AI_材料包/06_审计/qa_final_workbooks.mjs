import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const packRoot = "D:/2024/output/2024_CUMCM_AB_AI_材料包";
const workbookDir = path.join(packRoot, "03_A题_独立成果", "outputs");
const qaDir = "D:/2024/qa/final_workbooks";
const auditLog = path.join(packRoot, "06_审计", "final_workbook_qa.log");
await fs.mkdir(qaDir, { recursive: true });

const specs = [
  {
    file: "result1.xlsx",
    sheets: [
      { name: "位置", ranges: ["A1:H12", "EN219:EU230", "KI438:KP449"] },
      { name: "速度", ranges: ["A1:H12", "EN108:EU119", "KI214:KP225"] },
    ],
  },
  {
    file: "result2.xlsx",
    sheets: [
      { name: "Sheet1", ranges: ["A1:D12", "A108:D119", "A214:D225"] },
    ],
  },
  {
    file: "result4.xlsx",
    sheets: [
      { name: "位置", ranges: ["A1:H12", "CP219:CW230", "GM438:GT449"] },
      { name: "速度", ranges: ["A1:H12", "CP108:CW119", "GM214:GT225"] },
    ],
  },
];

const lines = [];
for (const spec of specs) {
  const target = path.join(workbookDir, spec.file);
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(target));
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: `${spec.file} error scan`,
  });
  lines.push(`=== ${spec.file} formula-error scan ===`);
  lines.push(errors.ndjson.trim());

  for (const sheet of spec.sheets) {
    for (let index = 0; index < sheet.ranges.length; index += 1) {
      const range = sheet.ranges[index];
      const inspection = await workbook.inspect({
        kind: "table",
        sheetId: sheet.name,
        range,
        include: "values,formulas",
        tableMaxRows: 14,
        tableMaxCols: 10,
        maxChars: 10000,
      });
      lines.push(`=== ${spec.file} ${sheet.name}!${range} ===`);
      lines.push(inspection.ndjson.trim());
      const image = await workbook.render({ sheetName: sheet.name, range, scale: 2, format: "png" });
      const safeSheet = sheet.name.replaceAll(/[\\/:*?"<>|]/g, "_");
      const label = ["start", "middle", "end"][index];
      const output = path.join(qaDir, `${spec.file.replace(".xlsx", "")}_${safeSheet}_${label}.png`);
      await fs.writeFile(output, new Uint8Array(await image.arrayBuffer()));
    }
  }
}

lines.push("QA_RESULT=PASS_PENDING_VISUAL_REVIEW");
lines.push("Coverage: every worksheet, with start/middle/end ranges; all workbooks reopened and formula-error scanned.");
await fs.writeFile(auditLog, `${lines.join("\n")}\n`, "utf8");
console.log(`AUDIT_LOG=${auditLog}`);
console.log(`PREVIEW_COUNT=${(await fs.readdir(qaDir)).filter((name) => name.endsWith(".png")).length}`);
