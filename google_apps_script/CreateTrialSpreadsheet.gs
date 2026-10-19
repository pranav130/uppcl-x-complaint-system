/**
 * ==============================================================================
 * 1-Click Trial Spreadsheet Generator for UPPCL X Complaint Monitoring
 * Run this function in Google Apps Script (https://script.google.com)
 * It creates a brand new standalone Google Spreadsheet in your Google Drive
 * matching the EXACT format, colors, fonts, and formulas of the original sheet.
 * ==============================================================================
 */

function createTrialSpreadsheet() {
  // 1. Create new spreadsheet in Google Drive
  const ss = SpreadsheetApp.create('UPPCL X Complaint Monitoring - Trial');
  const url = ss.getUrl();
  const id = ss.getId();
  
  Logger.log('====================================================');
  Logger.log('CREATED NEW TRIAL SPREADSHEET:');
  Logger.log(url);
  Logger.log('Spreadsheet ID: ' + id);
  Logger.log('====================================================');

  // 2. Setup 'Twitter Complaint List' Tab
  const mainSheet = ss.getActiveSheet();
  mainSheet.setName('Twitter Complaint List');

  const headers = [
    'DATE', 'Link Shift', 'Reply Shift', 'C F', ' LINK URL', 'Twitter Id',
    'Head', 'Untagged Complaint', 'Picked Status', 'Complaint Type', 'DISCOM',
    'Zone', 'District', 'Remark', 'Status', 'REPLY_WITHIN_30_MIN_BY_Laqshya Media',
    'REPLY_WITHIN_60_MIN_BY_DISCOM', 'COMPLAINT_NO', 'STS',
    // Columns T to AF (Automation Extensions)
    'Post ID', 'Post Text', 'Post Created At (UTC)', 'First Detected At (IST)',
    'Language', 'Routing Confidence', 'Suggested Reply Draft', 'Reply Approval Status',
    'Reply Post ID', 'Reply Post URL', 'Reply Posted At', 'Processing Status', 'Last Error'
  ];

  const colCount = headers.length;

  // Row 1: Cyan Headers (#4DD0E1, Verdana 13pt bold, dark #1A2F40)
  const headerRange = mainSheet.getRange(1, 1, 1, colCount);
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
  mainSheet.setRowHeight(1, 66);

  // Row 2: Counter / Formula Row
  const counterValues = new Array(colCount).fill('');
  counterValues[4] = '=COUNTA(E3:E)';
  counterValues[3] = '=COUNTIF(D3:D, ">=1")';

  const counterRange = mainSheet.getRange(2, 1, 1, colCount);
  counterRange.setValues([counterValues]);
  counterRange.setFontFamily('Verdana');
  counterRange.setFontSize(11);
  counterRange.setFontWeight('bold');
  counterRange.setFontColor('#1A2F40');
  counterRange.setBackground('#4DD0E1');
  counterRange.setHorizontalAlignment('center');
  counterRange.setVerticalAlignment('middle');
  counterRange.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
  mainSheet.setRowHeight(2, 33);

  // Freeze top 2 rows
  mainSheet.setFrozenRows(2);

  // Row 3+: Sample Verified Complaint Rows
  const sampleData = [
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

  const dataRange = mainSheet.getRange(3, 1, sampleData.length, colCount);
  dataRange.setValues(sampleData);
  dataRange.setFontFamily('Verdana');
  dataRange.setFontSize(10);
  dataRange.setHorizontalAlignment('center');
  dataRange.setVerticalAlignment('middle');
  dataRange.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);
  mainSheet.getRange(3, 5, sampleData.length, 1).setHorizontalAlignment('left');
  mainSheet.getRange(3, 21, sampleData.length, 1).setHorizontalAlignment('left');
  mainSheet.getRange(3, 27, sampleData.length, 1).setHorizontalAlignment('left');

  // Set column widths
  mainSheet.setColumnWidth(1, 110);
  mainSheet.setColumnWidth(2, 110);
  mainSheet.setColumnWidth(3, 110);
  mainSheet.setColumnWidth(4, 50);
  mainSheet.setColumnWidth(5, 340);
  mainSheet.setColumnWidth(6, 170);
  mainSheet.setColumnWidth(7, 80);
  mainSheet.setColumnWidth(8, 90);
  mainSheet.setColumnWidth(9, 100);
  mainSheet.setColumnWidth(10, 160);
  mainSheet.setColumnWidth(11, 100);
  mainSheet.setColumnWidth(12, 130);
  mainSheet.setColumnWidth(13, 130);
  mainSheet.setColumnWidth(14, 250);
  mainSheet.setColumnWidth(15, 150);
  mainSheet.setColumnWidth(21, 380);
  mainSheet.setColumnWidth(27, 380);

  // 3. Setup 'Settings' Tab
  const settingsSheet = ss.insertSheet('Settings');
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

  // 4. Setup 'Dashboard' Tab
  const dashSheet = ss.insertSheet('Dashboard');
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

  return { url: url, id: id };
}
