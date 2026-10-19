/**
 * ==============================================================================
 * UPPCL X Complaint Monitoring - In-Place Sheet Formatter
 * 
 * Paste this into:
 * Trial Spreadsheet (https://docs.google.com/spreadsheets/d/1fLRAxtZkwS9-Eab9y15AMm4n44gRmr6Z/)
 *   -> Extensions -> Apps Script
 *   -> Paste this file and click "Run formatThisTrialSheet"
 * 
 * It will instantly format the active sheet to match the EXACT layout of:
 * https://docs.google.com/spreadsheets/d/12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU/edit?gid=283417465#gid=283417465
 * 
 * - Row 1: Header (Height 66px, Fill #4DD0E1 Cyan, Font Verdana 13pt bold, dark #1A2F40)
 * - Row 2: Counter row (Height 33px, Fill #4DD0E1 Cyan, =COUNTA(E3:E))
 * - Frozen Top 2 Rows
 * - Data starting at Row 3 (Verdana 10pt, 1px solid black borders)
 * ==============================================================================
 */

function formatThisTrialSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Target or create 'Twitter Complaint List' tab
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) {
    sheet = ss.getActiveSheet();
    sheet.setName('Twitter Complaint List');
  }

  const headers = [
    'DATE', 'Link Shift', 'Reply Shift', 'C F', ' LINK URL', 'Twitter Id',
    'Head', 'Untagged Complaint', 'Picked Status', 'Complaint Type', 'DISCOM',
    'Zone', 'District', 'Remark', 'Status', 'REPLY_WITHIN_30_MIN_BY_Laqshya Media',
    'REPLY_WITHIN_60_MIN_BY_DISCOM', 'COMPLAINT_NO', 'STS',
    // Automation Extensions (Columns T to AF)
    'Post ID', 'Post Text', 'Post Created At (UTC)', 'First Detected At (IST)',
    'Language', 'Routing Confidence', 'Suggested Reply Draft', 'Reply Approval Status',
    'Reply Post ID', 'Reply Post URL', 'Reply Posted At', 'Processing Status', 'Last Error'
  ];

  const colCount = headers.length;

  // Set Row 1 Headers
  const headerRange = sheet.getRange(1, 1, 1, colCount);
  headerRange.setValues([headers]);
  headerRange.setFontFamily('Verdana');
  headerRange.setFontSize(13);
  headerRange.setFontWeight('bold');
  headerRange.setFontColor('#1A2F40');
  headerRange.setBackground('#4DD0E1');
  headerRange.setHorizontalAlignment('center');
  headerRange.setVerticalAlignment('middle');
  headerRange.setWrap(true);
  headerRange.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
  sheet.setRowHeight(1, 66);

  // Set Row 2 Counter / Formula Row
  const counterValues = new Array(colCount).fill('');
  counterValues[4] = '=COUNTA(E3:E)'; // Column E (LINK URL) Total Count
  counterValues[3] = '=COUNTIF(D3:D, ">=1")'; // Column D (C F) Count
  
  const counterRange = sheet.getRange(2, 1, 1, colCount);
  counterRange.setValues([counterValues]);
  counterRange.setFontFamily('Verdana');
  counterRange.setFontSize(11);
  counterRange.setFontWeight('bold');
  counterRange.setFontColor('#1A2F40');
  counterRange.setBackground('#4DD0E1');
  counterRange.setHorizontalAlignment('center');
  counterRange.setVerticalAlignment('middle');
  counterRange.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
  sheet.setRowHeight(2, 33);

  // Freeze top 2 rows
  sheet.setFrozenRows(2);

  // Sample data rows if empty
  const lastRow = sheet.getLastRow();
  if (lastRow <= 2) {
    const sampleRows = [
      [
        '19-10-2026', 'MORNING', 'MORNING', '1',
        'https://x.com/Diwaker70180261/status/2111604765486707028?s=20',
        'Diwaker70180261', 'upm', '', 'YES', 'SUPPLY_OUTAGE',
        'MVVNL', 'DEVIPATAN', 'GONDA', 'Verified match for GONDA -> MVVNL',
        'Forwarded to Discom', 'YES', '', '', '',
        '2111604765486707028',
        '@UPPCLLKO @mduppcl गोंडा जिले के वजीरगंज ब्लॉक में पिछले 12 घंटे से बिजली आपूर्ति पूरी तरह बाधित है।',
        '2026-10-19T06:00:00Z', '19-10-2026 11:30:00', 'hi', 'HIGH',
        'Concerned team @MVVNLHQ, कृपया सम्मानित उपभोक्ता की बिजली आपूर्ति बाधित होने की शिकायत का संज्ञान लेकर आवश्यक कार्यवाही करें।',
        'DRAFT_READY', '', '', '', 'CLASSIFIED', ''
      ],
      [
        '19-10-2026', 'MORNING', 'MORNING', '1',
        'https://x.com/drx_mohd_sami/status/2111617408557568279?s=20',
        'drx_mohd_sami', 'upl', '', 'YES', 'SUPPLY_OUTAGE',
        'PVVNL', 'BULANDSAHAR', 'BULANDSAHAR', 'Verified match for BULANDSAHAR -> PVVNL',
        'Forwarded to Discom', 'YES', '', '', '',
        '2111617408557568279',
        '@UPPCLLKO @PVVNLHQ Bulandshahr city power outage since 2 PM. Inverter batteries dying, please restore supply immediately.',
        '2026-10-19T06:15:00Z', '19-10-2026 11:45:00', 'en', 'HIGH',
        'Concerned team @PVVNLHQ, kindly look into this consumer power supply outage grievance and take prompt action.',
        'DRAFT_READY', '', '', '', 'CLASSIFIED', ''
      ],
      [
        '19-10-2026', 'MORNING', 'MORNING', '1',
        'https://x.com/durgeshkumabq8/status/2111609477049012326?s=20',
        'durgeshkumabq8', 'akb', '', 'YES', 'TRANSFORMER_DAMAGE',
        'MVVNL', 'AYODHYA', 'AYODHYA', 'Verified match for AYODHYA -> MVVNL',
        'Forwarded to Discom', 'YES', '', '', '',
        '2111609477049012326',
        '@aksharmaBharat @UPPCLLKO हमारे गांव में 63 KVA का ट्रांसफार्मर फुंक गया है। 3 दिन से अंधेरा है। नया ट्रांसफार्मर लगवाया जाए।',
        '2026-10-19T06:20:00Z', '19-10-2026 11:50:00', 'hi', 'HIGH',
        'Concerned team @MVVNLHQ, कृपया क्षतिग्रस्त परिवर्तक (ट्रांसफार्मर) का अविलंब संज्ञान लेकर नियमानुसार आवश्यक कार्यवाही सुनिश्चित करें।',
        'DRAFT_READY', '', '', '', 'CLASSIFIED', ''
      ]
    ];

    const dataRange = sheet.getRange(3, 1, sampleRows.length, colCount);
    dataRange.setValues(sampleRows);
    dataRange.setFontFamily('Verdana');
    dataRange.setFontSize(10);
    dataRange.setHorizontalAlignment('center');
    dataRange.setVerticalAlignment('middle');
    dataRange.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
    
    // Align URLs and text columns to left for readability
    sheet.getRange(3, 5, sampleRows.length, 1).setHorizontalAlignment('left');  // URL
    sheet.getRange(3, 21, sampleRows.length, 1).setHorizontalAlignment('left'); // Post Text
    sheet.getRange(3, 27, sampleRows.length, 1).setHorizontalAlignment('left'); // Reply Draft
  }

  // Set standard column widths
  sheet.setColumnWidth(1, 110); // Date
  sheet.setColumnWidth(2, 110); // Link Shift
  sheet.setColumnWidth(3, 110); // Reply Shift
  sheet.setColumnWidth(4, 50);  // C F
  sheet.setColumnWidth(5, 340); // LINK URL
  sheet.setColumnWidth(6, 170); // Twitter Id
  sheet.setColumnWidth(7, 80);  // Head
  sheet.setColumnWidth(8, 90);  // Untagged Complaint
  sheet.setColumnWidth(9, 100); // Picked Status
  sheet.setColumnWidth(10, 160); // Complaint Type
  sheet.setColumnWidth(11, 100); // DISCOM
  sheet.setColumnWidth(12, 130); // Zone
  sheet.setColumnWidth(13, 130); // District
  sheet.setColumnWidth(14, 250); // Remark
  sheet.setColumnWidth(15, 150); // Status
  sheet.setColumnWidth(21, 380); // Post Text
  sheet.setColumnWidth(27, 380); // Reply Draft

  // 2. Add Supporting Tabs if missing
  setupSupportingTabs(ss);

  Logger.log('Trial Sheet formatted successfully!');
  SpreadsheetApp.getActiveSpreadsheet().toast('Trial Sheet formatted to exact UPPCL specifications!', 'Success', 5);
}

function setupSupportingTabs(ss) {
  // Settings Tab
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
    settingsSheet.getRange(1, 1, 1, 3).setFontFamily('Verdana').setFontWeight('bold').setBackground('#4DD0E1').setFontColor('#1A2F40');
    settingsSheet.getRange(1, 1, settingsData.length, 3).setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
    settingsSheet.autoResizeColumns(1, 3);
  }

  // Dashboard Tab
  let dashSheet = ss.getSheetByName('Dashboard');
  if (!dashSheet) {
    dashSheet = ss.insertSheet('Dashboard');
    const dashData = [
      ['UPPCL X COMPLAINT MONITORING DASHBOARD (TRIAL)', '', '', ''],
      ['Metric', 'Value', 'Formula / Source', 'Notes'],
      ['Total Complaints Recorded', '=COUNTA(\'Twitter Complaint List\'!E3:E)', 'Active post links count', ''],
      ['Outage Complaints', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "SUPPLY_OUTAGE")', 'SUPPLY_OUTAGE', ''],
      ['Transformer Damaged', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "TRANSFORMER_DAMAGE")', 'TRANSFORMER_DAMAGE', ''],
      ['Billing Issues', '=COUNTIF(\'Twitter Complaint List\'!J3:J, "BILL_RELATED")', 'BILL_RELATED', ''],
      ['MVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "MVVNL")', 'Central UP', ''],
      ['PVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "PVVNL")', 'Western UP', ''],
      ['PuVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "PuVVNL")', 'Eastern UP', ''],
      ['DVVNL Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "DVVNL")', 'Southern UP', ''],
      ['KESCo Assigned', '=COUNTIF(\'Twitter Complaint List\'!K3:K, "KESCO")', 'Kanpur City', '']
    ];
    dashSheet.getRange(1, 1, dashData.length, 4).setValues(dashData);
    dashSheet.getRange(1, 1, 1, 4).merge().setFontFamily('Verdana').setFontWeight('bold').setFontSize(14).setBackground('#4DD0E1').setFontColor('#1A2F40').setHorizontalAlignment('center');
    dashSheet.getRange(2, 1, 1, 4).setFontFamily('Verdana').setFontWeight('bold').setBackground('#4DD0E1').setFontColor('#1A2F40');
    dashSheet.getRange(1, 1, dashData.length, 4).setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
    dashSheet.autoResizeColumns(1, 4);
  }
}
