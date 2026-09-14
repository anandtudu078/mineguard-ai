"""The India / MMDR reference rule pack.

This is *data*, not code. Nothing in the domain model knows about India, the
MMDR Act or a March fiscal year - this module simply supplies one jurisdiction's
worth of minerals, obligation rules and demo concessions so the platform has
something meaningful to show on first run.

IMPORTANT
    Every rate, deadline and entity below is an **illustrative default for
    development**. Royalty rates, filing deadlines and penalty provisions change
    by notification. Verify against the current statute before relying on any of
    it in production.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from app.models.enums import (
    HolderEntityType,
    LeaseStatus,
    LeaseType,
    LicenceType,
    MineralCategory,
    ObligationCategory,
    Recurrence,
    RoyaltyBasis,
)

# ---------------------------------------------------------------------------
# Minerals
# ---------------------------------------------------------------------------
MINERALS: list[dict[str, Any]] = [
    {
        "code": "IRON_ORE",
        "name": "Iron Ore",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "15.0000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Haematite and magnetite ore. Major mineral, central royalty schedule.",
    },
    {
        "code": "BAUXITE",
        "name": "Bauxite",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "0.5000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Aluminium ore. Notably low ad valorem rate under the current schedule.",
    },
    {
        "code": "LIMESTONE",
        "name": "Limestone",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "15.0000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Cement and steel grade limestone.",
    },
    {
        "code": "MANGANESE",
        "name": "Manganese Ore",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "15.0000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Manganese ore for ferro-alloy production.",
    },
    {
        "code": "CHROMITE",
        "name": "Chromite",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "15.0000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Chromium ore, chiefly from the Sukinda valley.",
    },
    {
        "code": "COPPER_ORE",
        "name": "Copper Ore",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "4.6200",
        "royalty_unit": "percent_of_sale_value",
        "description": "Copper concentrates and ore.",
    },
    {
        "code": "GRAPHITE",
        "name": "Graphite",
        "category": MineralCategory.MAJOR,
        "royalty_basis": RoyaltyBasis.AD_VALOREM,
        "royalty_rate": "15.0000",
        "royalty_unit": "percent_of_sale_value",
        "description": "Natural graphite, flake and amorphous.",
    },
    {
        "code": "DOLOMITE",
        "name": "Dolomite",
        "category": MineralCategory.MINOR,
        "royalty_basis": RoyaltyBasis.SPECIFIC,
        "royalty_rate": "55.0000",
        "royalty_unit": "INR_per_tonne",
        "description": "Minor mineral; rates set by state rules.",
    },
    {
        "code": "SILICA_SAND",
        "name": "Silica Sand",
        "category": MineralCategory.MINOR,
        "royalty_basis": RoyaltyBasis.SPECIFIC,
        "royalty_rate": "40.0000",
        "royalty_unit": "INR_per_tonne",
        "description": "Minor mineral used in glass and foundry industries.",
    },
    {
        "code": "GRANITE",
        "name": "Granite (Dimension Stone)",
        "category": MineralCategory.MINOR,
        "royalty_basis": RoyaltyBasis.SPECIFIC,
        "royalty_rate": "120.0000",
        "royalty_unit": "INR_per_cubic_metre",
        "description": "Dimension stone; state-controlled minor mineral.",
    },
]

# ---------------------------------------------------------------------------
# Obligation rules
# ---------------------------------------------------------------------------
# Offsets are days after the reporting period ends. A 92-day offset from a
# 31 March year end lands on 1 July, which is the familiar annual return date.
_MAJOR_LEASE_TYPES = [LeaseType.MINING_LEASE.value, LeaseType.COMPOSITE_LICENCE.value]
_ALL_LEASE_TYPES: list[str] = []
_MAJOR_MINERALS = [MineralCategory.MAJOR.value]

OBLIGATIONS: list[dict[str, Any]] = [
    {
        "code": "MMDR_MONTHLY_PRODUCTION_RETURN",
        "title": "Monthly return of production and dispatches",
        "description": (
            "Monthly statement of mineral raised, dispatched and stocked, filed "
            "with the state mining authority."
        ),
        "category": ObligationCategory.RETURN_FILING,
        "legal_reference": "MCDR Rule 26; state mineral concession rules",
        "jurisdiction": "central",
        "recurrence": Recurrence.MONTHLY,
        "due_days_after_period_end": 15,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "penalty_note": "Late filing attracts a penalty and can suspend dispatch permits.",
    },
    {
        "code": "ROYALTY_MONTHLY",
        "title": "Royalty payment for mineral dispatched",
        "description": "Royalty on the sale value or quantity of mineral dispatched.",
        "category": ObligationCategory.PAYMENT,
        "legal_reference": "MMDR Act s.9",
        "jurisdiction": "central",
        "recurrence": Recurrence.MONTHLY,
        "due_days_after_period_end": 15,
        "requires_payment": True,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Simple interest accrues on late royalty; recovery may follow.",
    },
    {
        "code": "DMFT_CONTRIBUTION_MONTHLY",
        "title": "District Mineral Foundation contribution",
        "description": (
            "Contribution to the District Mineral Foundation, levied as a "
            "percentage of royalty for the benefit of affected districts."
        ),
        "category": ObligationCategory.PAYMENT,
        "legal_reference": "MMDR Act s.9B",
        "jurisdiction": "central",
        "recurrence": Recurrence.MONTHLY,
        "due_days_after_period_end": 15,
        "requires_payment": True,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Unpaid DMFT is recovered as arrears of land revenue.",
    },
    {
        "code": "NMET_CONTRIBUTION_MONTHLY",
        "title": "National Mineral Exploration Trust contribution",
        "description": "Contribution to NMET, levied as a percentage of royalty.",
        "category": ObligationCategory.PAYMENT,
        "legal_reference": "MMDR Act s.9C",
        "jurisdiction": "central",
        "recurrence": Recurrence.MONTHLY,
        "due_days_after_period_end": 15,
        "requires_payment": True,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Recoverable as arrears of land revenue.",
    },
    {
        "code": "MCDR_ANNUAL_RETURN",
        "title": "Annual return of mineral production",
        "description": (
            "Consolidated annual return covering production, dispatch, waste "
            "dumping and conservation of minerals."
        ),
        "category": ObligationCategory.RETURN_FILING,
        "legal_reference": "MCDR Rule 26",
        "jurisdiction": "central",
        "recurrence": Recurrence.ANNUAL,
        "due_days_after_period_end": 92,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "penalty_note": "Non-filing is a violation reportable to the regional controller.",
    },
    {
        "code": "EC_COMPLIANCE_HALF_YEARLY",
        "title": "Environmental clearance compliance report",
        "description": (
            "Six-monthly compliance report against the conditions of the "
            "environmental clearance, filed with the regulator."
        ),
        "category": ObligationCategory.ENVIRONMENT,
        "legal_reference": "EIA Notification 2006, condition of EC",
        "jurisdiction": "central",
        "recurrence": Recurrence.HALF_YEARLY,
        "due_days_after_period_end": 30,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Non-compliance can trigger closure directions and prosecution.",
    },
    {
        "code": "PMCP_ANNUAL_REPORT",
        "title": "Progressive mine closure plan annual report",
        "description": (
            "Annual report on implementation of the progressive mine closure "
            "plan, including financial assurance status."
        ),
        "category": ObligationCategory.ENVIRONMENT,
        "legal_reference": "MCDR Rule 23",
        "jurisdiction": "central",
        "recurrence": Recurrence.ANNUAL,
        "due_days_after_period_end": 60,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "penalty_note": "Inadequate closure provisioning blocks lease transfer or renewal.",
    },
    {
        "code": "CSR_ANNUAL_REPORT",
        "title": "Mining CSR annual report",
        "description": (
            "Annual report of corporate social responsibility spend in the "
            "affected area around the mine."
        ),
        "category": ObligationCategory.SOCIAL,
        "legal_reference": "MMDR Act s.9C; Companies Act s.135",
        "jurisdiction": "central",
        "recurrence": Recurrence.ANNUAL,
        "due_days_after_period_end": 120,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "applies_to_mineral_categories": _MAJOR_MINERALS,
        "penalty_note": "Unspent CSR obligations must be transferred to a designated fund.",
    },
    {
        "code": "DGMS_QUARTERLY_STATISTICS",
        "title": "Quarterly mine safety statistics",
        "description": (
            "Quarterly statistics on employment, accidents and occupational "
            "health reported to the Directorate General of Mines Safety."
        ),
        "category": ObligationCategory.SAFETY,
        "legal_reference": "Mines Act 1952; DGMS circulars",
        "jurisdiction": "central",
        "recurrence": Recurrence.QUARTERLY,
        "due_days_after_period_end": 15,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Failure to report notifiable accidents is a serious offence.",
    },
    {
        "code": "GROUND_WATER_COMPLIANCE",
        "title": "Ground water abstraction compliance",
        "description": (
            "Half-yearly return of ground water abstraction against the "
            "granted NOC, with piezometer readings."
        ),
        "category": ObligationCategory.ENVIRONMENT,
        "legal_reference": "Ground Water regulation; NOC conditions",
        "jurisdiction": "central",
        "recurrence": Recurrence.HALF_YEARLY,
        "due_days_after_period_end": 30,
        "applies_to_lease_types": _ALL_LEASE_TYPES,
        "penalty_note": "Excess abstraction voids the NOC and invites closure.",
    },
    {
        "code": "IBM_STAR_RATING_ANNUAL",
        "title": "Star rating of mines submission",
        "description": (
            "Annual self-assessment for the star rating of mines, covering "
            "scientific mining and sustainable development parameters."
        ),
        "category": ObligationCategory.REPORTING,
        "legal_reference": "IBM star rating scheme",
        "jurisdiction": "central",
        "recurrence": Recurrence.ANNUAL,
        "due_days_after_period_end": 90,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "penalty_note": "A low star rating affects statutory clearances and financing.",
    },
    {
        "code": "MINE_CLOSURE_FINAL_REPORT",
        "title": "Final mine closure report",
        "description": (
            "One-time closure report filed when the mine is finally closed, "
            "with evidence of reclamation and rehabilitation."
        ),
        "category": ObligationCategory.ENVIRONMENT,
        "legal_reference": "MCDR Rule 23(5)",
        "jurisdiction": "central",
        "recurrence": Recurrence.ONE_TIME,
        "due_days_after_period_end": 0,
        "applies_to_lease_types": _MAJOR_LEASE_TYPES,
        "penalty_note": "Closure without an approved report leaves the lessee liable.",
    },
]

# ---------------------------------------------------------------------------
# Demo holders
# ---------------------------------------------------------------------------
# All entities below are fictitious. Registration numbers use an obviously
# synthetic prefix so they cannot be mistaken for real identifiers.
HOLDERS: list[dict[str, Any]] = [
    {
        "name": "Deccan Mineral Resources Pvt Ltd",
        "entity_type": HolderEntityType.COMPANY,
        "registration_number": "DEMO-CIN-000001",
        "tax_identifier": "DEMOAAACD1234A1Z0",
        "contact_person": "R. Kulkarni",
        "email": "compliance@deccan-mineral.example",
        "phone": "+91-80-0000-0001",
        "address_line": "Plot 14, Industrial Estate, Hosapete",
        "district": "Vijayanagara",
        "state": "Karnataka",
    },
    {
        "name": "Sahyadri Iron & Steel Limited",
        "entity_type": HolderEntityType.COMPANY,
        "registration_number": "DEMO-CIN-000002",
        "tax_identifier": "DEMOAAACS5678B1Z1",
        "contact_person": "P. Deshmukh",
        "email": "statutory@sahyadri-steel.example",
        "phone": "+91-20-0000-0002",
        "address_line": "Tower B, Kalyani Nagar",
        "district": "Pune",
        "state": "Maharashtra",
    },
    {
        "name": "Vindhya Bauxite Cooperative Society",
        "entity_type": HolderEntityType.COOPERATIVE,
        "registration_number": "DEMO-COOP-000003",
        "contact_person": "S. Meena",
        "email": "board@vindhya-coop.example",
        "phone": "+91-771-000-0003",
        "address_line": "Cooperative Bhavan, Main Road",
        "district": "Baloda Bazar",
        "state": "Chhattisgarh",
    },
    {
        "name": "GRK Stone Aggregates LLP",
        "entity_type": HolderEntityType.JOINT_VENTURE,
        "registration_number": "DEMO-LLP-000004",
        "tax_identifier": "DEMOAAAFG9012C1Z2",
        "contact_person": "A. Reddy",
        "email": "operations@grk-aggregates.example",
        "phone": "+91-40-0000-0004",
        "address_line": "Survey 88, Gachibowli",
        "district": "Hyderabad",
        "state": "Telangana",
    },
]


def _metres_per_degree(lat_degrees: float) -> tuple[float, float]:
    """Local metres per degree of latitude and longitude on the WGS84 spheroid.

    The standard series expansion, accurate to well under a metre. A single
    global constant instead leaves a systematic ~0.5% area bias at Indian
    latitudes, which would read as a boundary error in every lease at once.
    """
    phi = math.radians(lat_degrees)
    metres_lat = (
        111132.92
        - 559.82 * math.cos(2 * phi)
        + 1.175 * math.cos(4 * phi)
        - 0.0023 * math.cos(6 * phi)
    )
    metres_lon = (
        111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)
    )
    return metres_lat, metres_lon


def lease_box(
    lat: float,
    lon: float,
    area_hectares: float,
    *,
    area_scale: float = 1.0,
) -> dict[str, Any]:
    """A square-ish lease footprint whose surveyed area matches the deed area.

    The side length is derived from the stated area rather than hardcoded, so
    the boundary PostGIS measures lines up with the area recorded in the lease
    deed. Hand-picked offsets drift out of agreement with the stated figure and
    make the survey-vs-deed reconciliation look broken instead of useful.

    ``area_scale`` deliberately changes the enclosed area, so ``area_scale=1.05``
    yields a lease surveyed at 5% more than it was granted for. It scales the
    area rather than the side length, because area is the number a reader has in
    mind, and side length goes as its square root.

    Emitted as a *Polygon*, matching what the map draw tool sends. A GeoJSON
    MultiPolygon needs four levels of nesting (polygons -> rings -> positions),
    and ST_Multi in the write path already promotes a Polygon for us, so there
    is no reason to hand-build the deeper form and risk getting it wrong.
    """
    # A square of the given area, so each side is the square root of the area.
    side_metres = math.sqrt(area_hectares * 10_000.0 * area_scale)
    metres_lat, metres_lon = _metres_per_degree(lat)
    half_lat = (side_metres / 2.0) / metres_lat
    half_lon = (side_metres / 2.0) / metres_lon

    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon - half_lon, lat - half_lat],
                [lon + half_lon, lat - half_lat],
                [lon + half_lon, lat + half_lat],
                [lon - half_lon, lat + half_lat],
                [lon - half_lon, lat - half_lat],
            ]
        ],
    }


def _licences_for(
    expiry_offsets: dict[str, int],
    authority_by_type: dict[str, str],
    today: date,
) -> list[dict[str, Any]]:
    """Build clearances from a mapping of licence type to expiry offset in days.

    Reference numbers are derived only from the licence type so they stay stable
    across reseeds: the seed upserts clearances by reference, so a reference that
    shifted with today's date would duplicate records instead of refreshing them.
    """
    licences: list[dict[str, Any]] = []
    for licence_type, offset in expiry_offsets.items():
        valid_to = today + timedelta(days=offset)
        issued = valid_to - timedelta(days=1825)
        licences.append(
            {
                "licence_type": LicenceType(licence_type),
                "authority": authority_by_type.get(licence_type, "State Authority"),
                "reference_number": f"DEMO/{licence_type.upper().replace('_', '-')}",
                "issued_date": issued,
                "valid_from": issued,
                "valid_to": valid_to,
                "is_mandatory": True,
            }
        )
    return licences


def lease_definitions(today: date) -> list[dict[str, Any]]:
    """Demo concessions spanning several states and compliance postures.

    Expiry offsets are relative to ``today`` so the dashboard always shows a
    mix of healthy, expiring and lapsed positions whenever the seed is run.
    """
    spcb = "State Pollution Control Board"
    authorities = {
        LicenceType.ENVIRONMENTAL_CLEARANCE.value: "MoEFCC",
        LicenceType.FOREST_CLEARANCE.value: "MoEFCC (Forest Advisory Committee)",
        LicenceType.CONSENT_TO_OPERATE.value: spcb,
        LicenceType.MINING_PLAN_APPROVAL.value: "Indian Bureau of Mines",
        LicenceType.GROUND_WATER_NTOC.value: "Central Ground Water Authority",
        LicenceType.EXPLOSIVE_LICENCE.value: "Petroleum & Explosives Safety Organisation",
        LicenceType.LEASE_DEED.value: "State Department of Mines & Geology",
        LicenceType.DRONE_SURVEY_APPROVAL.value: "Directorate General of Civil Aviation",
    }

    return [
        {
            "lease_number": "ML/KA/2016/0042",
            "name": "Hosapete Iron Ore Block A",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 0,
            "mineral_code": "IRON_ORE",
            "area_hectares": "112.4000",
            "village": "Kudligi",
            "district": "Vijayanagara",
            "state": "Karnataka",
            "lat": 15.27,
            "lon": 76.39,
            "grant_date": today - timedelta(days=3300),
            "effective_from": today - timedelta(days=3300),
            "effective_to": today + timedelta(days=900),
            "annual_production_tonnes": "1850000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 820,
                    LicenceType.FOREST_CLEARANCE.value: 1200,
                    LicenceType.CONSENT_TO_OPERATE.value: 210,
                    LicenceType.MINING_PLAN_APPROVAL.value: 430,
                    LicenceType.LEASE_DEED.value: 900,
                },
                authorities,
                today,
            ),
        },
        {
            # Expiring soon: drives the renewal queue.
            "lease_number": "ML/KA/2011/0117",
            "name": "Sandur Manganese Lease",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.PENDING_RENEWAL,
            "holder_index": 1,
            "mineral_code": "MANGANESE",
            "area_hectares": "86.2500",
            "village": "Sandur",
            "district": "Ballari",
            "state": "Karnataka",
            "lat": 15.14,
            "lon": 76.92,
            "grant_date": today - timedelta(days=5200),
            "effective_from": today - timedelta(days=5200),
            "effective_to": today + timedelta(days=47),
            "annual_production_tonnes": "420000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 380,
                    LicenceType.CONSENT_TO_OPERATE.value: 38,
                    LicenceType.MINING_PLAN_APPROVAL.value: 47,
                    LicenceType.LEASE_DEED.value: 47,
                },
                authorities,
                today,
            ),
        },
        {
            # Lapsed term: should read as critical.
            "lease_number": "ML/OD/2009/0231",
            "name": "Keonjhar Chromite Block II",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 1,
            "mineral_code": "CHROMITE",
            "area_hectares": "204.7800",
            "village": "Sukinda",
            "district": "Jajpur",
            "state": "Odisha",
            "lat": 21.06,
            "lon": 85.79,
            "grant_date": today - timedelta(days=5800),
            "effective_from": today - timedelta(days=5800),
            "effective_to": today - timedelta(days=34),
            "annual_production_tonnes": "610000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: -95,
                    LicenceType.CONSENT_TO_OPERATE.value: 26,
                    LicenceType.MINING_PLAN_APPROVAL.value: -240,
                    LicenceType.LEASE_DEED.value: -34,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "ML/OD/2018/0503",
            "name": "Sundargarh Iron Ore Lease",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 0,
            "mineral_code": "IRON_ORE",
            "area_hectares": "341.9000",
            # Surveyed area is 5% beyond the area granted. Real leases drift this
            # way, and it is exactly the kind of gap the register must surface.
            "area_variance": 1.05,
            "village": "Barsuan",
            "district": "Sundargarh",
            "state": "Odisha",
            "lat": 22.12,
            "lon": 84.03,
            "grant_date": today - timedelta(days=2400),
            "effective_from": today - timedelta(days=2400),
            "effective_to": today + timedelta(days=3100),
            "annual_production_tonnes": "4200000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 1450,
                    LicenceType.FOREST_CLEARANCE.value: 980,
                    LicenceType.CONSENT_TO_OPERATE.value: 300,
                    LicenceType.MINING_PLAN_APPROVAL.value: 700,
                    LicenceType.GROUND_WATER_NTOC.value: 74,
                    LicenceType.LEASE_DEED.value: 3100,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "CL/JH/2021/0012",
            "name": "West Singhbhum Composite Licence",
            "lease_type": LeaseType.COMPOSITE_LICENCE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 2,
            "mineral_code": "IRON_ORE",
            "area_hectares": "158.6000",
            "village": "Noamundi",
            "district": "West Singhbhum",
            "state": "Jharkhand",
            "lat": 22.40,
            "lon": 85.80,
            "grant_date": today - timedelta(days=1500),
            "effective_from": today - timedelta(days=1500),
            "effective_to": today + timedelta(days=2100),
            "annual_production_tonnes": "890000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 610,
                    LicenceType.FOREST_CLEARANCE.value: 610,
                    LicenceType.CONSENT_TO_OPERATE.value: 155,
                    LicenceType.MINING_PLAN_APPROVAL.value: 400,
                    LicenceType.LEASE_DEED.value: 2100,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "ML/CG/2014/0078",
            "name": "Dantewada Bauxite Plateau",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 2,
            "mineral_code": "BAUXITE",
            "area_hectares": "612.3000",
            "village": "Bacheli",
            "district": "Dantewada",
            "state": "Chhattisgarh",
            "lat": 18.90,
            "lon": 81.35,
            "grant_date": today - timedelta(days=4100),
            "effective_from": today - timedelta(days=4100),
            "effective_to": today + timedelta(days=82),
            "annual_production_tonnes": "3100000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 240,
                    LicenceType.FOREST_CLEARANCE.value: -120,
                    LicenceType.CONSENT_TO_OPERATE.value: 82,
                    LicenceType.MINING_PLAN_APPROVAL.value: 82,
                    LicenceType.LEASE_DEED.value: 82,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "QL/RJ/2020/0441",
            "name": "Ajmer Dolomite Quarry",
            "lease_type": LeaseType.QUARRY_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 3,
            "mineral_code": "DOLOMITE",
            "area_hectares": "24.7000",
            "village": "Kishangarh",
            "district": "Ajmer",
            "state": "Rajasthan",
            "lat": 26.45,
            "lon": 74.64,
            "grant_date": today - timedelta(days=1900),
            "effective_from": today - timedelta(days=1900),
            "effective_to": today + timedelta(days=1750),
            "annual_production_tonnes": "76000.000",
            "licences": _licences_for(
                {
                    LicenceType.CONSENT_TO_OPERATE.value: 340,
                    LicenceType.MINING_PLAN_APPROVAL.value: 900,
                    LicenceType.LEASE_DEED.value: 1750,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "QL/AP/2019/0303",
            "name": "Kurnool Silica Sand Quarry",
            "lease_type": LeaseType.QUARRY_LEASE,
            "status": LeaseStatus.SUSPENDED,
            "holder_index": 3,
            "mineral_code": "SILICA_SAND",
            "area_hectares": "31.2000",
            "village": "Nandyal",
            "district": "Kurnool",
            "state": "Andhra Pradesh",
            "lat": 15.83,
            "lon": 78.04,
            "grant_date": today - timedelta(days=2600),
            "effective_from": today - timedelta(days=2600),
            "effective_to": today + timedelta(days=620),
            "annual_production_tonnes": "0.000",
            "licences": _licences_for(
                {
                    LicenceType.CONSENT_TO_OPERATE.value: -18,
                    LicenceType.MINING_PLAN_APPROVAL.value: 620,
                    LicenceType.LEASE_DEED.value: 620,
                },
                authorities,
                today,
            ),
        },
        {
            "lease_number": "ML/GA/2017/0065",
            "name": "North Goa Limestone Concession",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.ACTIVE,
            "holder_index": 0,
            "mineral_code": "LIMESTONE",
            "area_hectares": "97.0500",
            "village": "Bicholim",
            "district": "North Goa",
            "state": "Goa",
            "lat": 15.60,
            "lon": 73.95,
            "grant_date": today - timedelta(days=2900),
            "effective_from": today - timedelta(days=2900),
            "effective_to": today + timedelta(days=520),
            "annual_production_tonnes": "540000.000",
            "licences": _licences_for(
                {
                    LicenceType.ENVIRONMENTAL_CLEARANCE.value: 520,
                    LicenceType.CONSENT_TO_OPERATE.value: 67,
                    LicenceType.MINING_PLAN_APPROVAL.value: 400,
                    LicenceType.LEASE_DEED.value: 520,
                },
                authorities,
                today,
            ),
        },
        {
            # Newly granted: nothing has come due yet. Exercises the
            # "components excluded" path in the scoring engine.
            "lease_number": "ML/MP/2025/0009",
            "name": "Katni Graphite Block",
            "lease_type": LeaseType.MINING_LEASE,
            "status": LeaseStatus.PENDING,
            "holder_index": 1,
            "mineral_code": "GRAPHITE",
            "area_hectares": "148.9000",
            "village": "Bahoriband",
            "district": "Katni",
            "state": "Madhya Pradesh",
            "lat": 23.83,
            "lon": 80.39,
            "grant_date": today - timedelta(days=25),
            "effective_from": today - timedelta(days=25),
            "effective_to": today + timedelta(days=3600),
            "annual_production_tonnes": None,
            "licences": _licences_for(
                {
                    LicenceType.MINING_PLAN_APPROVAL.value: 3600,
                    LicenceType.LEASE_DEED.value: 3600,
                },
                authorities,
                today,
            ),
        },
    ]
