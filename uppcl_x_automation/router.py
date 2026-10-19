"""Intelligent DISCOM and District Routing Engine for UPPCL.

Maps consumer complaint text, mentioned handles, and location cues to the
appropriate Uttar Pradesh Distribution Company (DISCOM), Zone, and District.
Handles English, Hinglish, and Devanagari Hindi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from uppcl_x_automation.config import AppConfig, DistrictInfo, DiscomInfo


@dataclass
class RoutingResult:
    discom: Optional[str]
    zone: Optional[str]
    district: Optional[str]
    discom_handle: Optional[str]
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW', 'UNCERTAIN'
    reasoning: str
    needs_review: bool


# Prominent sub-district localities, tehsils, and powerhouses mapped to districts
LOCALITY_MAP: Dict[str, str] = {
    # Gautam Budh Nagar / Ghaziabad
    "gomti nagar": "LUCKNOW",
    "gomtinagar": "LUCKNOW",
    "aliganj": "LUCKNOW",
    "indira nagar": "LUCKNOW",
    "hazratganj": "LUCKNOW",
    "jankipuram": "LUCKNOW",
    "indirapuram": "GHAZIABAD",
    "vaishali": "GHAZIABAD",
    "vasundhara": "GHAZIABAD",
    "sahibabad": "GHAZIABAD",
    "crossings republik": "GHAZIABAD",
    "raj nagar": "GHAZIABAD",
    "pari chowk": "GAUTAM BUDH NAGAR",
    "knowledge park": "GAUTAM BUDH NAGAR",
    "greater noida west": "GAUTAM BUDH NAGAR",
    "noida extension": "GAUTAM BUDH NAGAR",
    # Kanpur
    "kalyanpur": "KANPUR CITY",
    "govind nagar": "KANPUR CITY",
    "rawatpur": "KANPUR CITY",
    "kakadeo": "KANPUR CITY",
    "sharda nagar": "KANPUR CITY",
    # Varanasi
    "assighat": "VARANASI",
    "assi ghat": "VARANASI",
    "godowlia": "VARANASI",
    "bhelupur": "VARANASI",
    "sigra": "VARANASI",
    "shivpur": "VARANASI",
    "lahartara": "VARANASI",
    # Prayagraj
    "civil lines prayagraj": "PRAYAGRAJ",
    "civil lines allahabad": "PRAYAGRAJ",
    "katra allahabad": "PRAYAGRAJ",
    "jhusi": "PRAYAGRAJ",
    "naimi": "PRAYAGRAJ",
    # Gorakhpur
    "gorkhnath": "GORAKHPUR",
    "gorakhnath": "GORAKHPUR",
    "taramandal": "GORAKHPUR",
    "medical college gorakhpur": "GORAKHPUR",
    # Agra
    "kamla nagar agra": "AGRA",
    "sanjay place": "AGRA",
    "bodla": "AGRA",
    # Meerut
    "shastri nagar meerut": "MEERUT",
    "modipuram": "MEERUT",
    "partapur": "MEERUT",
    # Jhansi
    "sipri bazar": "JHANSI",
    "sadar bazar jhansi": "JHANSI",
}


class DiscomRouter:
    """Routes electricity grievances to one of the 5 official UP DISCOMs."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.districts: Dict[str, DistrictInfo] = config.districts
        self.aliases: Dict[str, str] = config.district_aliases
        self.discoms: Dict[str, DiscomInfo] = config.discoms

        # Pre-compile regex matchers
        # Sort keys by length descending to match multi-word phrases first (e.g. 'Kanpur Dehat' before 'Kanpur')
        self._compiled_districts: List[Tuple[str, re.Pattern[str], DistrictInfo]] = []
        for name, info in sorted(self.districts.items(), key=lambda x: len(x[0]), reverse=True):
            # If name is ASCII
            if name.isascii():
                pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
            else:
                pattern = re.compile(rf"{re.escape(name)}", re.IGNORECASE)
            self._compiled_districts.append((name, pattern, info))

        self._compiled_aliases: List[Tuple[str, str, re.Pattern[str]]] = []
        for alias, target in sorted(self.aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if alias.isascii():
                pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            else:
                pattern = re.compile(rf"{re.escape(alias)}", re.IGNORECASE)
            self._compiled_aliases.append((alias, target, pattern))

        self._compiled_localities: List[Tuple[str, str, re.Pattern[str]]] = []
        for locality, target in sorted(LOCALITY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = re.compile(rf"\b{re.escape(locality)}\b", re.IGNORECASE)
            self._compiled_localities.append((locality, target, pattern))

    def _get_discom(self, discom_code: Optional[str]) -> Optional[DiscomInfo]:
        """Case-insensitive lookup for DISCOM info."""
        if not discom_code:
            return None
        code_upper = discom_code.upper()
        for k, v in self.discoms.items():
            if k.upper() == code_upper:
                return v
        return None

    def route(self, text: str, mentioned_handles: Optional[List[str]] = None, author_location: Optional[str] = None) -> RoutingResult:
        """Route a complaint post to the appropriate DISCOM.

        Args:
            text: Full text of the complaint post
            mentioned_handles: List of handles mentioned in the post
            author_location: Public location string from the user's profile if available

        Returns:
            RoutingResult containing DISCOM, Zone, District, confidence, and audit trail.
        """
        combined_text = f"{text or ''} {' '.join(mentioned_handles or [])}"
        clean_text = combined_text.strip()

        # Step 1: Check if a specific DISCOM handle was directly mentioned
        mentioned_discoms = set()
        for d_code, d_info in self.discoms.items():
            if d_info.handle.lower() in clean_text.lower():
                mentioned_discoms.add(d_code)

        # Step 2: Check for direct mentions of Canonical Districts in post text
        found_districts: List[Tuple[str, DistrictInfo, str]] = []
        for d_name, pattern, d_info in self._compiled_districts:
            if pattern.search(clean_text):
                found_districts.append((d_name, d_info, f"canonical district '{d_name}'"))

        # Step 3: Check for District Aliases (English, Hinglish, Devanagari Hindi)
        if not found_districts:
            for alias, target_district, pattern in self._compiled_aliases:
                if pattern.search(clean_text):
                    if target_district in self.districts:
                        d_info = self.districts[target_district]
                        found_districts.append((target_district, d_info, f"alias '{alias}' -> '{target_district}'"))

        # Step 4: Check for prominent localities/powerhouses
        if not found_districts:
            for locality, target_district, pattern in self._compiled_localities:
                if pattern.search(clean_text):
                    if target_district in self.districts:
                        d_info = self.districts[target_district]
                        found_districts.append((target_district, d_info, f"locality '{locality}' -> '{target_district}'"))

        # Step 5: Check author profile location if text search yielded nothing
        if not found_districts and author_location:
            loc_str = author_location.strip()
            for d_name, pattern, d_info in self._compiled_districts:
                if pattern.search(loc_str):
                    found_districts.append((d_name, d_info, f"author profile location '{d_name}'"))
            if not found_districts:
                for alias, target_district, pattern in self._compiled_aliases:
                    if pattern.search(loc_str):
                        if target_district in self.districts:
                            d_info = self.districts[target_district]
                            found_districts.append((target_district, d_info, f"author profile alias '{alias}' -> '{target_district}'"))

        # Evaluate Findings
        # Case A: Exactly one district resolved
        if len(found_districts) == 1:
            district_name, d_info, reason = found_districts[0]
            discom_code = d_info.discom
            discom_obj = self._get_discom(discom_code)
            discom_handle = discom_obj.handle if discom_obj else None

            # If the user also mentioned a specific DISCOM handle, verify agreement
            if mentioned_discoms and discom_code not in mentioned_discoms:
                # Contradiction: text mentions District X belonging to Discom A, but tagged Discom B
                return RoutingResult(
                    discom=discom_code,
                    zone=d_info.zone,
                    district=district_name,
                    discom_handle=discom_handle,
                    confidence="MEDIUM",
                    reasoning=f"District identified as {district_name} ({reason}), but consumer tagged contradictory DISCOM(s): {', '.join(mentioned_discoms)}.",
                    needs_review=True,
                )

            return RoutingResult(
                discom=discom_code,
                zone=d_info.zone,
                district=district_name,
                discom_handle=discom_handle,
                confidence="HIGH",
                reasoning=f"Verified match for {reason} belonging to {discom_code} ({d_info.zone} Zone).",
                needs_review=False,
            )

        # Case B: Multiple districts detected
        if len(found_districts) > 1:
            unique_discoms = {item[1].discom for item in found_districts}
            d_names = [item[0] for item in found_districts]
            if len(unique_discoms) == 1:
                discom_code = list(unique_discoms)[0]
                discom_obj = self._get_discom(discom_code)
                return RoutingResult(
                    discom=discom_code,
                    zone=found_districts[0][1].zone,
                    district=found_districts[0][0],
                    discom_handle=discom_obj.handle if discom_obj else None,
                    confidence="MEDIUM",
                    reasoning=f"Multiple districts detected in same DISCOM ({', '.join(d_names)}). Defaulted to primary match.",
                    needs_review=False,
                )
            # Conflicting DISCOMs
            return RoutingResult(
                discom=None,
                zone=None,
                district=None,
                discom_handle=None,
                confidence="UNCERTAIN",
                reasoning=f"Multiple conflicting districts detected spanning different DISCOMs: {', '.join(d_names)}.",
                needs_review=True,
            )

        # Case C: No district found, but a single official DISCOM handle was directly tagged
        if len(mentioned_discoms) == 1:
            discom_code = list(mentioned_discoms)[0]
            discom_obj = self._get_discom(discom_code)
            return RoutingResult(
                discom=discom_code,
                zone=None,
                district=None,
                discom_handle=discom_obj.handle if discom_obj else None,
                confidence="MEDIUM",
                reasoning=f"No specific district mentioned, but consumer explicitly tagged official DISCOM handle {discom_obj.handle if discom_obj else discom_code}.",
                needs_review=False,
            )

        # Case D: No location information could be found
        return RoutingResult(
            discom=None,
            zone=None,
            district=None,
            discom_handle=None,
            confidence="UNCERTAIN",
            reasoning="No district, city, landmark, or specific DISCOM handle identified in post text or profile.",
            needs_review=True,
        )
