// SPEED PROBE — paste as a SECOND Office Script named "Speed probe" and
// run it on the model. It reads NO cell values: only the size of each
// sheet's used range, which Excel already knows.
//
//   finishes instantly  -> the workbook is fine, my reads are the problem
//   takes 30s+          -> opening/recalculating the workbook is the cost,
//                          and no amount of read-trimming will help
//
// It also prints how big Excel thinks each sheet is. A sheet reporting
// thousands of rows or hundreds of columns past its real data is carrying
// stray formatting, and that alone can make every read enormous.
function main(workbook: ExcelScript.Workbook): string {
  const out: string[] = [];
  const sheets: ExcelScript.Worksheet[] = workbook.getWorksheets();
  for (let i: number = 0; i < sheets.length; i++) {
    const ur: ExcelScript.Range | undefined = sheets[i].getUsedRange();
    out.push(sheets[i].getName() + ": " + (ur
      ? (ur.getRowCount() + " rows x " + ur.getColumnCount() + " cols")
      : "empty"));
  }
  const res: string = out.join("  |  ");
  console.log(res);
  return res;
}
