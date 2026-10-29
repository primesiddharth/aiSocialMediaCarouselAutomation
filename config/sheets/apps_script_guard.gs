/**
 * ZERO-TOUCH SOCIAL AUTOMATION - GOOGLE SHEETS SETUP & APPROVAL GUARD
 * Paste into Extensions -> Apps Script in your Google Sheet and click Run -> setupSheetSchema()
 */

const TAB_NAME = "Content_Pipeline";

function setupSheetSchema() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(TAB_NAME);
  if (!sheet) {
    sheet = ss.getActiveSheet();
    sheet.setName(TAB_NAME);
  }

  // 1. Freeze Header Row & Style Headers
  sheet.setFrozenRows(1);
  const headerRange = sheet.getRange("A1:M1");
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#111827");
  headerRange.setFontColor("#FFFFFF");

  // 2. Enforce "Include Image?" Dropdown (Column B, Rows 2 to 500) -> Exact PDF Spec: Yes / No
  const imageRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Yes", "No"], true)
    .setAllowInvalid(false)
    .setHelpText("Select 'Yes' to generate a FLUX.1 image, or 'No' for text-only (excludes Instagram).")
    .build();
  sheet.getRange("B2:B500").setDataValidation(imageRule);

  // 3. Enforce "Status" Dropdown (Column D, Rows 2 to 500)
  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Pending", "Processing", "Draft", "Approved", "Publishing", "Published", "Error"], true)
    .setAllowInvalid(false)
    .setHelpText("Workflow state: AI sets 'Draft'. Change to 'Approved' to queue for Buffer drip-feed.")
    .build();
  sheet.getRange("D2:D500").setDataValidation(statusRule);

  // 4. Set Default "Pending" on initial sample rows if Status is blank
  for (let r = 2; r <= 3; r++) {
    if (sheet.getRange(r, 1).getValue() !== "" && sheet.getRange(r, 4).getValue() === "") {
      sheet.getRange(r, 4).setValue("Pending");
    }
  }
}

/**
 * Automatic Human-in-the-Loop Guard Trigger:
 * Blocks setting Status = "Approved" if LinkedIn/Facebook drafts are empty,
 * or if Include Image? == "Yes" and Image_URL is empty.
 */
function onEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== TAB_NAME) return;

  const row = e.range.getRow();
  const col = e.range.getColumn();
  if (row <= 1) return;

  // If HR edits Column A (Topic) and Status (Col D) is empty, auto-set Status to "Pending"
  if (col === 1 && e.value && sheet.getRange(row, 4).getValue() === "") {
    sheet.getRange(row, 4).setValue("Pending");
  }

  // If HR changes Status (Col D) to "Approved", validate that drafts exist
  if (col === 4 && e.value === "Approved") {
    const includeImage = sheet.getRange(row, 2).getValue();
    const linkedInDraft = sheet.getRange(row, 5).getValue();
    const facebookDraft = sheet.getRange(row, 6).getValue();
    const imageUrl = sheet.getRange(row, 10).getValue();

    if (!linkedInDraft || !facebookDraft) {
      e.range.setValue(e.oldValue || "Pending");
      SpreadsheetApp.getUi().alert(
        "Approval Blocked: AI Drafts have not been generated for this row yet. Wait for Status to reach 'Draft'."
      );
      return;
    }

    if (includeImage === "Yes" && !imageUrl) {
      e.range.setValue("Draft");
      SpreadsheetApp.getUi().alert(
        "Approval Blocked: 'Include Image?' is set to 'Yes', but Image_URL is empty."
      );
      return;
    }
  }
}