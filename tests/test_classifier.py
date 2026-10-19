"""Unit tests for GrievanceClassifier.

Tests Hindi, English, Hinglish complaint categorization, shift detection,
PR announcement filtering, and appreciation detection.
"""

from datetime import datetime, timezone
import pytest
from uppcl_x_automation.classifier import GrievanceClassifier


@pytest.fixture
def classifier():
    return GrievanceClassifier()


def test_classify_supply_outage_hindi(classifier):
    text = "@UPPCLLKO लखनऊ गोमती नगर में पिछले 6 घंटे से बिजली नहीं आ रही है, कृपया तुरंत सप्लाई चालू कराएं।"
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO"])
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "SUPPLY_OUTAGE"
    assert res.language == "hi"
    assert res.head == "upl"


def test_classify_transformer_damage_hinglish(classifier):
    text = "@aksharmaBharat @mduppcl Hamare gaon me 63 KVA transformer fuk gaya hai. Blast hua tha kal raat."
    res = classifier.classify(text, mentioned_accounts=["@aksharmaBharat", "@mduppcl"])
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "TRANSFORMER_DAMAGE"
    assert res.head == "upm"  # MD UPPCL takes priority in head resolution


def test_classify_billing_english(classifier):
    text = "@UPPCLLKO Received a high bill of Rs 45,000 for a 1-room house. Smart meter recharge overcharged."
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO"])
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "BILL_RELATED"
    assert res.language == "en"


def test_classify_pole_hazard(classifier):
    text = "@UPPCLLKO 11KV wire broken and hanging on main road. Electric current spark noticed."
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO"])
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type in ("POLE_RELATED", "ACCIDENT_PRONE_TO_OCCURED")


def test_classify_appreciation(classifier):
    text = "@UPPCLLKO @mduppcl Thank you so much for resolving the power outage in 20 minutes! Great work team."
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO", "@mduppcl"])
    assert res.is_complaint is False
    assert res.picked_status == "APPRECIATION"
    assert res.complaint_type == ""


def test_classify_pr_announcement(classifier):
    text = "ऊर्जा मंत्री श्री @aksharmaBharat जी ने आज शक्ति भवन में वरिष्ठ अधिकारियों के साथ विभागीय समीक्षा बैठक की।"
    res = classifier.classify(text, mentioned_accounts=["@aksharmaBharat"])
    assert res.is_complaint is False
    assert res.picked_status == "NO"


def test_shift_detection(classifier):
    # 03:00 UTC = 08:30 IST -> MORNING shift
    utc_morning = datetime(2026, 10, 19, 3, 0, 0, tzinfo=timezone.utc)
    _, shift_morning = classifier.get_ist_shift_and_date(utc_morning)
    assert shift_morning == "MORNING"

    # 10:00 UTC = 15:30 IST -> EVENING shift
    utc_evening = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
    _, shift_evening = classifier.get_ist_shift_and_date(utc_evening)
    assert shift_evening == "EVENING"

    # 18:00 UTC = 23:30 IST -> NIGHT shift
    utc_night = datetime(2026, 10, 19, 18, 0, 0, tzinfo=timezone.utc)
    _, shift_night = classifier.get_ist_shift_and_date(utc_night)
    assert shift_night == "NIGHT"


def test_untagged_complaint_detection(classifier):
    text = "Bijli nahi aa rahi hai subah se"
    res = classifier.classify(text, mentioned_accounts=[])
    assert res.untagged_complaint == "Untagged"


def test_classify_row54_kesco_complaint_reply(classifier):
    """Row 54 issue: Official DISCOM replies with polite signoff 'धन्यवाद' MUST NOT be classified as APPRECIATION."""
    text = "@MauryaMax53296 @UPPCLLKO @SKescokanpur @DMKanpur प्रिय उपभोक्ता, संबंधित अधिकारी द्वारा दी गयी जानकारी के अनुसार आपकी पूर्व में दर्ज शिकायत पर KS13102601198 काम चल रहा है। हम आपको शीघ्र ही अपडेट करेंगे अथवा शिकायत की स्थिति की जानकारी हेतु आप 1912 नम्बर पर संपर्क कर सकते है, धन्यवाद। #1912KESCo191026"
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO", "@SKescokanpur", "@DMKanpur"], author_username="KESCoHQ")
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "DISSATISFIED_CONSUMER"
    assert res.confidence >= 0.85


def test_classify_official_discom_resolution_reply(classifier):
    """Official 1912/DISCOM replies stating resolution must be YES complaints, not citizen appreciation."""
    text = "@UPPCLLKO @backup1kk Dear Sir, your complaint has been resolved. For the resolution of any future inconvenience, you may contact our toll-free number 1912. Thank you.@UPPCLLKO @mduppcl @aksharmaBharat @KESCoHQ #GoodGovernance #1912KESCo191026"
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO", "@mduppcl", "@aksharmaBharat", "@KESCoHQ"], author_username="KESCoHQ")
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "DISSATISFIED_CONSUMER"


def test_classify_citizen_polite_request_with_dhanyawad(classifier):
    """Consumer grievance ending with polite 'धन्यवाद' is a complaint, NOT appreciation."""
    text = "@UPPCLLKO हमारे मोहल्ले में 11KV का तार टूट कर सड़क पर झूल रहा है, कृपया तुरंत ठीक कराएं, धन्यवाद।"
    res = classifier.classify(text, mentioned_accounts=["@UPPCLLKO"], author_username="citizen_user")
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "POLE_RELATED"


def test_classify_citizen_ots_request_with_aabhari(classifier):
    """Citizen requesting OTS scheme ending with 'आभारी रहेंगे' is BILL_RELATED, NOT appreciation."""
    text = "@aksharmaBharat @BJP4UP माननीय उर्जा मंत्री जी महोदय आपसे अनुरोध हैं कि बिजली बिल के पुराने बकाए पर एक मुस्त समाधान योजना OTS लाने की कृपा करें जनता हित के लिए जिससे सभी लोगों का पुराना बकाया बिल भरा जा सके महोदय सभी आपके आभारी रहेंगे 🙏"
    res = classifier.classify(text, mentioned_accounts=["@aksharmaBharat", "@BJP4UP"], author_username="AshokVermayfxc")
    assert res.is_complaint is True
    assert res.picked_status == "YES"
    assert res.complaint_type == "BILL_RELATED"


def test_classify_genuine_hindi_appreciation(classifier):
    """Authentic citizen appreciation when power is restored."""
    text = "@MVVNLHQ @UPPCLLKO बिजली आ गई है धन्यवाद"
    res = classifier.classify(text, mentioned_accounts=["@MVVNLHQ", "@UPPCLLKO"], author_username="Ajayverma_lko")
    assert res.is_complaint is False
    assert res.picked_status == "APPRECIATION"
    assert res.complaint_type == ""

