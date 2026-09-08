/** 问题 2：先渲染附件 02，再按模板生成、导出、重载和核验正式 Excel。 */

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  FileBlob,
  SpreadsheetFile,
} from "./.artifact-runtime/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";


const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..", "..", "..");
const sourcePath = path.join(root, "附件", "附件02.xlsx");
const modelPath = path.join(root, "工作记录", "诊断结果", "Q02", "q02_model_output_v001.json");
const outputDir = path.join(root, "工作记录", "结果", "Q02");
const versionedPath = path.join(outputDir, "result2-v001.xlsx");
const submissionPath = path.join(root, "result2.xlsx");
const diagnosticDir = path.join(root, "工作记录", "诊断结果", "Q02");
const sourcePreviewPath = path.join(diagnosticDir, "附件02-编辑前预览-v001.png");
const outputPreviewPath = path.join(diagnosticDir, "result2-生成后预览-v001.png");
const auditPath = path.join(diagnosticDir, "q02_excel_audit_v001.json");
const inspectPath = path.join(outputDir, "result2-v001.xlsx.inspect.ndjson");


async function sha256(filePath) {
  const data = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}


function normalize(value) {
  return value === undefined ? null : value;
}


async function importWorkbook(filePath) {
  return SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
}


function readState(workbook) {
  const sheet = workbook.worksheets.getItemAt(0);
  const range = sheet.getRange("A1:J10");
  return {
    sheetName: sheet.name,
    values: range.values.map((row) => row.map(normalize)),
    formulas: range.formulas.map((row) => row.map((value) => value ?? "")),
  };
}


const model = JSON.parse(await fs.readFile(modelPath, "utf8"));
const table = model.formal_table;
if (table.rows_beta_deg.length !== 8 || table.columns_distance_nmi.length !== 8) {
  throw new Error("问题 2 正式结果必须是 8×8 矩阵");
}

await fs.mkdir(diagnosticDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
const sourceHashBefore = await sha256(sourcePath);
if (sourceHashBefore !== model.template.sha256) {
  throw new Error("附件 02 当前哈希与模型运行时记录不一致");
}

const workbook = await importWorkbook(sourcePath);
const sheet = workbook.worksheets.getItemAt(0);
const before = readState(workbook);
const sourcePreview = await workbook.render({
  sheetName: sheet.name,
  range: "A1:J10",
  scale: 2,
  format: "png",
});
await fs.writeFile(sourcePreviewPath, new Uint8Array(await sourcePreview.arrayBuffer()));

sheet.getRange("C3:J10").values = table.coverage_width_m_2dp;
sheet.getRange("C3:J10").format.numberFormat = "0.00";
workbook.recalculate();

const outputPreview = await workbook.render({
  sheetName: sheet.name,
  range: "A1:J10",
  scale: 2,
  format: "png",
});
await fs.writeFile(outputPreviewPath, new Uint8Array(await outputPreview.arrayBuffer()));

const inspection = await workbook.inspect({
  kind: "region",
  sheetId: sheet.name,
  range: "A1:J10",
  maxChars: 12000,
});
const formulaInspection = await workbook.inspect({
  kind: "formula",
  sheetId: sheet.name,
  range: "A1:J10",
  maxChars: 4000,
  options: { maxResults: 200 },
});
await fs.writeFile(
  inspectPath,
  `${inspection.ndjson ?? JSON.stringify(inspection)}\n${formulaInspection.ndjson ?? JSON.stringify(formulaInspection)}\n`,
  "utf8",
);

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(versionedPath);
await fs.copyFile(versionedPath, submissionPath);

const reloaded = await importWorkbook(versionedPath);
const reloadedSheet = reloaded.worksheets.getItemAt(0);
const after = readState(reloaded);
const outputStyleInspection = await reloaded.inspect({
  kind: "computedStyle",
  sheetId: reloadedSheet.name,
  range: "C3:J10",
  maxChars: 10000,
});
const outputStyleText = outputStyleInspection.ndjson ?? JSON.stringify(outputStyleInspection);

const sourceHashAfter = await sha256(sourcePath);
const versionedHash = await sha256(versionedPath);
const submissionHash = await sha256(submissionPath);
const axesCorrect =
  JSON.stringify(after.values[1].slice(2)) === JSON.stringify(table.columns_distance_nmi) &&
  JSON.stringify(after.values.slice(2).map((row) => row[1])) === JSON.stringify(table.rows_beta_deg);
const outputValues = after.values.slice(2).map((row) => row.slice(2));
const valuesCorrect = JSON.stringify(outputValues) === JSON.stringify(table.coverage_width_m_2dp);
const numericFinite = outputValues.flat().every((value) => typeof value === "number" && Number.isFinite(value) && value > 0);
const formulasAbsent = after.formulas.flat().every((value) => value === "");
const formulaErrorPattern = /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/;
const formulaErrorCells = [];
after.values.forEach((row, rowIndex) => {
  row.forEach((value, columnIndex) => {
    const formula = after.formulas[rowIndex][columnIndex];
    if (formulaErrorPattern.test(String(value ?? "")) || formulaErrorPattern.test(String(formula ?? ""))) {
      formulaErrorCells.push({ row: rowIndex + 1, column: columnIndex + 1, value, formula });
    }
  });
});
const checks = {
  source_template_unchanged: sourceHashBefore === sourceHashAfter,
  output_files_byte_identical: versionedHash === submissionHash,
  eight_by_eight_values_present: outputValues.length === 8 && outputValues.every((row) => row.length === 8),
  axes_match_template_and_model: axesCorrect,
  values_match_formal_table: valuesCorrect,
  result_cells_numeric_finite_positive: numericFinite,
  formulas_absent: formulasAbsent,
  formula_error_count_zero: formulaErrorCells.length === 0,
  number_format_two_decimals: outputStyleText.includes("0.00"),
};
const audit = {
  schema_version: "q02-excel-audit-v001",
  source: {
    path: "附件/附件02.xlsx",
    sha256_before: sourceHashBefore,
    sha256_after: sourceHashAfter,
  },
  outputs: {
    versioned: { path: "工作记录/结果/Q02/result2-v001.xlsx", sha256: versionedHash },
    submission: { path: "result2.xlsx", sha256: submissionHash },
  },
  template_before: before,
  readback: after,
  computed_style_inspection: outputStyleText,
  formula_error_cells: formulaErrorCells,
  checks,
  all_passed: Object.values(checks).every(Boolean),
};
await fs.writeFile(auditPath, `${JSON.stringify(audit, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ all_passed: audit.all_passed, checks, outputs: audit.outputs }, null, 2));
if (!audit.all_passed) {
  throw new Error("问题 2 Excel 读回核验未全部通过");
}
