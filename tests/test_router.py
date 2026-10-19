"""Unit tests for DiscomRouter.

Tests district canonical mapping, English/Hindi aliases, locality resolution,
confidence scoring, and conflicting jurisdiction handling.
"""

import pytest
from uppcl_x_automation.config import load_config
from uppcl_x_automation.router import DiscomRouter


@pytest.fixture
def router():
    config = load_config()
    return DiscomRouter(config)


def test_route_pvvnl_noida_alias(router):
    text = "@UPPCLLKO Noida Sector 62 me light nahi hai subah se."
    res = router.route(text)
    assert res.discom == "PVVNL"
    assert res.district == "GAUTAM BUDH NAGAR"
    assert res.zone == "NOIDA"
    assert res.discom_handle == "@PVVNLHQ"
    assert res.confidence in ("HIGH", "MEDIUM")
    assert res.needs_review is False


def test_route_mvvnl_lucknow_locality(router):
    text = "@mduppcl Gomti Nagar sub station fault, transformer damaged."
    res = router.route(text)
    assert res.discom == "MVVNL"
    assert res.district == "LUCKNOW"
    assert res.zone == "LESA"
    assert res.discom_handle == "@MVVNLHQ"
    assert res.needs_review is False


def test_route_puvvnl_varanasi_hindi(router):
    text = "@ChairmanUppcl बनारस अस्सी घाट के पास बिजली कटौती चल रही है।"
    res = router.route(text)
    assert res.discom == "PuVVNL"
    assert res.district == "VARANASI"
    assert res.zone == "VARANASI-1"
    assert res.discom_handle == "@PuVVNLHQ"
    assert res.needs_review is False


def test_route_dvvnl_agra(router):
    text = "@UPPCLLKO Agra Sanjay Place market me power supply off hai."
    res = router.route(text)
    assert res.discom == "DVVNL"
    assert res.district == "AGRA"
    assert res.discom_handle == "@dvvnlhq"
    assert res.needs_review is False


def test_route_kesco_kanpur_urban(router):
    text = "@UPPCLLKO Kanpur city Govind Nagar me 11KV line breakdown."
    res = router.route(text)
    assert res.discom == "KESCO"
    assert res.district == "KANPUR CITY"
    assert res.discom_handle == "@KESCoHQ"
    assert res.needs_review is False


def test_route_discom_handle_only(router):
    text = "@UPPCLLKO @PVVNLHQ Power tripping continuously for 4 hours."
    res = router.route(text, mentioned_handles=["@UPPCLLKO", "@PVVNLHQ"])
    assert res.discom == "PVVNL"
    assert res.discom_handle == "@PVVNLHQ"
    assert res.confidence == "MEDIUM"
    assert res.needs_review is False


def test_route_unknown_location(router):
    text = "@UPPCLLKO Light chali gayi hai kab aayegi?"
    res = router.route(text)
    assert res.discom is None
    assert res.confidence == "UNCERTAIN"
    assert res.needs_review is True


def test_route_conflicting_districts(router):
    text = "@UPPCLLKO Comparing electricity outage in Meerut and Gorakhpur today."
    res = router.route(text)
    assert res.confidence == "UNCERTAIN"
    assert res.needs_review is True
