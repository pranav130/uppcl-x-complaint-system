/**
 * ==============================================================================
 * UPPCL X Complaint Monitoring & Workflow Companion Script
 * Container-bound script for Google Sheets:
 * https://docs.google.com/spreadsheets/d/10_210Ynr_F0Pj1Yov_pqjVZ1kaYIEWrbGF1jn16sgNY/
 * ==============================================================================
 */

/**
 * Creates custom menu when spreadsheet is opened.
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('UPPCL Automation')
    .addItem('Restore Blue Clickable Links & Format', 'restoreBlueLinksAndFormat')
    .addItem('Standardize All Row Formats', 'standardizeFormatting')
    .addSeparator()
    .addItem('Review Pending Drafts', 'highlightPendingDrafts')
    .addItem('Approve Selected Rows', 'approveSelectedRows')
    .addSeparator()
    .addItem('Setup Supporting Tabs', 'setupSupportingTabs')
    .addItem('Refresh Dashboard KPIs', 'refreshDashboard')
    .addSeparator()
    .addItem('Emergency Stop: ENGAGE', 'engageEmergencyStop')
    .addItem('Emergency Stop: RELEASE', 'releaseEmergencyStop')
    .addToUi();
}

/**
 * Restores Column E (and Column 29) to native Google Sheets blue clickable hyperlinks
 * and applies uniform 22px compact row height and solid black borders across all rows.
 */
function restoreBlueLinksAndFormat() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) {
    sheet = ss.getActiveSheet();
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return;
  const numDataRows = lastRow - 2;
  const lastCol = Math.max(sheet.getLastColumn(), 32);

  // 1. Format general cells (Verdana 10pt, vertical middle, solid black border, 22px height)
  const dataRange = sheet.getRange(3, 1, numDataRows, lastCol);
  dataRange.setFontFamily('Verdana')
    .setFontSize(10)
    .setFontWeight('normal')
    .setVerticalAlignment('middle')
    .setHorizontalAlignment('center')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP)
    .setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

  // Set non-link text color to black
  sheet.getRange(3, 1, numDataRows, 4).setFontColor('#000000'); // Cols A-D
  sheet.getRange(3, 6, numDataRows, lastCol - 5).setFontColor('#000000'); // Cols F onwards

  // Set uniform compact row height (22px)
  for (let r = 3; r <= lastRow; r++) {
    sheet.setRowHeight(r, 22);
  }

  // 2. Restore Column E (LINK URL) as native blue (#1155cc) underlined clickable links
  const urlRange = sheet.getRange(3, 5, numDataRows, 1);
  const urlValues = urlRange.getValues();
  const linkStyle = SpreadsheetApp.newTextStyle()
    .setForegroundColor('#1155cc')
    .setUnderline(true)
    .setFontFamily('Verdana')
    .setFontSize(10)
    .build();

  const richTextValues = [];
  for (let i = 0; i < urlValues.length; i++) {
    const rawUrl = String(urlValues[i][0] || '').trim();
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
      const rich = SpreadsheetApp.newRichTextValue()
        .setText(rawUrl)
        .setLinkUrl(rawUrl)
        .setTextStyle(linkStyle)
        .build();
      richTextValues.push([rich]);
    } else {
      richTextValues.push([SpreadsheetApp.newRichTextValue().setText(rawUrl).build()]);
    }
  }
  urlRange.setRichTextValues(richTextValues);
  urlRange.setHorizontalAlignment('left');

  // Left-align text columns
  if (lastCol >= 21) {
    sheet.getRange(3, 21, numDataRows, 1).setHorizontalAlignment('left'); // Post Text
  }
  if (lastCol >= 27) {
    sheet.getRange(3, 27, numDataRows, 1).setHorizontalAlignment('left'); // Reply Draft
  }

  SpreadsheetApp.flush();
  try {
    SpreadsheetApp.getUi().alert('All URLs restored to blue clickable links with uniform 22px row formatting!');
  } catch (e) {
    // Ignore alert if executed from background
  }
}

/**
 * Standardize formatting and restore blue links.
 */
function standardizeFormatting() {
  restoreBlueLinksAndFormat();
}

/**
 * Webhook receiver that inserts complaints from the Python monitoring engine.
 */
function doPost(e) {
  try {
    const contents = JSON.parse(e.postData.contents);
    
    // Support remote action: restore_links
    if (contents.action === 'restore_links' || contents.action === 'standardize_format') {
      restoreBlueLinksAndFormat();
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok', action: contents.action }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const rows = contents.rows;
    if (!rows || !rows.length) {
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok', inserted: 0 }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName('Twitter Complaint List');
    if (!sheet) {
      sheet = ss.getActiveSheet();
    }

    const startRow = Math.max(sheet.getLastRow() + 1, 3);
    const range = sheet.getRange(startRow, 1, rows.length, rows[0].length);
    range.setValues(rows);
    range.setFontFamily('Verdana');
    range.setFontSize(10);
    range.setHorizontalAlignment('center');
    range.setVerticalAlignment('middle');
    range.setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
    range.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

    // Uniform 22px row height
    for (let i = 0; i < rows.length; i++) {
      sheet.setRowHeight(startRow + i, 22);
    }

    // Format Column E as blue clickable link
    const linkStyle = SpreadsheetApp.newTextStyle()
      .setForegroundColor('#1155cc')
      .setUnderline(true)
      .setFontFamily('Verdana')
      .setFontSize(10)
      .build();

    const linkRichText = [];
    for (let i = 0; i < rows.length; i++) {
      const urlStr = String(rows[i][4] || '').trim();
      if (urlStr.startsWith('http')) {
        linkRichText.push([SpreadsheetApp.newRichTextValue().setText(urlStr).setLinkUrl(urlStr).setTextStyle(linkStyle).build()]);
      } else {
        linkRichText.push([SpreadsheetApp.newRichTextValue().setText(urlStr).build()]);
      }
    }
    const linkRange = sheet.getRange(startRow, 5, rows.length, 1);
    linkRange.setRichTextValues(linkRichText);
    linkRange.setHorizontalAlignment('left');

    if (rows[0].length >= 21) {
      sheet.getRange(startRow, 21, rows.length, 1).setHorizontalAlignment('left');
    }
    if (rows[0].length >= 27) {
      sheet.getRange(startRow, 27, rows.length, 1).setHorizontalAlignment('left');
    }

    SpreadsheetApp.flush();
    return ContentService.createTextOutput(JSON.stringify({ status: 'ok', inserted: rows.length, startRow: startRow }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: 'error', error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Initializes supporting tabs (Settings, Dashboard, Processing Log)
 */
function setupSupportingTabs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Settings Tab
  let settingsSheet = ss.getSheetByName('Settings');
  if (!settingsSheet) {
    settingsSheet = ss.insertSheet('Settings');
    const settingsData = [
      ['SETTING_KEY', 'VALUE', 'DESCRIPTION'],
      ['EMERGENCY_STOP', 'FALSE', 'Global kill-switch. When TRUE, no polling or replies run.'],
      ['AUTO_POST_ENABLED', 'FALSE', 'When FALSE, replies only draft and require manual approval.'],
      ['DAILY_POST_CAP', '50', 'Maximum automated replies permitted per calendar day.'],
      ['POLLING_INTERVAL_MINS', '5', 'Frequency of background post monitoring cycles.'],
      ['ALLOWED_DISCOMS', '@PVVNLHQ, @dvvnlhq, @PuVVNLHQ, @KESCoHQ, @MVVNLHQ', 'Safety allowlist of receiving handles.'],
      ['MONITORED_APEX', '@UPPCLLKO, @EMofficeUP, @AKSharmaOffice, @aksharmaBharat, @ChairmanUppcl, @mduppcl', 'Monitored accounts.']
    ];
    settingsSheet.getRange(1, 1, settingsData.length, 3).setValues(settingsData);
    settingsSheet.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#4DD0E1').setFontColor('#1A2F40');
    settingsSheet.autoResizeColumns(1, 3);
  }

  // 2. Processing Log Tab
  let logSheet = ss.getSheetByName('Processing Log');
  if (!logSheet) {
    logSheet = ss.insertSheet('Processing Log');
    const logHeaders = [['TIMESTAMP (IST)', 'EVENT_TYPE', 'POSTS_FETCHED', 'COMPLAINTS_FOUND', 'DRAFTS_READY', 'REPLIES_POSTED', 'ERRORS', 'STATUS']];
    logSheet.getRange(1, 1, 1, logHeaders[0].length).setValues(logHeaders);
    logSheet.getRange(1, 1, 1, logHeaders[0].length).setFontWeight('bold').setBackground('#4DD0E1').setFontColor('#1A2F40');
    logSheet.autoResizeColumns(1, logHeaders[0].length);
  }

  // 3. Dashboard Tab
  let dashSheet = ss.getSheetByName('Dashboard');
  if (!dashSheet) {
    dashSheet = ss.insertSheet('Dashboard');
    const dashData = [
      ['UPPCL X COMPLAINT MONITORING DASHBOARD', '', '', ''],
      ['Metric', 'Value', 'Formula / Source', 'Notes'],
      ['Total Complaints Recorded', '=COUNTA(\'Twitter Complaint List\'!E3:E)', 'Active post links count', ''],
      ['Outage Complaints', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "SUPPLY_OUTAGE")', 'SUPPLY_OUTAGE', ''],
      ['Transformer Damaged', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "TRANSFORMER_DAMAGE")', 'TRANSFORMER_DAMAGE', ''],
      ['Billing Issues', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "BILL_RELATED")', 'BILL_RELATED', ''],
      ['Safety Hazards / Broken Poles', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "POLE_WIRE_HAZARD")', 'High priority', ''],
      ['MVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "MVVNL")', 'Central UP', ''],
      ['PVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "PVVNL")', 'Western UP', ''],
      ['PuVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "PuVVNL")', 'Eastern UP', ''],
      ['DVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "DVVNL")', 'Southern UP', ''],
      ['KESCo Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "KESCO")', 'Kanpur City', '']
    ];
    dashSheet.getRange(1, 1, dashData.length, 4).setValues(dashData);
    dashSheet.getRange(1, 1, 1, 4).merge().setFontWeight('bold').setFontSize(14).setBackground('#4DD0E1').setFontColor('#1A2F40').setHorizontalAlignment('center');
    dashSheet.getRange(2, 1, 1, 4).setFontWeight('bold').setBackground('#4DD0E1').setFontColor('#1A2F40');
    dashSheet.autoResizeColumns(1, 4);
  }

  SpreadsheetApp.getUi().alert('Supporting tabs (Settings, Processing Log, Dashboard) verified and ready.');
}

/**
 * Highlights rows with ready drafts in soft yellow for review.
 */
function highlightPendingDrafts() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  if (sheet.getName() !== 'Twitter Complaint List') {
    SpreadsheetApp.getUi().alert('Please switch to the "Twitter Complaint List" tab.');
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return;

  const approvalCol = 28; // Column AB (Reply Approval Status)
  const range = sheet.getRange(3, 1, lastRow - 2, sheet.getLastColumn());
  const values = range.getValues();

  let count = 0;
  for (let i = 0; i < values.length; i++) {
    const status = values[i][approvalCol - 1];
    if (status === 'DRAFT_READY' || status === 'PENDING') {
      sheet.getRange(3 + i, 1, 1, sheet.getLastColumn()).setBackground('#FFF9C4');
      count++;
    }
  }

  SpreadsheetApp.getUi().alert('Found ' + count + ' complaint row(s) with drafts pending review.');
}

/**
 * Approves selected rows for publishing.
 */
function approveSelectedRows() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  if (sheet.getName() !== 'Twitter Complaint List') {
    SpreadsheetApp.getUi().alert('Please switch to the "Twitter Complaint List" tab.');
    return;
  }

  const selection = sheet.getActiveRange();
  const startRow = selection.getRow();
  const numRows = selection.getNumRows();

  if (startRow < 3) {
    SpreadsheetApp.getUi().alert('Please select data rows starting at Row 3.');
    return;
  }

  const approvalCol = 28;
  for (let r = startRow; r < startRow + numRows; r++) {
    sheet.getRange(r, approvalCol).setValue('APPROVED');
    sheet.getRange(r, 1, 1, sheet.getLastColumn()).setBackground('#E8F5E9');
  }

  SpreadsheetApp.getUi().alert('Marked ' + numRows + ' row(s) as APPROVED.');
}

function engageEmergencyStop() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const settings = ss.getSheetByName('Settings');
  if (settings) {
    settings.getRange(2, 2).setValue('TRUE');
    SpreadsheetApp.getUi().alert('EMERGENCY STOP ENGAGED: Automated posting and sync halted.');
  }
}

function releaseEmergencyStop() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const settings = ss.getSheetByName('Settings');
  if (settings) {
    settings.getRange(2, 2).setValue('FALSE');
    SpreadsheetApp.getUi().alert('EMERGENCY STOP RELEASED: System returned to normal operating mode.');
  }
}

function refreshDashboard() {
  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert('Dashboard metrics refreshed.');
}
