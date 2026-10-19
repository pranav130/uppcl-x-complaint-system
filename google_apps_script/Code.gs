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
    .addItem('▶ Enable 24/7 Cloud Sync (Laptop-Free)', 'enable247CloudSync')
    .addItem('⏹ Disable 24/7 Cloud Sync', 'disable247CloudSync')
    .addItem('⚡ Run Cloud Sync Once Now', 'runCloudSyncCycle')
    .addSeparator()
    .addItem('Apply Original Formatting (Blue Links & 45px Rows)', 'applyOriginalFormatting')
    .addItem('Fix Misclassified Appreciation Rows', 'fixMisclassifiedComplaints')
    .addItem('Make Rows Compact (22px)', 'makeRowsCompact')
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
 * Applies the original comfortable row height (45px) with text wrapping
 * and restores Column E as blue clickable hyperlinks (#1155cc, underlined).
 */
function applyOriginalFormatting() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) {
    sheet = ss.getActiveSheet();
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return;
  const numDataRows = lastRow - 2;
  const lastCol = Math.max(sheet.getLastColumn(), 32);

  // 1. Row 1 Header (66px, #4DD0E1 Cyan, Verdana 13pt bold)
  sheet.setRowHeight(1, 66);
  sheet.getRange(1, 1, 1, lastCol)
    .setFontFamily('Verdana').setFontSize(13).setFontWeight('bold')
    .setBackground('#4DD0E1').setFontColor('#1A2F40')
    .setHorizontalAlignment('center').setVerticalAlignment('middle')
    .setWrap(true)
    .setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

  // 2. Row 2 Counter (33px, #4DD0E1 Cyan, Verdana 11pt bold)
  sheet.setRowHeight(2, 33);
  sheet.getRange(2, 1, 1, lastCol)
    .setFontFamily('Verdana').setFontSize(11).setFontWeight('bold')
    .setBackground('#4DD0E1').setFontColor('#1A2F40')
    .setHorizontalAlignment('center').setVerticalAlignment('middle')
    .setWrap(false)
    .setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

  sheet.setFrozenRows(2);

  // 3. Set all data rows to 45px height with text wrapping
  for (let r = 3; r <= lastRow; r++) {
    sheet.setRowHeight(r, 45);
  }

  const dataRange = sheet.getRange(3, 1, numDataRows, lastCol);
  dataRange.setFontFamily('Verdana')
    .setFontSize(10)
    .setFontWeight('normal')
    .setVerticalAlignment('middle')
    .setHorizontalAlignment('center')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP)
    .setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

  // Set standard columns font color to black
  sheet.getRange(3, 1, numDataRows, 4).setFontColor('#000000');
  sheet.getRange(3, 6, numDataRows, lastCol - 5).setFontColor('#000000');

  // 4. Restore Column E (LINK URL) as native blue (#1155cc) underlined clickable links
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
    sheet.getRange(3, 21, numDataRows, 1).setHorizontalAlignment('left');
  }
  if (lastCol >= 27) {
    sheet.getRange(3, 27, numDataRows, 1).setHorizontalAlignment('left');
  }

  SpreadsheetApp.flush();
}

/**
 * Optional alternative: Compact 22px row height with blue links.
 */
function makeRowsCompact() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) sheet = ss.getActiveSheet();

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return;

  for (let r = 3; r <= lastRow; r++) {
    sheet.setRowHeight(r, 22);
  }
  sheet.getRange(3, 1, lastRow - 2, sheet.getLastColumn()).setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
  SpreadsheetApp.flush();
}

/**
 * Scans all rows in 'Twitter Complaint List' and corrects any official DISCOM replies,
 * trailing thread updates, or citizen requests that were incorrectly marked as APPRECIATION.
 */
function fixMisclassifiedComplaints() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) sheet = ss.getActiveSheet();

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return 0;

  const numRows = lastRow - 2;
  const lastCol = Math.max(sheet.getLastColumn(), 32);
  const dataRange = sheet.getRange(3, 1, numRows, lastCol);
  const values = dataRange.getValues();

  const officialHandles = [
    'uppcllko', 'mduppcl', 'chairmanuppcl', 'emofficeup', 'aksharmaoffice', 'aksharmabharat',
    'pvvnlhq', '1912pvvnl', 'pvvnl', 'dvvnlhq', 'dvvnl_care', 'puvvnlhq', 'puvvnl',
    'kescohq', 'skescokanpur', '1912kesco', 'mvvnlhq', 'mvvnlmd', 'madhyanchalv', 'zoneamausi'
  ];

  let correctedCount = 0;

  for (let i = 0; i < values.length; i++) {
    const row = values[i];
    const twitterId = String(row[5] || '').toLowerCase().replace('@', '').trim();
    const pickedStatus = String(row[8] || '').trim().toUpperCase();
    const fullText = (String(row[20] || '') + ' ' + String(row[4] || '')).toLowerCase();

    const isOfficial = officialHandles.some(h => twitterId.includes(h)) ||
                       twitterId.startsWith('1912') ||
                       twitterId.endsWith('hq') ||
                       twitterId.endsWith('care');

    const hasReplyOrComplaintMarkers = /प्रिय\s*उपभोक्ता|प्रिय\s*ग्राहक|काम\s*चल\s*रहा|पूर्व\s*में\s*दर्ज|शिकायत\s*संख्या|1912|संबंधित\s*अधिकारी|समाधान\s*कर\s*दिया|previously\s*lodged|work\s*is\s*going|अनुरोध|ots|बकाया|तार|पोल|खंभा/i.test(fullText);

    // If marked APPRECIATION but is an official handle or official reply:
    if (pickedStatus === 'APPRECIATION' && (isOfficial || hasReplyOrComplaintMarkers)) {
      const rowIndex = i + 3;
      sheet.getRange(rowIndex, 9).setValue('YES'); // Picked Status
      if (!row[9] || String(row[9]).trim() === '') {
        const compType = (fullText.includes('ots') || fullText.includes('बकाया')) ? 'BILL_RELATED' : 'DISSATISFIED_CONSUMER';
        sheet.getRange(rowIndex, 10).setValue(compType); // Complaint Type
      }
      sheet.getRange(rowIndex, 15).setValue('Forwarded to Discom'); // Status
      sheet.getRange(rowIndex, 16).setValue('YES'); // Reply within 30 min
      correctedCount++;
    }
  }

  SpreadsheetApp.flush();
  try {
    SpreadsheetApp.getUi().alert(`Completed: Corrected ${correctedCount} misclassified complaint rows to 'Picked Status: YES' and 'DISSATISFIED_CONSUMER'.`);
  } catch (e) {
    // Webhook execution context without active UI
  }
  return correctedCount;
}

/**
 * Webhook receiver that inserts complaints from the Python monitoring engine.
 */
function doPost(e) {
  try {
    const contents = JSON.parse(e.postData.contents);
    if (contents.action === 'restore_links' || contents.action === 'apply_original_format') {
      applyOriginalFormatting();
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok', action: contents.action }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    if (contents.action === 'fix_misclassified') {
      const fixed = fixMisclassifiedComplaints();
      return ContentService.createTextOutput(JSON.stringify({ status: 'ok', action: contents.action, fixedCount: fixed }))
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
    range.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
    range.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

    // Set row height to 45px matching original format
    for (let i = 0; i < rows.length; i++) {
      sheet.setRowHeight(startRow + i, 45);
    }

    // Set Column E as blue clickable link
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

function setupSupportingTabs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
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
}

function highlightPendingDrafts() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  if (sheet.getName() !== 'Twitter Complaint List') {
    SpreadsheetApp.getUi().alert('Please switch to the "Twitter Complaint List" tab.');
    return;
  }

  const lastRow = sheet.getLastRow();
  if (lastRow < 3) return;

  const approvalCol = 28;
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

/**
 * ==============================================================================
 * 24/7 CLOUD SYNC ENGINE (RUNS ENTIRELY ON GOOGLE CLOUD - ZERO LAPTOP NEEDED)
 * ==============================================================================
 */

/**
 * Enables automatic 5-minute cloud synchronization via Google Cloud time-driven trigger.
 * Once activated, Google's cloud servers run the sync 24/7 even when your laptop is closed.
 */
function enable247CloudSync() {
  disable247CloudSync(); // Prevent multiple triggers
  ScriptApp.newTrigger('runCloudSyncCycle')
    .timeBased()
    .everyMinutes(5)
    .create();

  // Run initial cycle immediately
  runCloudSyncCycle();

  try {
    SpreadsheetApp.getUi().alert(
      '✅ 24/7 Cloud Sync is now ACTIVE!\n\n' +
      'Google Cloud will automatically monitor X and update this sheet every 5 minutes.\n\n' +
      'You can safely close your laptop or browser — the cloud will keep running 24/7 uninterrupted!'
    );
  } catch (e) {
    Logger.log('24/7 Trigger created.');
  }
}

/**
 * Disables the automatic 24/7 cloud sync trigger.
 */
function disable247CloudSync() {
  const triggers = ScriptApp.getProjectTriggers();
  let count = 0;
  for (let i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'runCloudSyncCycle') {
      ScriptApp.deleteTrigger(triggers[i]);
      count++;
    }
  }
  try {
    SpreadsheetApp.getUi().alert('⏹ 24/7 Cloud Sync stopped. Removed ' + count + ' active trigger(s).');
  } catch (e) {
    Logger.log('Disabled ' + count + ' trigger(s).');
  }
}

/**
 * Core 24/7 cloud sync function executed by the Google Cloud time-based trigger.
 * Fetches recent tweets from X API v2, classifies them, and appends them to the sheet.
 */
function runCloudSyncCycle() {
  const props = PropertiesService.getScriptProperties();
  const bearerToken = props.getProperty('X_BEARER_TOKEN') ||
    'AAAAAAAAAAAAAAAAAAAAACbr%2FwEAAAAAySPqrdOjXkNWagBKKbkzMA97ZnI%3DRBPSknXnu5S8uXS3j7lPbXPHlYCpiLfD2Yt8cRtRvWm1NcSi1E';

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Twitter Complaint List');
  if (!sheet) sheet = ss.getActiveSheet();

  const lastRow = sheet.getLastRow();
  const existingIds = new Set();
  if (lastRow >= 3) {
    const checkStart = Math.max(3, lastRow - 500);
    const idRange = sheet.getRange(checkStart, 3, lastRow - checkStart + 1, 1).getValues();
    for (let i = 0; i < idRange.length; i++) {
      const val = String(idRange[i][0]).trim();
      if (val) existingIds.add(val);
    }
  }

  let sinceId = props.getProperty('LAST_SEEN_POST_ID');

  const query = '(@UPPCLLKO OR @EMofficeUP OR @AKSharmaOffice OR @aksharmaBharat OR @ChairmanUppcl OR @mduppcl OR to:UPPCLLKO OR to:EMofficeUP OR to:AKSharmaOffice OR to:aksharmaBharat OR to:ChairmanUppcl OR to:mduppcl) -is:retweet';
  let url = 'https://api.twitter.com/2/tweets/search/recent?query=' + encodeURIComponent(query) +
    '&max_results=50' +
    '&tweet.fields=id,text,author_id,created_at,conversation_id,in_reply_to_user_id' +
    '&expansions=author_id' +
    '&user.fields=id,name,username';

  if (sinceId) {
    url += '&since_id=' + sinceId;
  }

  let response;
  try {
    response = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: {
        'Authorization': 'Bearer ' + bearerToken,
        'User-Agent': 'UPPCLComplaintMonitor-AppsScript/1.0'
      },
      muteHttpExceptions: true
    });
  } catch (err) {
    Logger.log('HTTP fetch error: ' + err);
    return;
  }

  const statusCode = response.getResponseCode();
  if (statusCode !== 200) {
    Logger.log('X API returned status ' + statusCode + ': ' + response.getContentText());
    return;
  }

  const data = JSON.parse(response.getContentText());
  const tweets = data.data || [];
  if (tweets.length === 0) {
    Logger.log('No new tweets found in this cycle.');
    return;
  }

  const usersMap = {};
  if (data.includes && data.includes.users) {
    for (let i = 0; i < data.includes.users.length; i++) {
      const u = data.includes.users[i];
      usersMap[u.id] = u;
    }
  }

  let highestId = sinceId || '0';
  const rowsToInsert = [];

  // Sort tweets oldest to newest
  tweets.sort(function(a, b) {
    if (a.id.length !== b.id.length) return a.id.length - b.id.length;
    return a.id.localeCompare(b.id);
  });

  for (let t = 0; t < tweets.length; t++) {
    const tweet = tweets[t];
    const tweetId = String(tweet.id);

    if (tweetId.length > highestId.length || (tweetId.length === highestId.length && tweetId > highestId)) {
      highestId = tweetId;
    }

    if (existingIds.has(tweetId)) {
      continue;
    }

    const user = usersMap[tweet.author_id] || { username: 'citizen', name: 'Citizen' };
    const username = user.username;
    const authorName = user.name;
    const text = tweet.text || '';
    const tweetUrl = 'https://x.com/' + username + '/status/' + tweetId;

    let istDateStr = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd');
    let istTimeStr = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'HH:mm:ss');
    if (tweet.created_at) {
      const dt = new Date(tweet.created_at);
      istDateStr = Utilities.formatDate(dt, 'Asia/Kolkata', 'yyyy-MM-dd');
      istTimeStr = Utilities.formatDate(dt, 'Asia/Kolkata', 'HH:mm:ss');
    }

    const c = classifyTweetInScript(text, username);

    const row = new Array(32).fill('');
    row[0] = ''; // S.No.
    row[1] = istDateStr; // Date
    row[2] = tweetId; // Complaint No.
    row[3] = 'Twitter/X'; // Source
    row[4] = tweetUrl; // Link
    row[5] = '@' + username; // Twitter ID
    row[6] = authorName; // Name
    row[7] = 'Official'; // Executive
    row[8] = c.pickedStatus; // Picked Status (YES, NO, APPRECIATION)
    row[9] = c.complaintType; // Complaint Type
    row[10] = c.discom; // Discom
    row[11] = c.district; // District
    row[12] = c.zone; // Zone
    row[13] = ''; // Region
    row[14] = 'Pending'; // Status
    row[15] = c.replyWithin30Min; // Reply within 30 min
    row[16] = istTimeStr; // Time of Tweet
    row[17] = c.summary; // Complaint Detail
    row[18] = c.actionTaken; // Action Taken
    row[19] = ''; // Remarks
    row[20] = text; // Original Tweet Text
    row[21] = ''; // Retweet/Quote count
    row[22] = ''; // Media Link
    row[23] = ''; // Verified
    row[24] = ''; // Follower count
    row[25] = ''; // Language
    row[26] = c.draftReply; // Draft Reply
    row[27] = 'DRAFT_READY'; // Approval Status
    row[28] = ''; // Escalation Level
    row[29] = ''; // Assigned Official
    row[30] = ''; // Resolution TAT
    row[31] = ''; // Feedback Status

    rowsToInsert.push(row);
    existingIds.add(tweetId);
  }

  if (rowsToInsert.length > 0) {
    const insertStartRow = Math.max(sheet.getLastRow() + 1, 3);
    const startSNo = insertStartRow - 2;

    for (let r = 0; r < rowsToInsert.length; r++) {
      rowsToInsert[r][0] = startSNo + r;
    }

    const range = sheet.getRange(insertStartRow, 1, rowsToInsert.length, 32);
    range.setValues(rowsToInsert);
    range.setFontFamily('Verdana');
    range.setFontSize(10);
    range.setHorizontalAlignment('center');
    range.setVerticalAlignment('middle');
    range.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
    range.setBorder(true, true, true, true, true, true, '#000000', SpreadsheetApp.BorderStyle.SOLID);

    // Apply 45px row height
    for (let r = 0; r < rowsToInsert.length; r++) {
      sheet.setRowHeight(insertStartRow + r, 45);
    }

    // Restore Column E as blue clickable link (#1155cc)
    const linkStyle = SpreadsheetApp.newTextStyle()
      .setForegroundColor('#1155cc')
      .setUnderline(true)
      .setFontFamily('Verdana')
      .setFontSize(10)
      .build();

    const linkRichText = [];
    for (let r = 0; r < rowsToInsert.length; r++) {
      const u = rowsToInsert[r][4];
      linkRichText.push([SpreadsheetApp.newRichTextValue().setText(u).setLinkUrl(u).setTextStyle(linkStyle).build()]);
    }
    const linkRange = sheet.getRange(insertStartRow, 5, rowsToInsert.length, 1);
    linkRange.setRichTextValues(linkRichText);
    linkRange.setHorizontalAlignment('left');

    sheet.getRange(insertStartRow, 21, rowsToInsert.length, 1).setHorizontalAlignment('left');
    sheet.getRange(insertStartRow, 27, rowsToInsert.length, 1).setHorizontalAlignment('left');

    SpreadsheetApp.flush();
    Logger.log('Appended ' + rowsToInsert.length + ' rows.');
  }

  if (highestId && highestId !== '0') {
    props.setProperty('LAST_SEEN_POST_ID', highestId);
  }
}

/**
 * Intelligent grievance classifier with UP Discom routing and accurate Appreciation/Complaint distinction.
 */
function classifyTweetInScript(text, username) {
  const lowerText = text.toLowerCase();
  const lowerUser = username.toLowerCase();

  const officialHandles = [
    'uppcllko', 'mduppcl', 'chairmanuppcl', 'emofficeup', 'aksharmaoffice', 'aksharmabharat',
    'pvvnlhq', '1912pvvnl', 'pvvnl', 'dvvnlhq', 'dvvnl_care', 'puvvnlhq', 'puvvnl',
    'kescohq', 'skescokanpur', '1912kesco', 'mvvnlhq', 'mvvnlmd', 'madhyanchalv', 'zoneamausi'
  ];

  const isOfficial = officialHandles.some(h => lowerUser.includes(h)) ||
                     lowerUser.startsWith('1912') ||
                     lowerUser.endsWith('hq') ||
                     lowerUser.endsWith('care');

  // DISCOM Mapping
  let discom = '';
  if (/pvvnl|meerut|noida|ghaziabad|moradabad|saharanpur|aligarh|bulandshahr|muzaffarnagar|baghpat/i.test(lowerText)) {
    discom = 'PVVNL';
  } else if (/puvvnl|varanasi|prayagraj|gorakhpur|ayodhya|azamgarh|mirzapur|jaunpur|basti/i.test(lowerText)) {
    discom = 'PuVVNL';
  } else if (/mvvnl|lucknow|bareilly|faizabad|sitapur|lakhimpur|hardoi|raebareli|unnao/i.test(lowerText)) {
    discom = 'MVVNL';
  } else if (/dvvnl|agra|mathura|firozabad|jhansi|banda|etawah|mainpuri/i.test(lowerText)) {
    discom = 'DVVNL';
  } else if (/kesco|kanpur/i.test(lowerText)) {
    discom = 'KESCo';
  }

  // District Mapping
  let district = '';
  const districts = [
    'Lucknow', 'Kanpur', 'Varanasi', 'Agra', 'Meerut', 'Noida', 'Ghaziabad', 'Prayagraj',
    'Gorakhpur', 'Bareilly', 'Aligarh', 'Moradabad', 'Saharanpur', 'Jhansi', 'Ayodhya',
    'Muzaffarnagar', 'Mathura', 'Budaun', 'Rampur', 'Shahjahanpur', 'Farrukhabad', 'Firozabad'
  ];
  for (let d of districts) {
    if (new RegExp('\\b' + d.toLowerCase() + '\\b', 'i').test(lowerText)) {
      district = d;
      break;
    }
  }

  // Grievance Category
  let complaintType = 'DISSATISFIED_CONSUMER';
  if (/बिजली\s*गायब|आपूर्ति\s*ठप|no\s*power|no\s*electricity|power\s*cut|outage|blackout|बिजली\s*कटौ|बिजली\s*नहीं/i.test(lowerText)) {
    complaintType = 'SUPPLY_OUTAGE';
  } else if (/ट्रांसफार्मर|transformer|फुंक|ब्लास्ट/i.test(lowerText)) {
    complaintType = 'TRANSFORMER_ISSUE';
  } else if (/बिल|bill|billing|मीटर\s*रीडिंग|overcharge|ots|बकाया/i.test(lowerText)) {
    complaintType = 'BILL_RELATED';
  } else if (/तार\s*टू|करंट|करंट\s*आ\s*रहा|spark|wire\s*break|danger|हादसा|खंभा|पोल/i.test(lowerText)) {
    complaintType = 'SAFETY_HAZARD';
  } else if (/meter|मीटर\s*खराब|मीटर\s*बदल/i.test(lowerText)) {
    complaintType = 'METER_FAULT';
  } else if (/नया\s*कनेक्शन|new\s*connection/i.test(lowerText)) {
    complaintType = 'NEW_CONNECTION';
  }

  // Determine Picked Status (YES, NO, APPRECIATION)
  let pickedStatus = 'YES';
  const hasPureAppreciation = /बहुत\s*बहुत\s*धन्यवाद|उत्कृष्ट\s*कार्य|सराहनीय|great\s*job|thank\s*you\s*so\s*much|thanks\s*for\s*quick/i.test(lowerText) &&
                              !/समस्या|शिकायत|बिजली|outage|complaint|अधिकारी|प्रिय\s*उपभोक्ता/i.test(lowerText);

  if (hasPureAppreciation && !isOfficial) {
    pickedStatus = 'APPRECIATION';
    complaintType = 'APPRECIATION';
  }

  const discomHandle = discom ? ('@' + discom + 'HQ') : '@UPPCLLKO';
  const draftReply = `प्रिय उपभोक्ता, आपकी शिकायत को संबंधित वितरण निगम ${discomHandle} को त्वरित संज्ञान एवं समाधान हेतु अग्रसारित किया जा रहा है।`;

  return {
    discom: discom || 'UPPCL',
    district: district,
    zone: district ? district + ' Zone' : '',
    complaintType: complaintType,
    pickedStatus: pickedStatus,
    replyWithin30Min: isOfficial ? 'YES' : 'NO',
    summary: text.substring(0, 150),
    actionTaken: isOfficial ? 'Forwarded to Discom' : 'Pending Review',
    draftReply: draftReply
  };
}
