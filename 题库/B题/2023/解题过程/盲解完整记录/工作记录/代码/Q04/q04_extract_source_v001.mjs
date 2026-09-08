import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "./.artifact-runtime/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..", "..", "..");
const sourcePath = path.join(root, "附件", "附件03.xlsx");
const outputPath = path.join(root, "工作记录", "诊断结果", "Q04", "q04_source_grid_v001.json");
const previewPath = path.join(root, "工作记录", "诊断结果", "Q04", "附件03-表头与数据预览-v001.png");
const inspectPath = path.join(root, "工作记录", "诊断结果", "Q04", "附件03-artifact-inspect-v001.ndjson");

const bytes = await fs.readFile(sourcePath);
const hash = crypto.createHash("sha256").update(bytes).digest("hex");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const sheet = workbook.worksheets.getItemAt(0);
const range = sheet.getRange("A1:GU253");
const values = range.values;
const formulas = range.formulas;
const x = values[1].slice(2);
const y = values.slice(2).map((row) => row[1]);
const depths = values.slice(2).map((row) => row.slice(2));
const allFinite = [...x, ...y, ...depths.flat()].every((value) => typeof value === "number" && Number.isFinite(value));
const formulaCount = formulas.flat().filter((value) => typeof value === "string" && value.length > 0).length;
const inspection = await workbook.inspect({
  kind: "workbook,sheet,region,formula",
  sheetId: sheet.name,
  range: "A1:GU253",
  maxChars: 16000,
  tableMaxRows: 8,
  tableMaxCols: 10,
  options: { maxResults: 200 },
});
const preview = await workbook.render({ sheetName: sheet.name, range: "A1:L12", scale: 1.5, format: "png" });
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
await fs.writeFile(inspectPath, inspection.ndjson ?? JSON.stringify(inspection), "utf8");
const report = {
  source_relative_path: "附件/附件03.xlsx",
  source_sha256: hash,
  sheet_names: workbook.worksheets.items.map((item) => item.name),
  declared_range: "A1:GU253",
  x_count: x.length,
  y_count: y.length,
  depth_shape: [depths.length, depths[0].length],
  x_nmi: x,
  y_nmi: y,
  depth_m: depths,
  formula_count: formulaCount,
  all_coordinates_and_depths_finite_numeric: allFinite,
};
await fs.writeFile(outputPath, JSON.stringify(report), "utf8");
console.log(JSON.stringify({
  source_sha256: hash, sheets: report.sheet_names, x_count: x.length, y_count: y.length,
  depth_shape: report.depth_shape, formula_count: formulaCount, all_finite: allFinite,
}, null, 2));
if (!(x.length === 201 && y.length === 251 && depths.every((row) => row.length === 201) && allFinite && formulaCount === 0)) {
  throw new Error("Attachment 03 structure check failed");
}
