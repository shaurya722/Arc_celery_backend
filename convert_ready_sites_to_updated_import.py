#!/usr/bin/env python3
"""
Convert the "[READY] Collection Sites and Events Import(...).csv" format into the
`Updated_Sites_Import__111.csv` schema (the one consumed by `import_sites_script.py`).

Usage:
  python3 convert_ready_sites_to_updated_import.py \
    --input "[READY] Collection Sites and Events Import(Sheet1) - [READY] Collection Sites and Events Import(Sheet1).csv" \
    --output Updated_Sites_Import__111_from_READY.csv
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from typing import Optional


OUT_HEADER = [
    "site_name",
    "census_year",
    "community_name",
    "site_type",
    "operator_type",
    "service_partner",
    "address_line_1",
    "address_line_2",
    "address_city",
    "address_postal_code",
    "region",
    "service_area",
    "address_latitude",
    "address_longitude",
    "latitude",
    "longitude",
    "is_active",
    "event_approved",
    "site_start_date",
    "site_end_date",
    "program_paint",
    "program_paint_start_date",
    "program_paint_end_date",
    "program_lights",
    "program_lights_start_date",
    "program_lights_end_date",
    "program_solvents",
    "program_solvents_start_date",
    "program_solvents_end_date",
    "program_pesticides",
    "program_pesticides_start_date",
    "program_pesticides_end_date",
    "program_fertilizers",
    "program_fertilizers_start_date",
    "program_fertilizers_end_date",
]


def _truthy(v: str) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "t")


def _to_bool_str(v: str) -> str:
    return "true" if _truthy(v) else "false"


def _parse_mmddyyyy(d: str) -> Optional[datetime]:
    if not d:
        return None
    s = str(d).strip()
    if not s:
        return None
    # Accept M/D/YYYY and MM/DD/YYYY
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _to_iso_date(d: str) -> str:
    dt = _parse_mmddyyyy(d)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%dT00:00:00")


def _site_type(collection_site_type: str) -> str:
    # Model choices: "Collection Site" or "Event"
    t = (collection_site_type or "").strip().lower()
    if "event" in t:
        return "Event"
    return "Collection Site"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--census-year", type=int, default=None, help="Force census_year column to this value (e.g. 2000).")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8", newline="") as f_in, open(
        args.output, "w", encoding="utf-8", newline=""
    ) as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=OUT_HEADER)
        writer.writeheader()

        for row in reader:
            # Programs in READY file:
            # - "Paints and Coatings" / "Paints and Coatings2" (duplicate) => paint
            # - "Lights" / "Lights3" (duplicate) => lights
            # - "Solvents", "Pesticides", "Fertilizers"
            paint_flag = _truthy(row.get("Paints and Coatings") or "") or _truthy(row.get("Paints and Coatings2") or "")
            lights_flag = _truthy(row.get("Lights") or "") or _truthy(row.get("Lights3") or "")
            solvents_flag = _truthy(row.get("Solvents") or "")
            pesticides_flag = _truthy(row.get("Pesticides") or "")
            fertilizers_flag = _truthy(row.get("Fertilizers") or "")

            # Dates: prefer program-specific start/end when present, otherwise fall back to site dates.
            site_start = _to_iso_date(row.get("Start Date - Paints and Coating") or "")
            site_end = _to_iso_date(row.get("End Date - Paints and Coatings") or "")

            out = {
                "site_name": (row.get("Collection Site Name") or "").strip(),
                "census_year": str(args.census_year) if args.census_year is not None else "",
                "community_name": (row.get("Community") or "").strip(),
                "site_type": _site_type(row.get("Collection Site Type") or ""),
                "operator_type": (row.get("Operator Type") or "").strip(),
                "service_partner": (row.get("Service Partner") or "").strip(),
                "address_line_1": (row.get("Address Line 1") or "").strip(),
                "address_line_2": (row.get("Address Line 2") or "").strip(),
                "address_city": (row.get("Address City") or "").strip(),
                "address_postal_code": (row.get("Address Postal / Zip Code") or "").strip(),
                "region": (row.get("Region/District") or "").strip(),
                "service_area": (row.get("Service Area") or "").strip(),
                "address_latitude": (row.get("Address Latitude") or "").strip(),
                "address_longitude": (row.get("Address Longitude") or "").strip(),
                "latitude": (row.get("Address Latitude") or "").strip(),
                "longitude": (row.get("Address Longitude") or "").strip(),
                "is_active": "true",
                "event_approved": "true" if _site_type(row.get("Collection Site Type") or "") == "Event" else "false",
                "site_start_date": site_start,
                "site_end_date": site_end,
                "program_paint": "true" if paint_flag else "false",
                "program_paint_start_date": _to_iso_date(row.get("Start Date - Paints and Coating") or ""),
                "program_paint_end_date": _to_iso_date(row.get("End Date - Paints and Coatings") or ""),
                "program_lights": "true" if lights_flag else "false",
                "program_lights_start_date": _to_iso_date(row.get("Lights - Start Date") or ""),
                "program_lights_end_date": _to_iso_date(row.get("Lights - End Date") or ""),
                "program_solvents": "true" if solvents_flag else "false",
                "program_solvents_start_date": _to_iso_date(row.get("Solvents - Start Date") or ""),
                "program_solvents_end_date": _to_iso_date(row.get("Solvents - End Date") or ""),
                "program_pesticides": "true" if pesticides_flag else "false",
                "program_pesticides_start_date": _to_iso_date(row.get("Pesticides - Start Date") or ""),
                "program_pesticides_end_date": _to_iso_date(row.get("Pesticides - End Date") or ""),
                "program_fertilizers": "true" if fertilizers_flag else "false",
                "program_fertilizers_start_date": _to_iso_date(row.get("Fertilizers - Start Date") or ""),
                "program_fertilizers_end_date": _to_iso_date(row.get("Fertilizers - End Date") or ""),
            }

            # Ensure required fields exist (importer will error on truly missing address_line_1/city/etc)
            writer.writerow(out)


if __name__ == "__main__":
    main()

