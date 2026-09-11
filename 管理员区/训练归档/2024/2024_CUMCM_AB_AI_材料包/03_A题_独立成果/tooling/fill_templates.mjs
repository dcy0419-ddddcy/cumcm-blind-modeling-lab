import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/2024/work_independent/A";
const sourceDir = "D:/2024/附件_A题/附件";
const computedDir = path.join(root, "computed");
const outputDir = path.join(root, "outputs");
const previewDir = path.join(root, "tmp", "filled_previews");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

function round6(value) {
  const rounded = Math.round(Number(value) * 1e6) / 1e6;
  return Object.is(rounded, -0) ? 0 : rounded;
}

async function readNumericCsv(filename) {
  const csvText = await fs.readFile(path.join(computedDir, filename), "utf8");
  const csvWorkbook = await Workbook.fromCSV(csvText, { sheetName: "Data" });
  const values = csvWorkbook.worksheets.getItem("Data").getUsedRange().values;
  return values.slice(1).map((row) => row.map((cell) => Number(cell)));
}

async function importTemplate(filename) {
  return SpreadsheetFile.importXlsx(await FileBlob.load(path.join(sourceDir, filename)));
}

async function exportAndVerify(workbook, filename, previewSpecs) {
  const target = path.join(outputDir, filename);
  const blob = await SpreadsheetFile.exportXlsx(workbook);
  await blob.save(target);

  const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(target));
  const errorScan = await reopened.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: `${filename} formula error scan`,
  });
  console.log(`--- ${filename} error scan ---`);
  console.log(errorScan.ndjson);

  for (const spec of previewSpecs) {
    const inspection = await reopened.inspect({
      kind: "table",
      sheetId: spec.sheet,
      range: spec.range,
      include: "values,formulas",
      tableMaxRows: 14,
      tableMaxCols: 10,
      maxChars: 8000,
    });
    console.log(`--- ${filename} ${spec.sheet}!${spec.range} ---`);
    console.log(inspection.ndjson);
    const preview = await reopened.render({
      sheetName: spec.sheet,
      range: spec.range,
      scale: 2,
      format: "png",
    });
    const safeSheet = spec.sheet.replaceAll(/[\\/:*?"<>|]/g, "_");
    await fs.writeFile(
      path.join(previewDir, `${filename.replace(".xlsx", "")}_${safeSheet}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}

const q1Rows = await readNumericCsv("question1_all_handles.csv");
if (q1Rows.length !== 301 * 224) throw new Error(`unexpected Q1 row count: ${q1Rows.length}`);
const q1Position = Array.from({ length: 448 }, () => Array(301).fill(null));
const q1Speed = Array.from({ length: 224 }, () => Array(301).fill(null));
for (const [time, handle, x, y, speed] of q1Rows) {
  q1Position[2 * handle][time] = round6(x);
  q1Position[2 * handle + 1][time] = round6(y);
  q1Speed[handle][time] = round6(speed);
}
const q1Workbook = await importTemplate("result1.xlsx");
const q1PosSheet = q1Workbook.worksheets.getItem("位置");
const q1SpeedSheet = q1Workbook.worksheets.getItem("速度");
const q1PosRange = q1PosSheet.getRangeByIndexes(1, 1, 448, 301);
const q1SpeedRange = q1SpeedSheet.getRangeByIndexes(1, 1, 224, 301);
q1PosRange.values = q1Position;
q1SpeedRange.values = q1Speed;
q1PosRange.setNumberFormat("0.000000");
q1SpeedRange.setNumberFormat("0.000000");
await exportAndVerify(q1Workbook, "result1.xlsx", [
  { sheet: "位置", range: "A1:H12" },
  { sheet: "速度", range: "A1:H12" },
]);

const q2Rows = await readNumericCsv("question2_terminal.csv");
if (q2Rows.length !== 224) throw new Error(`unexpected Q2 row count: ${q2Rows.length}`);
const q2Values = q2Rows.map((row) => row.slice(1).map(round6));
const q2Workbook = await importTemplate("result2.xlsx");
const q2Sheet = q2Workbook.worksheets.getItem("Sheet1");
const q2Range = q2Sheet.getRangeByIndexes(1, 1, 224, 3);
q2Range.values = q2Values;
q2Range.setNumberFormat("0.000000");
await exportAndVerify(q2Workbook, "result2.xlsx", [
  { sheet: "Sheet1", range: "A1:D12" },
  { sheet: "Sheet1", range: "A217:D225" },
]);

const q4Rows = await readNumericCsv("question4_all_handles.csv");
if (q4Rows.length !== 201 * 224) throw new Error(`unexpected Q4 row count: ${q4Rows.length}`);
const q4Position = Array.from({ length: 448 }, () => Array(201).fill(null));
const q4Speed = Array.from({ length: 224 }, () => Array(201).fill(null));
for (const [time, handle, x, y, speed] of q4Rows) {
  const col = time + 100;
  q4Position[2 * handle][col] = round6(x);
  q4Position[2 * handle + 1][col] = round6(y);
  q4Speed[handle][col] = round6(speed);
}
const q4Workbook = await importTemplate("result4.xlsx");
const q4PosSheet = q4Workbook.worksheets.getItem("位置");
const q4SpeedSheet = q4Workbook.worksheets.getItem("速度");
const q4PosRange = q4PosSheet.getRangeByIndexes(1, 1, 448, 201);
const q4SpeedRange = q4SpeedSheet.getRangeByIndexes(1, 1, 224, 201);
q4PosRange.values = q4Position;
q4SpeedRange.values = q4Speed;
q4PosRange.setNumberFormat("0.000000");
q4SpeedRange.setNumberFormat("0.000000");
await exportAndVerify(q4Workbook, "result4.xlsx", [
  { sheet: "位置", range: "A1:H12" },
  { sheet: "速度", range: "A1:H12" },
]);

console.log(`saved workbooks to ${outputDir}`);
