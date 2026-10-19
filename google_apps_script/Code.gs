/**
 * ==============================================================================
 * UPPCL X Complaint Monitoring & Workflow Companion Script
 * Container-bound or Standalone Apps Script for Google Sheets
 * Target Sheet: https://docs.google.com/spreadsheets/d/12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU/edit
 * ==============================================================================
 */

/**
 * Creates custom menu when spreadsheet is opened.
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('UPPCL Automation')
    .addItem('Setup Supporting Tabs', 'setupSupportingTabs')
    .addItem('Review Pending Drafts', 'highlightPendingDrafts')
    .addItem('Approve Selected Rows', 'approveSelectedRows')
    .addSeparator()
    .addItem('Emergency Stop: ENGAGE', 'engageEmergencyStop')
    .addItem('Emergency Stop: RELEASE', 'releaseEmergencyStop')
    .addSeparator()
    .addItem('Refresh Dashboard KPIs', 'refreshDashboard')
    .addToUi();
}

/**
 * Initializes supporting tabs (Settings, Dashboard, Processing Log, Review Queue)
 * without touching or overwriting existing operational or reference tabs.
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
    settingsSheet.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#E8EAED');
    settingsSheet.autoResizeColumns(1, 3);
  }

  // 2. Processing Log Tab
  let logSheet = ss.getSheetByName('Processing Log');
  if (!logSheet) {
    logSheet = ss.insertSheet('Processing Log');
    const logHeaders = [['TIMESTAMP (IST)', 'EVENT_TYPE', 'POSTS_FETCHED', 'COMPLAINTS_FOUND', 'DRAFTS_READY', 'REPLIES_POSTED', 'ERRORS', 'STATUS']];
    logSheet.getRange(1, 1, 1, logHeaders[0].length).setValues(logHeaders);
    logSheet.getRange(1, 1, 1, logHeaders[0].length).setFontWeight('bold').setBackground('#E8EAED');
    logSheet.autoResizeColumns(1, logHeaders[0].length);
  }

  // 3. Dashboard Tab
  let dashSheet = ss.getSheetByName('Dashboard');
  if (!dashSheet) {
    dashSheet = ss.insertSheet('Dashboard');
    const dashData = [
      ['UPPCL X COMPLAINT MONITORING DASHBOARD', '', '', ''],
      ['Metric', 'Value', 'Formula / Source', 'Notes'],
      ['Total Complaints Recorded', '=COUNTA(\'Twitter Complaint List\'!E11:E)', 'Active post links count', ''],
      ['Complaints Today', '=COUNTIF(\'Twitter Complaint List\'!A11:A, TEXT(TODAY(), "DD-MM-YYYY"))', 'Today count', ''],
      ['Outage Complaints', '=COUNTIF(\'Twitter Complaint List\'!J11:J, "SUPPLY_OUTAGE")', 'SUPPLY_OUTAGE', ''],
      ['Transformer Damaged', '=COUNTIF(\'Twitter Complaint List\'!J11:J, "TRANSFORMER_DAMAGE")', 'TRANSFORMER_DAMAGE', ''],
      ['Billing Issues', '=COUNTIF(\'Twitter Complaint List\'!J11:J, "BILL_RELATED")', 'BILL_RELATED', ''],
      ['Safety Hazards / Broken Poles', '=COUNTIF(\'Twitter Complaint List\'!J11:J, "POLE_RELATED") + COUNTIF(\'Twitter Complaint List\'!J11:J, "ACCIDENT_PRONE_TO_OCCURED")', 'High priority', ''],
      ['MVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K11:K, "MVVNL")', 'Central UP', ''],
      ['PVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K11:K, "PVVNL")', 'Western UP', ''],
      ['PuVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K11:K, "PuVVNL")', 'Eastern UP', ''],
      ['DVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K11:K, "DVVNL")', 'Southern UP', ''],
      ['KESCo Assigned', '=COUNTIF(\'Twitter Complaint List\'!K11:K, "KESCO")', 'Kanpur City', '']
    ];
    dashSheet.getRange(1, 1, dashData.length, 4).setValues(dashData);
    dashSheet.getRange(1, 1, 1, 4).merge().setFontWeight('bold').setFontSize(14).setBackground('#1A73E8').setFontColor('#FFFFFF');
    dashSheet.getRange(2, 1, 1, 4).setFontWeight('bold').setBackground('#E8EAED');
    dashSheet.autoResizeColumns(1, 4);
  }

  SpreadsheetApp.getUi().alert('Supporting tabs (Settings, Processing Log, Dashboard) verified and ready.');
}

/**
 * Approves the selected row drafts for publishing.
 */
function approveSelectedRows() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  if (sheet.getName() !== 'Twitter Complaint List') {
    SpreadsheetApp.getUi().alert('Please switch to the "Twitter Complaint List" tab to approve drafts.');
    return;
  }

  const selection = sheet.getActiveRange();
  const startRow = selection.getRow();
  const numRows = selection.getNumRows();

  // Column AA is column 27 (Reply Approval Status)
  for (let r = 0; r < numRows; r++) {
    const rowIdx = startRow + r;
    if (rowIdx >= 10) { // Below headers
      sheet.getRange(rowIdx, 27).setValue('APPROVED');
    }
  }

  SpreadsheetApp.getUi().alert(`Approved ${numRows} row(s) for publishing.`);
}

/**
 * Highlights rows needing human review.
 */
function highlightPendingDrafts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) return;

  const lastRow = sheet.getLastRow();
  if (lastRow < 10) return;

  const data = sheet.getRange(10, 1, lastRow - 9, 32).getValues();
  let count = 0;

  for (let i = 0; i < data.length; i++) {
    const rowIdx = 10 + i;
    const approvalStatus = data[i][26]; // Column AA
    const confidence = data[i][24]; // Column Y

    if (approvalStatus === 'NEEDS_REVIEW' || confidence === 'UNCERTAIN') {
      sheet.getRange(rowIdx, 1, 1, 19).setBackground('#FFF3E0'); // Light amber highlight
      count++;
    }
  }

  SpreadsheetApp.getUi().alert(`Identified and highlighted ${count} complaint(s) requiring manual verification.`);
}

/**
 * Engages emergency stop in Settings tab.
 */
function engageEmergencyStop() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const settings = ss.getSheetByName('Settings');
  if (settings) {
    settings.getRange(2, 2).setValue('TRUE');
    SpreadsheetApp.getUi().alert('EMERGENCY STOP ENGAGED: Automated posting and sync have been halted.');
  }
}

/**
 * Releases emergency stop in Settings tab.
 */
function releaseEmergencyStop() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const settings = ss.getSheetByName('Settings');
  if (settings) {
    settings.getRange(2, 2).setValue('FALSE');
    SpreadsheetApp.getUi().alert('EMERGENCY STOP RELEASED: System returned to normal operating mode.');
  }
}

/**
 * Recalculates Dashboard formulas.
 */
function refreshDashboard() {
  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert('Dashboard metrics refreshed.');
}
