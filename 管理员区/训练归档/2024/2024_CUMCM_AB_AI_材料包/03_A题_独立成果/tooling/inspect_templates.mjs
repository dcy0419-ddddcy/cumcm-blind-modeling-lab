import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourceDir = "D:/2024/附件_A题/附件";
const previewDir = "D:/2024/work_independent/A/tmp/template_previews";
await fs.mkdir(previewDir, { recursive: true });

for (const filename of ["result1.xlsx", "result2.xlsx", "result4.xlsx"]) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(sourceDir, filename)));
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table,region",
    maxChars: 12000,
    tableMaxRows: 12,
    tableMaxCols: 10,
    tableMaxCellChars: 100,
  });
  console.log(`--- ${filename} ---`);
  console.log(summary.ndjson);
  const sheetInfo = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 });
  console.log(sheetInfo.ndjson);
  const firstSheet = workbook.worksheets.getItemAt(0);
  const preview = await workbook.render({
    sheetName: firstSheet.name,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(previewDir, filename.replace(".xlsx", ".png")),
    new Uint8Array(await preview.arrayBuffer()),
  );
}
