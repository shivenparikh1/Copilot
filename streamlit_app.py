from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from io import BytesIO, StringIO
import re
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Global Sourcing Copilot",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CONFIDENCE_LEVELS = [
    "Verified",
    "Supplier Quote",
    "Public Estimate",
    "AI Estimate",
    "Manual Review Needed",
    "Unavailable Online",
]

CONFIDENCE_SCORE_MAP = {
    "Verified": 5,
    "Supplier Quote": 4,
    "Public Estimate": 3,
    "AI Estimate": 2,
    "Manual Review Needed": 1,
    "Unavailable Online": 1,
}

CONFIDENCE_ALIASES = {
    "estimated": "Public Estimate",
    "ai suggested": "AI Estimate",
    "needs manual review": "Manual Review Needed",
}

CRITICALITY_LEVELS = ["Low", "Medium", "High", "Critical"]

WORKFLOW_PAGES = [
    "Product",
    "Suppliers",
    "Framework",
    "Weights",
    "Dashboard",
    "Notes",
    "Export",
    "News",
]

LEGACY_PAGE_MAP = {
    "Guide": "Product",
    "Product Intake": "Product",
    "Supplier Discovery": "Suppliers",
    "Framework Table": "Framework",
    "Framework Weights": "Weights",
    "Scoring Weights": "Weights",
    "AI Insights": "Notes",
    "Sourcing Notes": "Notes",
    "Recommendation & Export": "Export",
    "Weekly News": "News",
}

SCORECARD_MAIN_COLUMNS = [
    "Supplier",
    "Final Score",
    "Recommendation",
    "Landed / Unit",
    "TCO / Unit",
    "Order TCO",
    "Lead Time Days",
    "Capability Score",
    "Quality Risk",
    "Compliance Risk",
    "Geopolitical Risk",
    "Logistics Risk",
    "Financial Stability",
    "Contract Terms",
    "Data Confidence",
    "Manual Review Flags",
]

DEFAULT_WEIGHTS = {
    "landed_cost": 15,
    "tco": 10,
    "lead_time": 12,
    "capability": 15,
    "quality_risk": 15,
    "compliance": 8,
    "geopolitical_risk": 8,
    "logistics": 7,
    "financial_stability": 5,
    "contract": 5,
}

WEIGHT_LABELS = {
    "landed_cost": "Total Landed Cost",
    "tco": "Total Cost of Ownership",
    "lead_time": "Lead Time",
    "capability": "Supplier Capability",
    "quality_risk": "Quality Risk",
    "compliance": "Compliance",
    "geopolitical_risk": "Geopolitical Risk",
    "logistics": "Logistics Risk",
    "financial_stability": "Financial Stability",
    "contract": "Contract Terms",
}

FIELD_KIND_LABELS = {
    "currency": "Cost input",
    "days": "Lead-time input",
    "number": "Commercial input",
    "risk": "Risk input",
    "score": "Capability input",
    "text": "Reference input",
}

NEWS_TOPICS = {
    "Global sourcing": "global sourcing supply chain procurement tariffs logistics",
    "Tariffs and trade": "tariffs trade policy supply chain sourcing",
    "Logistics": "ocean freight port congestion logistics supply chain",
    "Supplier risk": "supplier risk manufacturing supply chain disruption",
    "Nearshoring": "nearshoring reshoring manufacturing supply chain sourcing",
}

NEWS_LOOKBACK_DAYS = 30

SCORE_EXPLANATIONS = [
    {
        "title": "Total Landed Cost Score",
        "measures": "Direct per-unit cost to get the product to the destination.",
        "subfactors": "Unit cost, freight, tariffs and duties, insurance, customs brokerage, packaging, and warehousing.",
        "direction": "Lower landed cost is better.",
        "calculation": "Total Landed Cost per Unit = Unit Cost + Freight Cost + Tariffs and Duties + Insurance + Customs Brokerage + Packaging + Warehousing. Suppliers are normalized from 1 to 5 across the current comparison set, then converted to 100-point display scores.",
        "why": "A low quote is not enough; this shows the real cost after freight, import, and handling assumptions.",
    },
    {
        "title": "Total Cost of Ownership Score",
        "measures": "The broader unit economics after ownership and risk costs are included.",
        "subfactors": "Total landed cost, quality failure cost, expedite cost, inventory holding cost, supplier switching cost, warranty exposure, stockout risk cost, and requalification cost.",
        "direction": "Lower TCO is better.",
        "calculation": "TCO per Unit = Total Landed Cost per Unit + Quality Failure Cost + Expedite Cost + Inventory Holding Cost + Supplier Switching Cost + Warranty Exposure + Stockout Risk Cost + Requalification Cost. Suppliers are normalized from 1 to 5 across the comparison set.",
        "why": "It prevents a low unit price from hiding quality, inventory, service, and qualification costs.",
    },
    {
        "title": "Lead Time Score",
        "measures": "The expected end-to-end sourcing and replenishment timeline.",
        "subfactors": "Production lead time, raw material lead time, supplier planning time, inspection time, export clearance, transit, customs clearance, receiving, buffer time, and reorder review cycle.",
        "direction": "Lower lead time is better.",
        "calculation": "Total Lead Time = Production Lead Time + Raw Material Lead Time + Planning Time + Inspection Time + Export Clearance + Transit Time + Customs Clearance + Receiving Time + Buffer Time. The scoring basis also considers the reorder review cycle.",
        "why": "Lead time affects working capital, service risk, and how quickly the sourcing plan can respond to demand changes.",
    },
    {
        "title": "Supplier Capability Score",
        "measures": "Whether the supplier can actually perform beyond the attractiveness of the quote.",
        "subfactors": "Volume capability, equipment/process fit, certifications, scalability, engineering support, compliance understanding, documentation ability, backup capacity, factory dependency, relevant industry experience, and existing customer quality.",
        "direction": "Higher capability is better.",
        "calculation": "Capability subfactors are scored 1 to 5 and averaged with editable field weights.",
        "why": "A supplier must be able to meet demand, quality, documentation, and compliance needs over time.",
    },
    {
        "title": "Quality Risk Score",
        "measures": "The likelihood of defects, poor controls, weak inspection, or field issues.",
        "subfactors": "Defect rate, process control, inspection method, quality certifications, traceability, corrective actions, audit results, warranty claims, return rate, and field failure risk.",
        "direction": "Lower risk is better.",
        "calculation": "Risk inputs use a 1 to 5 scale. The score uses Risk-adjusted score = 6 - risk score, then averages the adjusted subfactors.",
        "why": "Quality risk can quickly erase savings through scrap, returns, warranty exposure, and launch delays.",
    },
    {
        "title": "Compliance Risk Score",
        "measures": "Supplier readiness for required product, trade, environmental, labor, and documentation obligations.",
        "subfactors": "Required certifications, product safety compliance, import/export compliance, environmental compliance, labor and ethical sourcing, documentation completeness, restricted material risk, audit readiness, and traceability documentation.",
        "direction": "Higher readiness and lower risk are better.",
        "calculation": "Positive compliance factors use 1 to 5 scoring. Risk factors use Risk-adjusted score = 6 - risk score.",
        "why": "Compliance gaps can block import, delay qualification, or create legal and customer risk.",
    },
    {
        "title": "Geopolitical Risk Score",
        "measures": "Country, policy, sanctions, conflict, currency, and trade exposure.",
        "subfactors": "Tariff exposure, trade war exposure, export controls, sanctions, political instability, military conflict, currency instability, government policy changes, single-country dependency, and friendshoring or nearshoring advantage.",
        "direction": "Lower risk and stronger friendly-region advantage are better.",
        "calculation": "Risk factors use Risk-adjusted score = 6 - risk score. Positive advantage factors use direct 1 to 5 scoring.",
        "why": "Country and trade risk can change landed cost, supply continuity, and customer acceptability.",
    },
    {
        "title": "Logistics Risk Score",
        "measures": "Transportation, import, warehouse, and delivery complexity.",
        "subfactors": "Distance to delivery location, freight mode complexity, port congestion, container availability, customs complexity, HS code uncertainty, import documentation risk, incoterms complexity, 3PL dependency, last-mile complexity, and warehouse requirement.",
        "direction": "Lower logistics risk is better.",
        "calculation": "Risk inputs use Risk-adjusted score = 6 - risk score and are averaged with editable field weights.",
        "why": "Logistics issues often turn into hidden cost, late delivery, and poor launch reliability.",
    },
    {
        "title": "Financial Stability Score",
        "measures": "The supplier's ability to remain solvent, invest, and support the program over time.",
        "subfactors": "Years in business, revenue stability, customer diversity, credit/payment risk, bankruptcy risk, customer overdependence, ability to invest in capacity, and ownership transparency.",
        "direction": "Higher stability and lower financial risk are better.",
        "calculation": "Positive factors use 1 to 5 scoring. Financial risk factors use Risk-adjusted score = 6 - risk score.",
        "why": "A supplier with weak finances can fail during ramp, delay capacity investment, or create continuity risk.",
    },
    {
        "title": "Contract Terms Score",
        "measures": "How favorable and protective the commercial agreement is.",
        "subfactors": "Payment terms, MOQ flexibility, volume discounts, lead-time commitments, service levels, warranty, liability, penalties, IP protection, termination flexibility, capacity reservation, and forecast commitment burden.",
        "direction": "Better terms and lower buyer burden are better.",
        "calculation": "Positive contract factors use 1 to 5 scoring. Burden and risk factors use Risk-adjusted score = 6 - risk score.",
        "why": "Contract terms decide how much risk remains after supplier selection.",
    },
    {
        "title": "Data Confidence Score",
        "measures": "How reliable the supplier data is.",
        "subfactors": "Verified supplier data, supplier-provided quotes, public estimates, AI estimates, manual review needs, and unavailable online data.",
        "direction": "Higher confidence is better, but it does not replace supplier performance.",
        "calculation": "Verified = 5, Supplier Quote = 4, Public Estimate = 3, AI Estimate = 2, Manual Review Needed or Unavailable Online = 1.",
        "why": "Estimated or AI-filled supplier data should not look as reliable as verified supplier evidence.",
    },
    {
        "title": "Manual Review Flags",
        "measures": "Important gaps or risk triggers that need human validation before award.",
        "subfactors": "Missing quality certification data, missing payment terms, missing compliance documentation, lead-time verification, tariff/duty review, unverified capability, low data confidence, high geopolitical risk, high logistics risk, and critical parts without backup suppliers.",
        "direction": "Fewer flags are better.",
        "calculation": "Flags are generated with rule-based checks on missing fields, low confidence, and high risk scores.",
        "why": "Flags keep the scorecard honest by showing what still needs validation.",
    },
]

BLANK_REQUIREMENT = {
    "product_name": "",
    "product_category": "",
    "product_specs": "",
    "quantity": 0,
    "quality_requirements": "",
    "compliance_requirements": "",
    "target_cost": 0.0,
    "required_lead_time": 0,
    "forecasted_demand": 0,
    "approved_materials": "",
    "technical_drawings": "",
    "packaging_requirements": "",
    "delivery_location": "",
    "criticality": "Medium",
}

REQUIREMENT_FIELD_ALIASES = {
    "product_name": ["product name", "product", "part name", "item", "item name", "sku", "component"],
    "product_category": ["product category", "category", "commodity", "sourcing category", "product type"],
    "product_specs": [
        "product specs",
        "specs",
        "specification",
        "specifications",
        "description",
        "technical specification",
        "product description",
    ],
    "quantity": ["quantity", "order quantity", "qty", "rfq quantity", "purchase quantity"],
    "quality_requirements": ["quality requirements", "quality", "qc requirements", "inspection requirements"],
    "compliance_requirements": [
        "compliance requirements",
        "compliance",
        "regulatory requirements",
        "certifications required",
        "required certifications",
    ],
    "target_cost": ["target cost", "target price", "target unit cost", "budget", "cost target"],
    "required_lead_time": [
        "required lead time",
        "target lead time",
        "lead time requirement",
        "required lead time days",
    ],
    "forecasted_demand": ["forecasted demand", "forecast demand", "annual demand", "demand forecast"],
    "approved_materials": ["approved materials", "material", "materials", "approved material"],
    "technical_drawings": [
        "technical drawings",
        "technical drawing",
        "drawing",
        "drawing link",
        "cad",
        "drawing notes",
    ],
    "packaging_requirements": ["packaging requirements", "packaging", "packing requirements"],
    "delivery_location": ["delivery location", "ship to", "destination", "delivery address", "final destination"],
    "criticality": ["criticality", "criticality level", "priority", "part criticality"],
}

SUPPLIER_FIELD_ALIASES = {
    "name": ["supplier", "supplier name", "vendor", "vendor name", "manufacturer", "manufacturer name"],
    "country": ["country", "supplier country", "manufacturing country"],
    "region": ["region", "supplier region", "manufacturing region"],
    "website": ["website", "supplier website", "url", "web site"],
    "product_match": ["product match", "capability match", "match", "supplier capability notes"],
    "certifications": ["certifications", "supplier certifications", "certification"],
    "annual_capacity": ["annual capacity", "capacity", "estimated annual capacity", "production capacity"],
    "customer_notes": ["customer notes", "notes", "supplier notes", "comments"],
    "confidence_level": ["confidence level", "confidence", "data confidence", "source confidence"],
}

SAMPLE_REQUIREMENT = {
    "product_name": "Precision aluminum motor housing",
    "product_category": "CNC machined components",
    "product_specs": "6061-T6 aluminum, anodized finish, +/-0.05 mm tolerance, RoHS compliant",
    "quantity": 42000,
    "quality_requirements": "PPAP sample approval, Cpk > 1.33, 100% dimensional report",
    "compliance_requirements": "RoHS, REACH, conflict minerals declaration",
    "target_cost": 9.25,
    "required_lead_time": 62,
    "forecasted_demand": 168000,
    "approved_materials": "6061-T6 aluminum, clear anodizing, approved insert hardware",
    "technical_drawings": "Drawing package GSC-MH-4821 Rev C; supplier NDA required before release",
    "packaging_requirements": "Tray packed, corrosion barrier bag, 240 units per pallet",
    "delivery_location": "Columbus, Ohio distribution center",
    "criticality": "High",
}

FRAMEWORK_SECTIONS = {
    "cost": {
        "label": "Cost",
        "description": "Direct landed cost inputs and cost-risk assumptions.",
        "fields": [
            ("unit_cost", "Unit cost", "currency"),
            ("freight_cost", "Freight cost", "currency"),
            ("tariffs_duty", "Tariffs and duty", "currency"),
            ("insurance", "Insurance", "currency"),
            ("customs_brokerage", "Customs brokerage", "currency"),
            ("packaging", "Packaging", "currency"),
            ("warehousing", "Warehousing", "currency"),
            ("cost_moq", "MOQ", "number"),
            ("cost_payment_terms", "Payment terms", "text"),
            ("currency_risk", "Currency risk", "risk"),
            ("quality_failure_cost", "Quality failure cost", "currency"),
            ("expedite_cost", "Expedite cost", "currency"),
            ("inventory_holding_cost", "Inventory holding cost", "currency"),
            ("supplier_switching_cost", "Supplier switching cost", "currency"),
            ("warranty_exposure", "Warranty exposure", "currency"),
            ("stockout_risk_cost", "Stockout risk cost", "currency"),
            ("requalification_cost", "Requalification cost", "currency"),
        ],
    },
    "lead_time": {
        "label": "Lead Time",
        "description": "End-to-end lead time assumptions in days.",
        "fields": [
            ("production_lead_time", "Supplier production lead time", "days"),
            ("raw_materials_lead_time", "Raw materials lead time", "days"),
            ("supplier_planning_time", "Internal supplier planning time", "days"),
            ("quality_inspection_time", "Quality inspection time", "days"),
            ("export_clearance_time", "Export clearance time", "days"),
            ("transit_time", "Transit time", "days"),
            ("customs_clearance_time", "Customs clearance time", "days"),
            ("receiving_putaway_time", "Receiving and put-away time", "days"),
            ("buffer_time", "Buffer time", "days"),
            ("reorder_review_cycle", "Reorder review cycle", "days"),
        ],
    },
    "capability": {
        "label": "Supplier Capability",
        "description": "Capability scores from 1 weak to 5 strong.",
        "fields": [
            ("volume_capability", "Volume capability score", "score"),
            ("equipment_capability", "Equipment capability score", "score"),
            ("quality_certification", "Quality certification score", "score"),
            ("scaling_ability", "Scaling ability score", "score"),
            ("engineering_support", "Engineering support score", "score"),
            ("compliance_understanding", "Compliance understanding score", "score"),
            ("documentation_ability", "Documentation ability score", "score"),
            ("single_factory_dependency", "Single factory dependency score", "score"),
            ("backup_capacity", "Backup capacity score", "score"),
            ("industry_experience", "Relevant industry experience", "score"),
            ("existing_customer_quality", "Existing customer quality", "score"),
        ],
    },
    "quality_risk": {
        "label": "Quality Risk",
        "description": "Risk scores from 1 very low risk to 5 very high risk.",
        "fields": [
            ("defect_rate_risk", "Defect rate score", "risk"),
            ("process_control_risk", "Process control score", "risk"),
            ("inspection_method_risk", "Inspection method score", "risk"),
            ("certification_risk", "Certification score", "risk"),
            ("traceability_risk", "Traceability score", "risk"),
            ("corrective_action_risk", "Corrective action score", "risk"),
            ("audit_result_risk", "Audit result score", "risk"),
            ("warranty_claim_risk", "Warranty claim risk score", "risk"),
            ("return_rate_risk", "Return rate risk score", "risk"),
            ("field_failure_risk", "Field failure risk score", "risk"),
        ],
    },
    "compliance": {
        "label": "Compliance Risk",
        "description": "Compliance readiness scores from 1 weak/high risk to 5 strong/low risk.",
        "fields": [
            ("required_certifications_available", "Required certifications available", "score"),
            ("product_safety_compliance", "Product safety compliance", "score"),
            ("import_export_compliance", "Import/export compliance", "score"),
            ("environmental_compliance", "Environmental compliance", "score"),
            ("labor_ethical_sourcing", "Labor and ethical sourcing compliance", "score"),
            ("documentation_completeness", "Documentation completeness", "score"),
            ("restricted_material_risk", "Restricted material risk", "risk"),
            ("audit_readiness", "Audit readiness", "score"),
            ("compliance_traceability_documentation", "Traceability documentation", "score"),
        ],
    },
    "geopolitical_risk": {
        "label": "Geopolitical Risk",
        "description": "Country and trade exposure scores from 1 very low risk to 5 very high risk.",
        "fields": [
            ("trade_war_exposure", "Trade war exposure", "risk"),
            ("tariff_risk", "Tariff risk", "risk"),
            ("export_control_risk", "Export control risk", "risk"),
            ("sanctions_risk", "Sanctions risk", "risk"),
            ("political_instability_risk", "Political instability risk", "risk"),
            ("military_conflict_risk", "Military conflict risk", "risk"),
            ("port_disruption_risk", "Port disruption risk", "risk"),
            ("labor_strike_risk", "Labor strike risk", "risk"),
            ("currency_instability_risk", "Currency instability risk", "risk"),
            ("government_policy_risk", "Government policy risk", "risk"),
            ("single_country_dependency_risk", "Single country dependency risk", "risk"),
            ("friendshoring_nearshoring_advantage", "Friendshoring/nearshoring advantage", "score"),
        ],
    },
    "logistics": {
        "label": "Logistics Risk",
        "description": "Logistics and import complexity scores from 1 low to 5 high.",
        "fields": [
            ("distance_to_delivery_risk", "Distance to delivery location", "risk"),
            ("freight_mode_complexity", "Freight mode complexity", "risk"),
            ("incoterms_complexity", "Incoterms complexity", "risk"),
            ("ocean_freight_risk", "Ocean freight risk", "risk"),
            ("air_freight_risk", "Air freight risk", "risk"),
            ("port_congestion_risk", "Port congestion risk", "risk"),
            ("container_availability_risk", "Container availability risk", "risk"),
            ("customs_clearance_complexity", "Customs clearance complexity", "risk"),
            ("freight_forwarder_requirement", "Freight forwarder requirement", "risk"),
            ("third_party_logistics_requirement", "3PL requirement", "risk"),
            ("warehousing_requirement", "Warehousing requirement", "risk"),
            ("cross_docking_requirement", "Cross-docking requirement", "risk"),
            ("last_mile_complexity", "Last-mile complexity", "risk"),
            ("import_documentation_risk", "Import documentation risk", "risk"),
            ("hs_code_risk", "HS code risk", "risk"),
            ("duties_taxes_risk", "Duties and taxes risk", "risk"),
        ],
    },
    "financial_stability": {
        "label": "Financial Stability",
        "description": "Supplier financial resilience scores from 1 weak/high risk to 5 strong/low risk.",
        "fields": [
            ("years_in_business_score", "Years in business", "score"),
            ("revenue_stability", "Revenue stability", "score"),
            ("customer_base_diversity", "Customer base diversity", "score"),
            ("credit_payment_risk", "Credit/payment risk", "risk"),
            ("bankruptcy_closure_risk", "Bankruptcy/closure risk", "risk"),
            ("customer_overdependence_risk", "Overdependence on one customer", "risk"),
            ("capacity_investment_ability", "Ability to invest in capacity", "score"),
            ("ownership_transparency", "Ownership transparency", "score"),
            ("financial_stability", "Overall financial stability", "score"),
        ],
    },
    "contract": {
        "label": "Contract Terms",
        "description": "Commercial terms and contract quality assumptions.",
        "fields": [
            ("contract_payment_terms", "Payment terms", "text"),
            ("payment_terms_score", "Payment terms favorability", "score"),
            ("contract_moq", "MOQ", "number"),
            ("moq_flexibility", "MOQ flexibility", "score"),
            ("volume_discounts", "Volume discounts", "text"),
            ("volume_discount_availability", "Volume discount availability", "score"),
            ("price_adjustment_clause", "Price adjustment clause", "score"),
            ("lead_time_commitment", "Lead time commitment", "score"),
            ("service_level_agreement", "Service level agreement", "score"),
            ("warranty_terms", "Warranty terms", "score"),
            ("liability_terms", "Liability terms", "score"),
            ("penalties", "Penalties", "score"),
            ("contract_incoterms", "Incoterms", "text"),
            ("ip_protection", "IP protection", "score"),
            ("termination_clause", "Termination clause", "score"),
            ("exclusivity", "Exclusivity", "risk"),
            ("capacity_reservation", "Capacity reservation", "score"),
            ("forecast_commitments", "Forecast commitments", "risk"),
        ],
    },
}

LANDED_COST_KEYS = [
    "unit_cost",
    "freight_cost",
    "tariffs_duty",
    "insurance",
    "customs_brokerage",
    "packaging",
    "warehousing",
]

OWNERSHIP_COST_KEYS = [
    "quality_failure_cost",
    "expedite_cost",
    "inventory_holding_cost",
    "supplier_switching_cost",
    "warranty_exposure",
    "stockout_risk_cost",
    "requalification_cost",
]

LEAD_TIME_KEYS = [
    "production_lead_time",
    "raw_materials_lead_time",
    "supplier_planning_time",
    "quality_inspection_time",
    "export_clearance_time",
    "transit_time",
    "customs_clearance_time",
    "receiving_putaway_time",
    "buffer_time",
]

LEAD_TIME_SCORE_KEYS = LEAD_TIME_KEYS + ["reorder_review_cycle"]


def default_values() -> dict[str, Any]:
    values: dict[str, Any] = {}
    for section in FRAMEWORK_SECTIONS.values():
        for key, _label, kind in section["fields"]:
            if kind == "text":
                values[key] = ""
            elif kind in {"score", "risk"}:
                values[key] = 3
            else:
                values[key] = 0.0
    return values


def all_framework_fields() -> list[dict[str, str]]:
    fields = []
    for section_key, section in FRAMEWORK_SECTIONS.items():
        for key, label, kind in section["fields"]:
            fields.append(
                {
                    "section_key": section_key,
                    "section": section["label"],
                    "key": key,
                    "label": label,
                    "kind": kind,
                }
            )
    return fields


def default_field_weights() -> dict[str, float]:
    return {field["key"]: 1.0 for field in all_framework_fields()}


def sync_category_weight_widgets() -> None:
    for key, value in st.session_state.weights.items():
        st.session_state[f"weight_{key}"] = int(value)


def sync_weight_inputs() -> None:
    for key in WEIGHT_LABELS:
        widget_key = f"weight_{key}"
        if widget_key in st.session_state:
            st.session_state.weights[key] = numeric(st.session_state[widget_key])


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_cell(value).lower()).strip()


def normalize_confidence_level(value: Any) -> str:
    normalized = normalize_label(value)
    if normalized in CONFIDENCE_ALIASES:
        return CONFIDENCE_ALIASES[normalized]
    for level in CONFIDENCE_LEVELS:
        if normalize_label(level) == normalized:
            return level
    return "Manual Review Needed"


def alias_lookup(alias_map: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for key, aliases in alias_map.items():
        lookup[normalize_label(key)] = key
        for alias in aliases:
            lookup[normalize_label(alias)] = key
    return lookup


def supplier_lookup() -> dict[str, str]:
    lookup = alias_lookup(SUPPLIER_FIELD_ALIASES)
    for section in FRAMEWORK_SECTIONS.values():
        for key, label, _kind in section["fields"]:
            lookup[normalize_label(key)] = key
            lookup[normalize_label(label)] = key
            lookup[normalize_label(label.replace(" score", "").replace(" risk", ""))] = key
    return lookup


def field_kind(key: str) -> str:
    for section in FRAMEWORK_SECTIONS.values():
        for field_key, _label, kind in section["fields"]:
            if field_key == key:
                return kind
    return "text"


def coerce_requirement_value(key: str, value: Any) -> Any:
    text_value = clean_cell(value)
    if not text_value:
        return None
    if key in {"quantity", "required_lead_time", "forecasted_demand"}:
        return int(numeric(value))
    if key == "target_cost":
        return float(numeric(value))
    if key == "criticality":
        for level in CRITICALITY_LEVELS:
            if normalize_label(level) == normalize_label(text_value):
                return level
        return text_value
    return text_value


def coerce_supplier_value(key: str, value: Any) -> Any:
    text_value = clean_cell(value)
    if not text_value:
        return None
    if key == "annual_capacity":
        return int(numeric(value))
    if key == "confidence_level":
        return normalize_confidence_level(text_value)
    kind = field_kind(key)
    if kind == "text":
        return text_value
    if kind in {"score", "risk"}:
        return max(1.0, min(5.0, numeric(value) or 3.0))
    return numeric(value)


def row_label_count(row: pd.Series, lookup: dict[str, str]) -> int:
    return sum(1 for value in row.tolist() if normalize_label(value) in lookup)


def mapped_columns(row: pd.Series, lookup: dict[str, str]) -> dict[int, str]:
    columns = {}
    seen = set()
    for col_idx, value in enumerate(row.tolist()):
        key = lookup.get(normalize_label(value))
        if key and key not in seen:
            columns[col_idx] = key
            seen.add(key)
    return columns


def extract_key_value_requirements(
    df: pd.DataFrame, sheet_name: str, requirement_lookup: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    extracted: dict[str, Any] = {}
    matches = []
    max_rows = min(len(df), 100)
    max_cols = min(len(df.columns), 12)
    for row_idx in range(max_rows):
        row = df.iloc[row_idx, :max_cols]
        if row_label_count(row, requirement_lookup) > 1:
            continue
        for col_idx in range(max_cols):
            key = requirement_lookup.get(normalize_label(df.iat[row_idx, col_idx]))
            if not key or key in extracted:
                continue
            candidates = []
            if col_idx + 1 < max_cols:
                candidates.append(df.iat[row_idx, col_idx + 1])
            if row_idx + 1 < max_rows:
                candidates.append(df.iat[row_idx + 1, col_idx])
            for candidate in candidates:
                if normalize_label(candidate) in requirement_lookup:
                    continue
                value = coerce_requirement_value(key, candidate)
                if value is not None:
                    extracted[key] = value
                    matches.append(f"{sheet_name}: {key}")
                    break
    return extracted, matches


def extract_wide_requirements(
    df: pd.DataFrame, sheet_name: str, requirement_lookup: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    for header_idx in range(min(len(df), 25)):
        columns = mapped_columns(df.iloc[header_idx], requirement_lookup)
        if len(columns) < 2:
            continue
        for row_idx in range(header_idx + 1, min(len(df), header_idx + 12)):
            row_values = {
                key: coerce_requirement_value(key, df.iat[row_idx, col_idx])
                for col_idx, key in columns.items()
            }
            row_values = {key: value for key, value in row_values.items() if value is not None}
            if row_values:
                return row_values, [f"{sheet_name}: {key}" for key in row_values]
    return {}, []


def supplier_id_from_name(name: str, position: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"imported-{slug or 'supplier'}-{position}"


def extract_supplier_rows(
    df: pd.DataFrame, sheet_name: str, supplier_field_lookup: dict[str, str]
) -> list[dict[str, Any]]:
    suppliers = []
    for header_idx in range(min(len(df), 30)):
        columns = mapped_columns(df.iloc[header_idx], supplier_field_lookup)
        if "name" not in columns.values() or len(columns) < 2:
            continue
        for row_idx in range(header_idx + 1, len(df)):
            raw_name = next(
                (df.iat[row_idx, col_idx] for col_idx, key in columns.items() if key == "name"),
                "",
            )
            name = clean_cell(raw_name)
            if not name:
                continue
            supplier = {
                "id": supplier_id_from_name(name, row_idx),
                "name": name,
                "country": "",
                "region": "",
                "website": "",
                "product_match": "",
                "certifications": "",
                "annual_capacity": 0,
                "customer_notes": f"Imported from {sheet_name}",
                "confidence_level": "Manual Review Needed",
                "values": default_values(),
            }
            for col_idx, key in columns.items():
                value = coerce_supplier_value(key, df.iat[row_idx, col_idx])
                if value is None:
                    continue
                if key in SUPPLIER_FIELD_ALIASES:
                    supplier[key] = value
                elif key in supplier["values"]:
                    supplier["values"][key] = value
            suppliers.append(supplier)
        if suppliers:
            return suppliers
    return suppliers


def parse_sourcing_workbook(file_bytes: bytes) -> dict[str, Any]:
    result = {"requirement": {}, "suppliers": [], "matches": [], "errors": []}
    requirement_lookup = alias_lookup(REQUIREMENT_FIELD_ALIASES)
    supplier_field_lookup = supplier_lookup()
    try:
        sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None, header=None, dtype=object)
    except Exception as error:  # noqa: BLE001 - Streamlit should show a friendly parsing error.
        result["errors"].append(f"Could not read workbook: {error}")
        return result

    for sheet_name, df in sheets.items():
        clean_df = df.dropna(how="all").dropna(axis=1, how="all")
        if clean_df.empty:
            continue
        key_values, key_matches = extract_key_value_requirements(clean_df, sheet_name, requirement_lookup)
        wide_values, wide_matches = extract_wide_requirements(clean_df, sheet_name, requirement_lookup)
        for key, value in {**key_values, **wide_values}.items():
            result["requirement"].setdefault(key, value)
        result["matches"].extend(key_matches + wide_matches)
        result["suppliers"].extend(extract_supplier_rows(clean_df, sheet_name, supplier_field_lookup))
    return result


def merge_imported_supplier(imported_supplier: dict[str, Any]) -> None:
    imported_name = normalize_label(imported_supplier["name"])
    existing_supplier = next(
        (supplier for supplier in st.session_state.suppliers if normalize_label(supplier["name"]) == imported_name),
        None,
    )
    if existing_supplier is None:
        st.session_state.suppliers.append(imported_supplier)
        return
    for key in [
        "country",
        "region",
        "website",
        "product_match",
        "certifications",
        "annual_capacity",
        "customer_notes",
        "confidence_level",
    ]:
        if imported_supplier.get(key) not in {"", 0, None}:
            existing_supplier[key] = imported_supplier[key]
    for key, value in imported_supplier["values"].items():
        if value not in {"", 0, 0.0, None}:
            existing_supplier["values"][key] = value


def apply_sourcing_import(parsed: dict[str, Any]) -> None:
    for key, value in parsed["requirement"].items():
        if value not in {"", None}:
            st.session_state.requirement[key] = value
    for supplier in parsed["suppliers"]:
        merge_imported_supplier(supplier)


COMMON_VALUES = {
    **default_values(),
    "unit_cost": 8.80,
    "freight_cost": 0.90,
    "tariffs_duty": 0.60,
    "insurance": 0.10,
    "customs_brokerage": 0.08,
    "packaging": 0.18,
    "warehousing": 0.14,
    "cost_moq": 25000,
    "cost_payment_terms": "Net 45",
    "currency_risk": 2,
    "quality_failure_cost": 0.22,
    "expedite_cost": 0.18,
    "inventory_holding_cost": 0.30,
    "supplier_switching_cost": 0.16,
    "warranty_exposure": 0.12,
    "stockout_risk_cost": 0.10,
    "requalification_cost": 0.08,
    "production_lead_time": 28,
    "raw_materials_lead_time": 14,
    "supplier_planning_time": 4,
    "quality_inspection_time": 3,
    "export_clearance_time": 2,
    "transit_time": 24,
    "customs_clearance_time": 4,
    "receiving_putaway_time": 2,
    "buffer_time": 7,
    "reorder_review_cycle": 14,
    "volume_capability": 4,
    "equipment_capability": 4,
    "quality_certification": 4,
    "financial_stability": 4,
    "scaling_ability": 4,
    "engineering_support": 4,
    "compliance_understanding": 4,
    "documentation_ability": 4,
    "single_factory_dependency": 3,
    "backup_capacity": 3,
    "industry_experience": 4,
    "existing_customer_quality": 4,
    "defect_rate_risk": 2,
    "process_control_risk": 2,
    "inspection_method_risk": 2,
    "certification_risk": 2,
    "traceability_risk": 2,
    "corrective_action_risk": 2,
    "audit_result_risk": 2,
    "warranty_claim_risk": 2,
    "return_rate_risk": 2,
    "field_failure_risk": 2,
    "required_certifications_available": 4,
    "product_safety_compliance": 4,
    "import_export_compliance": 4,
    "environmental_compliance": 4,
    "labor_ethical_sourcing": 4,
    "documentation_completeness": 4,
    "restricted_material_risk": 2,
    "audit_readiness": 4,
    "compliance_traceability_documentation": 4,
    "trade_war_exposure": 2,
    "tariff_risk": 2,
    "export_control_risk": 2,
    "sanctions_risk": 1,
    "political_instability_risk": 2,
    "military_conflict_risk": 1,
    "port_disruption_risk": 3,
    "labor_strike_risk": 2,
    "currency_instability_risk": 2,
    "government_policy_risk": 2,
    "single_country_dependency_risk": 3,
    "friendshoring_nearshoring_advantage": 3,
    "distance_to_delivery_risk": 3,
    "freight_mode_complexity": 2,
    "incoterms_complexity": 2,
    "ocean_freight_risk": 3,
    "air_freight_risk": 2,
    "port_congestion_risk": 3,
    "container_availability_risk": 2,
    "customs_clearance_complexity": 2,
    "freight_forwarder_requirement": 2,
    "third_party_logistics_requirement": 2,
    "warehousing_requirement": 2,
    "cross_docking_requirement": 1,
    "last_mile_complexity": 2,
    "import_documentation_risk": 2,
    "hs_code_risk": 2,
    "duties_taxes_risk": 2,
    "years_in_business_score": 4,
    "revenue_stability": 4,
    "customer_base_diversity": 4,
    "credit_payment_risk": 2,
    "bankruptcy_closure_risk": 1,
    "customer_overdependence_risk": 2,
    "capacity_investment_ability": 4,
    "ownership_transparency": 4,
    "contract_payment_terms": "Net 45 after inspection",
    "payment_terms_score": 4,
    "contract_moq": 25000,
    "moq_flexibility": 3,
    "volume_discounts": "2% over 75k units",
    "volume_discount_availability": 4,
    "price_adjustment_clause": 4,
    "lead_time_commitment": 4,
    "service_level_agreement": 4,
    "warranty_terms": 4,
    "liability_terms": 3,
    "penalties": 3,
    "contract_incoterms": "FOB Hai Phong",
    "ip_protection": 4,
    "termination_clause": 4,
    "exclusivity": 2,
    "capacity_reservation": 3,
    "forecast_commitments": 2,
}

SAMPLE_SUPPLIERS = [
    {
        "id": "pacific-precision",
        "name": "Pacific Precision Manufacturing",
        "country": "Vietnam",
        "region": "Southeast Asia",
        "website": "https://example.com/pacific-precision",
        "product_match": "Strong CNC aluminum housing capability",
        "certifications": "ISO 9001, IATF 16949, RoHS process controls",
        "annual_capacity": 220000,
        "customer_notes": "Verified through sourcing database and prior RFQ packet.",
        "confidence_level": "Verified",
        "values": {
            **COMMON_VALUES,
            "unit_cost": 8.45,
            "freight_cost": 0.82,
            "tariffs_duty": 0.48,
            "inventory_holding_cost": 0.28,
            "warranty_exposure": 0.10,
            "stockout_risk_cost": 0.08,
            "requalification_cost": 0.06,
            "production_lead_time": 30,
            "transit_time": 22,
            "buffer_time": 6,
            "volume_capability": 5,
            "scaling_ability": 4,
            "engineering_support": 4,
            "backup_capacity": 4,
            "industry_experience": 5,
            "existing_customer_quality": 4,
            "required_certifications_available": 5,
            "documentation_completeness": 5,
            "audit_readiness": 5,
            "port_congestion_risk": 2,
            "financial_stability": 4,
            "revenue_stability": 4,
            "customer_base_diversity": 4,
            "contract_payment_terms": "Net 60 after PPAP approval",
            "payment_terms_score": 5,
            "contract_moq": 30000,
            "moq_flexibility": 3,
            "capacity_reservation": 4,
        },
    },
    {
        "id": "shenzhen-alloy",
        "name": "Shenzhen Alloy Works",
        "country": "China",
        "region": "East Asia",
        "website": "https://example.com/shenzhen-alloy",
        "product_match": "Excellent machining breadth, tariff exposure needs review",
        "certifications": "ISO 9001; IATF data pending",
        "annual_capacity": 340000,
        "customer_notes": "Pricing attractive, but certification data needs manual validation.",
        "confidence_level": "Supplier Quote",
        "values": {
            **COMMON_VALUES,
            "unit_cost": 7.92,
            "freight_cost": 0.95,
            "tariffs_duty": 1.10,
            "customs_brokerage": 0.11,
            "cost_moq": 40000,
            "cost_payment_terms": "30% deposit / 70% before shipment",
            "currency_risk": 3,
            "quality_failure_cost": 0.36,
            "supplier_switching_cost": 0.22,
            "warranty_exposure": 0.18,
            "stockout_risk_cost": 0.18,
            "requalification_cost": 0.14,
            "production_lead_time": 24,
            "raw_materials_lead_time": 12,
            "transit_time": 26,
            "buffer_time": 9,
            "quality_certification": 3,
            "compliance_understanding": 3,
            "documentation_ability": 3,
            "industry_experience": 4,
            "existing_customer_quality": 3,
            "defect_rate_risk": 3,
            "certification_risk": 4,
            "traceability_risk": 3,
            "audit_result_risk": 3,
            "required_certifications_available": 3,
            "product_safety_compliance": 3,
            "documentation_completeness": 2,
            "restricted_material_risk": 3,
            "audit_readiness": 2,
            "compliance_traceability_documentation": 3,
            "trade_war_exposure": 4,
            "tariff_risk": 4,
            "export_control_risk": 3,
            "government_policy_risk": 3,
            "single_country_dependency_risk": 4,
            "friendshoring_nearshoring_advantage": 2,
            "duties_taxes_risk": 4,
            "financial_stability": 3,
            "credit_payment_risk": 3,
            "customer_overdependence_risk": 3,
            "ownership_transparency": 3,
            "contract_payment_terms": "30% deposit, balance before shipment",
            "payment_terms_score": 2,
            "contract_moq": 40000,
            "moq_flexibility": 2,
            "volume_discounts": "4% over 120k units",
            "volume_discount_availability": 4,
            "liability_terms": 2,
            "ip_protection": 3,
            "forecast_commitments": 3,
        },
    },
    {
        "id": "monterrey-cnc",
        "name": "Monterrey CNC Partners",
        "country": "Mexico",
        "region": "North America",
        "website": "https://example.com/monterrey-cnc",
        "product_match": "Nearshore option with faster transit and higher unit cost",
        "certifications": "ISO 9001, IATF 16949, USMCA documentation",
        "annual_capacity": 145000,
        "customer_notes": "Estimated cost from benchmark quote. Strong logistics profile.",
        "confidence_level": "Public Estimate",
        "values": {
            **COMMON_VALUES,
            "unit_cost": 9.35,
            "freight_cost": 0.42,
            "tariffs_duty": 0.08,
            "insurance": 0.06,
            "customs_brokerage": 0.06,
            "warehousing": 0.08,
            "cost_moq": 15000,
            "quality_failure_cost": 0.18,
            "expedite_cost": 0.08,
            "inventory_holding_cost": 0.16,
            "warranty_exposure": 0.08,
            "stockout_risk_cost": 0.06,
            "requalification_cost": 0.06,
            "production_lead_time": 20,
            "raw_materials_lead_time": 10,
            "export_clearance_time": 1,
            "transit_time": 5,
            "customs_clearance_time": 2,
            "buffer_time": 4,
            "reorder_review_cycle": 7,
            "volume_capability": 3,
            "scaling_ability": 3,
            "backup_capacity": 3,
            "industry_experience": 4,
            "existing_customer_quality": 3,
            "defect_rate_risk": 2,
            "process_control_risk": 2,
            "warranty_claim_risk": 1,
            "trade_war_exposure": 1,
            "tariff_risk": 1,
            "export_control_risk": 1,
            "port_disruption_risk": 1,
            "currency_instability_risk": 3,
            "single_country_dependency_risk": 2,
            "friendshoring_nearshoring_advantage": 5,
            "distance_to_delivery_risk": 1,
            "freight_mode_complexity": 1,
            "incoterms_complexity": 1,
            "ocean_freight_risk": 1,
            "port_congestion_risk": 1,
            "freight_forwarder_requirement": 1,
            "import_documentation_risk": 1,
            "duties_taxes_risk": 1,
            "financial_stability": 3,
            "years_in_business_score": 3,
            "customer_base_diversity": 3,
            "capacity_investment_ability": 3,
            "contract_payment_terms": "Net 30 after receipt",
            "payment_terms_score": 4,
            "contract_moq": 15000,
            "moq_flexibility": 5,
            "lead_time_commitment": 5,
            "service_level_agreement": 4,
            "penalties": 4,
            "contract_incoterms": "DAP Columbus",
            "capacity_reservation": 3,
            "forecast_commitments": 2,
        },
    },
]


def add_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1220px; padding-top: 1.35rem; padding-bottom: 2rem; }
        [data-testid="stSidebar"] { display: none; }
        h1, h2, h3 { letter-spacing: 0; }
        h1 { font-weight: 720; }
        .small-muted { color: #64748b; font-size: 0.9rem; }
        .risk-low { color: #047857; font-weight: 700; }
        .risk-med { color: #b45309; font-weight: 700; }
        .risk-high { color: #b91c1c; font-weight: 700; }
        .app-kicker {
            color: #475569;
            font-size: 0.95rem;
            margin-top: -0.35rem;
            max-width: 760px;
        }
        .intro-panel {
            border: 1px solid #dbe3ea;
            border-radius: 8px;
            padding: 2rem;
            background: #ffffff;
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.06);
            margin-top: 1rem;
        }
        .intro-panel h1 {
            font-size: 2.35rem;
            line-height: 1.1;
            margin: 0 0 0.85rem;
        }
        .intro-panel p {
            color: #475569;
            font-size: 1.05rem;
            line-height: 1.65;
            max-width: 820px;
        }
        .intro-points {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }
        .intro-point {
            border-top: 1px solid #dbe3ea;
            padding-top: 0.85rem;
        }
        .intro-point strong {
            display: block;
            color: #0f172a;
            font-size: 0.96rem;
            margin-bottom: 0.25rem;
        }
        .intro-point span {
            color: #64748b;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .st-key-workflow_navigation div[role="radiogroup"] {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            background: #f8fafc;
            border: 1px solid #dbe3ea;
            border-radius: 8px;
            padding: 0.35rem;
            margin: 0.6rem 0 1rem;
        }
        .st-key-workflow_navigation div[role="radiogroup"] label {
            border-radius: 6px;
            padding: 0.35rem 0.55rem;
            margin: 0;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: none;
        }
        div[data-testid="stMetric"] * {
            color: #0f172a !important;
        }
        div[data-testid="stMetricDelta"] * {
            color: #047857 !important;
        }
        @media (max-width: 760px) {
            .intro-panel { padding: 1.25rem; }
            .intro-panel h1 { font-size: 1.75rem; }
            .intro-points { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def migrate_supplier_record(supplier: dict[str, Any]) -> None:
    supplier["confidence_level"] = normalize_confidence_level(supplier.get("confidence_level", ""))
    if "values" not in supplier or not isinstance(supplier["values"], dict):
        supplier["values"] = default_values()
    defaults = default_values()
    for key, value in defaults.items():
        supplier["values"].setdefault(key, value)


def initialize_state() -> None:
    if "requirement" not in st.session_state:
        st.session_state.requirement = deepcopy(BLANK_REQUIREMENT)
    if "suppliers" not in st.session_state:
        st.session_state.suppliers = []
    for supplier in st.session_state.suppliers:
        migrate_supplier_record(supplier)
    if "weights" not in st.session_state:
        st.session_state.weights = deepcopy(DEFAULT_WEIGHTS)
    else:
        for key, value in DEFAULT_WEIGHTS.items():
            st.session_state.weights.setdefault(key, value)
        for key in list(st.session_state.weights.keys()):
            if key not in DEFAULT_WEIGHTS:
                del st.session_state.weights[key]
    if "field_weights" not in st.session_state:
        st.session_state.field_weights = default_field_weights()
    else:
        for key, value in default_field_weights().items():
            st.session_state.field_weights.setdefault(key, value)
    if "field_weight_editor_version" not in st.session_state:
        st.session_state.field_weight_editor_version = 0
    if "workspace_page" not in st.session_state:
        st.session_state.workspace_page = "Product"
    st.session_state.workspace_page = LEGACY_PAGE_MAP.get(
        st.session_state.workspace_page,
        st.session_state.workspace_page,
    )
    if "app_started" not in st.session_state:
        st.session_state.app_started = False


def reset_workspace() -> None:
    st.session_state.requirement = deepcopy(BLANK_REQUIREMENT)
    st.session_state.suppliers = []
    st.session_state.weights = deepcopy(DEFAULT_WEIGHTS)
    sync_category_weight_widgets()
    st.session_state.field_weights = default_field_weights()
    st.session_state.field_weight_editor_version += 1
    st.session_state.workspace_page = "Product"
    st.session_state.app_started = True


def load_demo_data() -> None:
    st.session_state.requirement = deepcopy(SAMPLE_REQUIREMENT)
    st.session_state.suppliers = deepcopy(SAMPLE_SUPPLIERS)
    st.session_state.weights = deepcopy(DEFAULT_WEIGHTS)
    sync_category_weight_widgets()
    st.session_state.field_weights = default_field_weights()
    st.session_state.field_weight_editor_version += 1
    st.session_state.workspace_page = "Dashboard"
    st.session_state.app_started = True


def navigate_to_page(page: str) -> None:
    st.session_state.app_started = True
    st.session_state.workspace_page = LEGACY_PAGE_MAP.get(page, page)


def show_welcome() -> None:
    st.session_state.app_started = False


def requirement_progress(requirement: dict[str, Any]) -> tuple[int, int]:
    required_fields = [
        "product_name",
        "product_category",
        "product_specs",
        "quantity",
        "quality_requirements",
        "compliance_requirements",
        "target_cost",
        "required_lead_time",
        "forecasted_demand",
        "approved_materials",
        "technical_drawings",
        "packaging_requirements",
        "delivery_location",
    ]
    complete = 0
    for field in required_fields:
        value = requirement.get(field)
        if isinstance(value, str):
            complete += int(bool(value.strip()))
        else:
            complete += int(numeric(value) > 0)
    return complete, len(required_fields)


def numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def supplier_numeric(supplier: dict[str, Any], key: str) -> float:
    return numeric(supplier["values"].get(key))


def field_weight(field_weights: dict[str, float], key: str) -> float:
    return max(0.0, numeric(field_weights.get(key, 1.0)))


def weighted_sum(supplier: dict[str, Any], keys: list[str], field_weights: dict[str, float]) -> float:
    return sum(supplier_numeric(supplier, key) * field_weight(field_weights, key) for key in keys)


def format_currency(value: float) -> str:
    if abs(value) >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def format_days(value: float) -> str:
    return f"{value:,.0f} days"


def short_name(name: str) -> str:
    parts = [part for part in name.split() if len(part) > 2]
    return " ".join(parts[:2]) or name


def bounded_score(value: Any, default: float = 3.0) -> float:
    number = numeric(value)
    if number <= 0:
        number = default
    return max(1.0, min(5.0, number))


def calculate_landed_cost(supplier: dict[str, Any]) -> float:
    return sum(supplier_numeric(supplier, key) for key in LANDED_COST_KEYS)


def calculate_tco(supplier: dict[str, Any]) -> float:
    return calculate_landed_cost(supplier) + sum(
        supplier_numeric(supplier, key) for key in OWNERSHIP_COST_KEYS
    )


def calculate_total_lead_time(supplier: dict[str, Any]) -> float:
    return sum(supplier_numeric(supplier, key) for key in LEAD_TIME_KEYS)


def calculate_average_score(scores: list[float | tuple[float, float]]) -> float:
    subfactor_list = [
        item if isinstance(item, tuple) else (item, 1.0)
        for item in scores
    ]
    total_weight = sum(weight for _value, weight in subfactor_list)
    if total_weight <= 0:
        return 3.0
    return sum(value * weight for value, weight in subfactor_list) / total_weight


def convert_risk_to_score(risk_score: float) -> float:
    return 6.0 - bounded_score(risk_score)


def normalize_lower_is_better(value: float, min_value: float, max_value: float) -> float:
    if max_value == min_value:
        return 5.0
    score = 5.0 - ((value - min_value) / (max_value - min_value)) * 4.0
    return max(1.0, min(5.0, score))


def score_to_100(score: float) -> int:
    return int(round(bounded_score(score) * 20))


def risk_average(
    supplier: dict[str, Any], section_key: str, field_weights: dict[str, float]
) -> float:
    subfactors = []
    for key, _label, kind in FRAMEWORK_SECTIONS[section_key]["fields"]:
        if kind != "risk":
            continue
        subfactors.append((bounded_score(supplier_numeric(supplier, key)), field_weight(field_weights, key)))
    return calculate_average_score(subfactors) if subfactors else 1.0


def average_section_score(
    supplier: dict[str, Any], section_key: str, field_weights: dict[str, float]
) -> float:
    subfactors = []
    for key, _label, kind in FRAMEWORK_SECTIONS[section_key]["fields"]:
        if kind not in {"score", "risk"}:
            continue
        raw_value = bounded_score(supplier_numeric(supplier, key))
        score = convert_risk_to_score(raw_value) if kind == "risk" else raw_value
        subfactors.append((score, field_weight(field_weights, key)))
    return calculate_average_score(subfactors)


def data_confidence_score(supplier: dict[str, Any]) -> int:
    return CONFIDENCE_SCORE_MAP.get(normalize_confidence_level(supplier.get("confidence_level", "")), 1)


def calculate_final_supplier_score(supplier: dict[str, Any], weights: dict[str, float]) -> int:
    category_scores = supplier.get("category_scores", supplier)
    total_weight = sum(max(0.0, numeric(value)) for value in weights.values())
    if total_weight <= 0:
        return 0
    weighted_score = sum(
        bounded_score(category_scores.get(key, 3.0)) * max(0.0, numeric(weights.get(key, 0.0)))
        for key in DEFAULT_WEIGHTS
    )
    return int(round((weighted_score / total_weight) * 20))


def generate_manual_review_flags(
    supplier: dict[str, Any],
    requirement: dict[str, Any] | None = None,
    supplier_count: int = 0,
    field_weights: dict[str, float] | None = None,
) -> list[str]:
    field_weights = field_weights or default_field_weights()
    values = supplier.get("values", {})
    certifications = str(supplier.get("certifications", "")).lower()
    flags = []

    if not certifications or "pending" in certifications or "unavailable" in certifications:
        flags.append("Missing quality certification data")
    if not str(values.get("contract_payment_terms") or values.get("cost_payment_terms") or "").strip():
        flags.append("Missing payment terms")
    if average_section_score(supplier, "compliance", field_weights) < 3:
        flags.append("Missing compliance documentation")
    if calculate_total_lead_time(supplier) <= 0 or data_confidence_score(supplier) <= 2:
        flags.append("Lead time estimate needs verification")
    if numeric(values.get("tariffs_duty")) <= 0 or bounded_score(values.get("tariff_risk")) >= 4:
        flags.append("Tariff/duty estimate needs manual review")
    if average_section_score(supplier, "capability", field_weights) < 3 or data_confidence_score(supplier) <= 2:
        flags.append("Supplier capability not verified")
    if data_confidence_score(supplier) < 3:
        flags.append("Data confidence below 3")
    if risk_average(supplier, "geopolitical_risk", field_weights) >= 4:
        flags.append("High geopolitical risk")
    if risk_average(supplier, "logistics", field_weights) >= 4:
        flags.append("High logistics risk")
    if (
        requirement
        and requirement.get("criticality") == "Critical"
        and supplier_count < 2
    ):
        flags.append("Critical part with no backup supplier")
    return list(dict.fromkeys(flags))


def calculate_metrics(
    suppliers: list[dict[str, Any]],
    weights: dict[str, float],
    quantity: float,
    field_weights: dict[str, float],
    requirement: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    base_metrics = []
    for supplier in suppliers:
        migrate_supplier_record(supplier)
        landed = calculate_landed_cost(supplier)
        tco = calculate_tco(supplier)
        lead_time = calculate_total_lead_time(supplier)
        weighted_landed = weighted_sum(supplier, LANDED_COST_KEYS, field_weights)
        weighted_tco = weighted_landed + weighted_sum(supplier, OWNERSHIP_COST_KEYS, field_weights)
        weighted_lead_time = weighted_sum(supplier, LEAD_TIME_SCORE_KEYS, field_weights)
        base_metrics.append(
            {
                "supplier_id": supplier["id"],
                "supplier_name": supplier["name"],
                "country": supplier.get("country", ""),
                "region": supplier.get("region", ""),
                "confidence_level": normalize_confidence_level(supplier.get("confidence_level", "")),
                "data_confidence_score": data_confidence_score(supplier),
                "total_landed_cost": landed,
                "total_cost_of_ownership": tco,
                "total_order_cost": landed * quantity,
                "total_order_tco": tco * quantity,
                "total_lead_time": lead_time,
                "weighted_landed_cost_basis": weighted_landed,
                "weighted_tco_basis": weighted_tco,
                "weighted_lead_time_basis": weighted_lead_time,
                "capability_score": average_section_score(supplier, "capability", field_weights),
                "quality_score": average_section_score(supplier, "quality_risk", field_weights),
                "quality_risk_average": risk_average(supplier, "quality_risk", field_weights),
                "compliance_score": average_section_score(supplier, "compliance", field_weights),
                "compliance_risk_average": risk_average(supplier, "compliance", field_weights),
                "geopolitical_score": average_section_score(supplier, "geopolitical_risk", field_weights),
                "geopolitical_risk_average": risk_average(supplier, "geopolitical_risk", field_weights),
                "logistics_score": average_section_score(supplier, "logistics", field_weights),
                "logistics_risk_average": risk_average(supplier, "logistics", field_weights),
                "financial_stability_score": average_section_score(
                    supplier, "financial_stability", field_weights
                ),
                "contract_score": average_section_score(supplier, "contract", field_weights),
                "manual_review_flags": generate_manual_review_flags(
                    supplier, requirement, len(suppliers), field_weights
                ),
            }
        )

    landed_values = [metric["weighted_landed_cost_basis"] for metric in base_metrics]
    tco_values = [metric["weighted_tco_basis"] for metric in base_metrics]
    lead_values = [metric["weighted_lead_time_basis"] for metric in base_metrics]

    for metric in base_metrics:
        landed_score = normalize_lower_is_better(
            metric["weighted_landed_cost_basis"], min(landed_values), max(landed_values)
        )
        tco_score = normalize_lower_is_better(
            metric["weighted_tco_basis"], min(tco_values), max(tco_values)
        )
        lead_score = normalize_lower_is_better(
            metric["weighted_lead_time_basis"], min(lead_values), max(lead_values)
        )
        metric["category_scores"] = {
            "landed_cost": landed_score,
            "tco": tco_score,
            "lead_time": lead_score,
            "capability": metric["capability_score"],
            "quality_risk": metric["quality_score"],
            "compliance": metric["compliance_score"],
            "geopolitical_risk": metric["geopolitical_score"],
            "logistics": metric["logistics_score"],
            "financial_stability": metric["financial_stability_score"],
            "contract": metric["contract_score"],
        }
        metric["dimension_scores"] = {
            "Landed Cost": score_to_100(landed_score),
            "TCO": score_to_100(tco_score),
            "Lead Time": score_to_100(lead_score),
            "Capability": score_to_100(metric["capability_score"]),
            "Quality": score_to_100(metric["quality_score"]),
            "Compliance": score_to_100(metric["compliance_score"]),
            "Geopolitical": score_to_100(metric["geopolitical_score"]),
            "Logistics": score_to_100(metric["logistics_score"]),
            "Financial Stability": score_to_100(metric["financial_stability_score"]),
            "Contract Terms": score_to_100(metric["contract_score"]),
        }
        metric["final_score"] = calculate_final_supplier_score(metric, weights)
    recommendation_labels = assign_recommendation_labels(base_metrics)
    for metric in base_metrics:
        metric["recommendation"] = recommendation_labels.get(metric["supplier_id"], "Review")
    return base_metrics


def assign_recommendation_labels(metrics: list[dict[str, Any]]) -> dict[str, str]:
    labels = {metric["supplier_id"]: [] for metric in metrics}
    if not metrics:
        return {}

    by_score = sorted(metrics, key=lambda metric: metric["final_score"], reverse=True)
    by_cost = sorted(metrics, key=lambda metric: metric["total_landed_cost"])
    by_lead = sorted(metrics, key=lambda metric: metric["total_lead_time"])

    labels[by_score[0]["supplier_id"]].append("Best Overall")
    labels[by_cost[0]["supplier_id"]].append("Lowest Cost")
    labels[by_lead[0]["supplier_id"]].append("Fastest Lead Time")

    backup = next(
        (
            metric
            for metric in by_score[1:]
            if max(
                metric["quality_risk_average"],
                metric["compliance_risk_average"],
                metric["geopolitical_risk_average"],
                metric["logistics_risk_average"],
            )
            < 4
            and metric["data_confidence_score"] >= 3
        ),
        None,
    )
    if backup:
        labels[backup["supplier_id"]].append("Best Backup Supplier")

    for metric in metrics:
        if max(
            metric["quality_risk_average"],
            metric["compliance_risk_average"],
            metric["geopolitical_risk_average"],
            metric["logistics_risk_average"],
        ) >= 4:
            labels[metric["supplier_id"]].append("High Risk")
        if metric["data_confidence_score"] < 3 or metric["manual_review_flags"]:
            labels[metric["supplier_id"]].append("Manual Review Needed")

    return {
        supplier_id: ", ".join(dict.fromkeys(supplier_labels)) or "Review"
        for supplier_id, supplier_labels in labels.items()
    }


def recommendation_summary(metrics: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    if not metrics:
        return {
            "best_overall": None,
            "lowest_cost": None,
            "fastest_lead_time": None,
            "highest_risk": None,
            "backup_supplier": None,
        }
    by_score = sorted(metrics, key=lambda metric: metric["final_score"], reverse=True)
    by_cost = sorted(metrics, key=lambda metric: metric["total_landed_cost"])
    by_lead = sorted(metrics, key=lambda metric: metric["total_lead_time"])
    by_risk = sorted(
        metrics,
        key=lambda metric: metric["quality_risk_average"]
        + metric["compliance_risk_average"]
        + metric["geopolitical_risk_average"]
        + metric["logistics_risk_average"]
        + (6 - metric["financial_stability_score"]),
        reverse=True,
    )
    return {
        "best_overall": by_score[0],
        "lowest_cost": by_cost[0],
        "fastest_lead_time": by_lead[0],
        "highest_risk": by_risk[0],
        "backup_supplier": next(
            (
                metric
                for metric in by_score[1:]
                if max(
                    metric["quality_risk_average"],
                    metric["geopolitical_risk_average"],
                    metric["logistics_risk_average"],
                )
                < 4
                and metric["data_confidence_score"] >= 3
            ),
            None,
        ),
    }


def analyze_requirement(requirement: dict[str, Any]) -> dict[str, Any]:
    missing = []
    risks = []
    questions = []
    required_text_fields = {
        "product_specs": "Product specs",
        "quality_requirements": "Quality requirements",
        "compliance_requirements": "Compliance requirements",
        "approved_materials": "Approved materials",
        "technical_drawings": "Technical drawings or notes",
        "packaging_requirements": "Packaging requirements",
        "delivery_location": "Delivery location",
    }
    for key, label in required_text_fields.items():
        if not str(requirement.get(key, "")).strip():
            missing.append(label)
    if numeric(requirement.get("target_cost")) <= 0:
        missing.append("Target cost")
    if numeric(requirement.get("required_lead_time")) <= 0:
        missing.append("Required lead time")

    if requirement.get("criticality") in {"High", "Critical"}:
        risks.append("Critical parts need dual sourcing, documented qualification, and a backup plan.")
        questions.append("What backup capacity can you reserve if demand spikes or quality holds occur?")
    required_lead_time = numeric(requirement.get("required_lead_time"))
    if 0 < required_lead_time < 45:
        risks.append("The required lead time is tight for global sourcing and may require nearshore options.")
        questions.append("Which lead-time steps can be contractually committed, and where is buffer hidden?")
    if "rohs" not in str(requirement.get("compliance_requirements", "")).lower():
        risks.append("Compliance scope may be incomplete for regulated product categories.")
    if numeric(requirement.get("forecasted_demand")) > numeric(requirement.get("quantity")) * 3:
        risks.append("Forecast demand materially exceeds the first order quantity, so scaling ability matters.")

    questions.extend(
        [
            "Can the supplier provide recent audit evidence and traceability records?",
            "Which cost elements are quoted, estimated, or excluded from the commercial offer?",
            "What payment terms, warranty terms, and IP protections are negotiable?",
        ]
    )
    if requirement.get("criticality") == "Critical" or len(risks) >= 4:
        risk_tier = "Critical"
    elif requirement.get("criticality") == "High" or len(risks) >= 2:
        risk_tier = "Medium-risk"
    else:
        risk_tier = "Low-risk"
    if risk_tier == "Critical":
        strategy = "Run parallel RFQs in two regions, require audit evidence before award, and reserve backup capacity."
    elif risk_tier == "Medium-risk":
        strategy = "Shortlist 3-5 suppliers, validate missing data manually, and compare landed cost against lead-time risk."
    else:
        strategy = "Use a focused RFQ with two verified suppliers and keep a light backup option."
    return {
        "missing": missing,
        "risks": risks,
        "questions": questions,
        "strategy": strategy,
        "risk_tier": risk_tier,
    }


def build_insights(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[str]:
    summary = recommendation_summary(metrics)
    insights = []
    lowest = summary["lowest_cost"]
    best = summary["best_overall"]
    fastest = summary["fastest_lead_time"]
    if lowest and lowest["geopolitical_risk_average"] >= 3 and lowest != best:
        insights.append("This supplier has low unit cost but high geopolitical risk.")
    if fastest and fastest["dimension_scores"]["Landed Cost"] < 70 and fastest != lowest:
        insights.append("This supplier has the shortest lead time but weaker cost performance.")
    for supplier in suppliers:
        if (
            normalize_confidence_level(supplier["confidence_level"])
            in {"Manual Review Needed", "Unavailable Online", "AI Estimate"}
            or "pending" in supplier["certifications"].lower()
        ):
            insights.append(
                f"{supplier['name']} needs manual review because quality certification data is missing or incomplete."
            )
    if requirement.get("criticality") in {"High", "Critical"}:
        insights.append("A backup supplier is recommended because this part is marked critical.")
    for metric in metrics:
        if metric["total_lead_time"] > numeric(requirement.get("required_lead_time")):
            insights.append(
                f"{metric['supplier_name']} exceeds the required lead time, reducing flexibility and increasing planning risk."
            )
    insights.append("A quote is not the deal. Contract terms should be reviewed before supplier selection.")
    insights.append("Supplier capability matters more than supplier promises.")
    return list(dict.fromkeys(insights))[:8]


def generate_memo(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> str:
    summary = recommendation_summary(metrics)
    best = summary["best_overall"]
    backup = summary["backup_supplier"]
    lowest = summary["lowest_cost"]
    fastest = summary["fastest_lead_time"]
    highest_risk = summary["highest_risk"]
    supplier_names = ", ".join(supplier["name"] for supplier in suppliers) or "No suppliers added"
    manual_items = [
        f"{metric['supplier_name']}: {', '.join(metric['manual_review_flags'])}"
        for metric in metrics
        if metric.get("manual_review_flags")
    ]
    ranking = " | ".join(
        f"{idx + 1}. {metric['supplier_name']} ({metric['final_score']}/100)"
        for idx, metric in enumerate(sorted(metrics, key=lambda item: item["final_score"], reverse=True))
    )
    return "\n".join(
        [
            "Global Sourcing Copilot Recommendation Memo",
            "",
            f"Product being sourced: {requirement.get('product_name') or 'Not specified'} ({requirement.get('product_category') or 'category not specified'})",
            f"Supplier options reviewed: {supplier_names}",
            "",
            f"Best supplier recommendation: {best['supplier_name'] if best else 'No recommendation available'} with a score of {best['final_score'] if best else 0}/100.",
            f"Recommendation label: {best['recommendation'] if best else 'n/a'}.",
            f"Backup supplier recommendation: {backup['supplier_name'] if backup else 'Add another qualified supplier before award'}.",
            "",
            f"Cost summary: Lowest landed cost is {lowest['supplier_name'] if lowest else 'n/a'} at {format_currency(lowest['total_landed_cost']) if lowest else 'n/a'} per unit. Best overall supplier TCO is {format_currency(best['total_cost_of_ownership']) if best else 'n/a'} per unit.",
            f"Lead time summary: Fastest option is {fastest['supplier_name'] if fastest else 'n/a'} at {format_days(fastest['total_lead_time']) if fastest else 'n/a'}.",
            f"Major risks: Highest combined risk is {highest_risk['supplier_name'] if highest_risk else 'n/a'}; review quality, geopolitical, and logistics assumptions before award.",
            f"Manual review items: {'; '.join(manual_items) if manual_items else 'No manual review flags generated.'}",
            "",
            "Negotiation suggestions: Clarify included cost elements, lock lead-time commitments, request audit and traceability evidence, negotiate payment terms, document warranty and liability coverage, and reserve capacity for the forecast demand.",
            "",
            f"Final recommendation reasoning: {best['supplier_name'] if best else 'The selected supplier'} balances landed cost, total cost of ownership, lead time, supplier capability, and risk better than the other options. Use {backup['supplier_name'] if backup else 'a qualified backup'} as a contingency supplier until production quality and commercial terms are fully validated.",
            "",
            f"Score ranking: {ranking}",
        ]
    )


def metrics_dataframe(metrics: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for metric in metrics:
        rows.append(
            {
                "Supplier": metric["supplier_name"],
                "Final Score": metric["final_score"],
                "Recommendation": metric["recommendation"],
                "Landed / Unit": metric["total_landed_cost"],
                "TCO / Unit": metric["total_cost_of_ownership"],
                "Order TCO": metric["total_order_tco"],
                "Lead Time Days": metric["total_lead_time"],
                "Cost Score": metric["dimension_scores"]["Landed Cost"],
                "TCO Score": metric["dimension_scores"]["TCO"],
                "Lead Time Score": metric["dimension_scores"]["Lead Time"],
                "Capability Score": metric["dimension_scores"]["Capability"],
                "Quality Risk": metric["quality_risk_average"],
                "Compliance Risk": metric["compliance_risk_average"],
                "Geopolitical Risk": metric["geopolitical_risk_average"],
                "Logistics Risk": metric["logistics_risk_average"],
                "Financial Stability": metric["dimension_scores"]["Financial Stability"],
                "Contract Terms": metric["dimension_scores"]["Contract Terms"],
                "Data Confidence": f"{metric['confidence_level']} ({metric['data_confidence_score']}/5)",
                "Manual Review Flags": "; ".join(metric["manual_review_flags"]) or "None",
            }
        )
    return pd.DataFrame(rows)


def format_scorecard_dataframe(score_df: pd.DataFrame) -> pd.DataFrame:
    if score_df.empty:
        return score_df
    display_df = score_df[[col for col in SCORECARD_MAIN_COLUMNS if col in score_df.columns]].copy()
    for col in ["Landed / Unit", "TCO / Unit", "Order TCO"]:
        display_df[col] = display_df[col].map(format_currency)
    display_df["Lead Time Days"] = display_df["Lead Time Days"].map(lambda value: f"{value:.0f}")
    for col in ["Quality Risk", "Compliance Risk", "Geopolitical Risk", "Logistics Risk"]:
        display_df[col] = display_df[col].map(lambda value: f"{value:.1f}/5")
    return display_df


def comparison_csv(suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> str:
    fields = []
    for section in FRAMEWORK_SECTIONS.values():
        fields.extend(section["fields"])
    metric_lookup = {metric["supplier_id"]: metric for metric in metrics}
    rows = []
    for supplier in suppliers:
        metric = metric_lookup.get(supplier["id"], {})
        row = {
            "Supplier": supplier["name"],
            "Country": supplier["country"],
            "Region": supplier["region"],
            "Confidence Level": supplier["confidence_level"],
            "Data Confidence Score": metric.get("data_confidence_score", ""),
            "Recommendation": metric.get("recommendation", ""),
            "Total Landed Cost": metric.get("total_landed_cost", ""),
            "Total Cost of Ownership": metric.get("total_cost_of_ownership", ""),
            "Total Lead Time": metric.get("total_lead_time", ""),
            "Final Score": metric.get("final_score", ""),
            "Cost Score": metric.get("dimension_scores", {}).get("Landed Cost", ""),
            "TCO Score": metric.get("dimension_scores", {}).get("TCO", ""),
            "Lead Time Score": metric.get("dimension_scores", {}).get("Lead Time", ""),
            "Capability Score": metric.get("dimension_scores", {}).get("Capability", ""),
            "Quality Risk": metric.get("quality_risk_average", ""),
            "Compliance Risk": metric.get("compliance_risk_average", ""),
            "Geopolitical Risk": metric.get("geopolitical_risk_average", ""),
            "Logistics Risk": metric.get("logistics_risk_average", ""),
            "Financial Stability": metric.get("dimension_scores", {}).get("Financial Stability", ""),
            "Contract Terms": metric.get("dimension_scores", {}).get("Contract Terms", ""),
            "Manual Review Flags": "; ".join(metric.get("manual_review_flags", [])),
        }
        for key, label, _kind in fields:
            row[label] = supplier["values"].get(key, "")
        rows.append(row)
    buffer = StringIO()
    pd.DataFrame(rows).to_csv(buffer, index=False)
    return buffer.getvalue()


def parse_news_datetime(raw_date: str) -> datetime | None:
    if not raw_date:
        return None
    try:
        parsed = parsedate_to_datetime(raw_date)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_news_date(raw_date: str) -> str:
    parsed = parse_news_datetime(raw_date)
    if parsed is not None:
        return parsed.strftime("%b %d, %Y")
    if raw_date:
        return raw_date
    return "Date unavailable"


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def fetch_weekly_news(query: str, limit: int) -> dict[str, Any]:
    recent_query = f"{query} when:{NEWS_LOOKBACK_DAYS}d"
    encoded_query = quote_plus(recent_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    search_url = f"https://news.google.com/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    fetched_at_dt = datetime.now(timezone.utc)
    fetched_at = fetched_at_dt.strftime("%b %d, %Y %H:%M UTC")
    cutoff = fetched_at_dt - timedelta(days=NEWS_LOOKBACK_DAYS)
    try:
        request = Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            raw_xml = response.read()
        root = ET.fromstring(raw_xml)
        articles = []
        for item in root.findall("./channel/item"):
            pub_date_raw = item.findtext("pubDate") or ""
            published_at = parse_news_datetime(pub_date_raw)
            if published_at is None or published_at < cutoff:
                continue
            source = item.findtext("source") or "Google News"
            articles.append(
                {
                    "title": unescape(item.findtext("title") or "Untitled article"),
                    "link": item.findtext("link") or "",
                    "source": unescape(source),
                    "published": parse_news_date(pub_date_raw),
                }
            )
            if len(articles) >= limit:
                break
        return {
            "articles": articles,
            "error": "",
            "rss_url": rss_url,
            "search_url": search_url,
            "fetched_at": fetched_at,
            "lookback_days": NEWS_LOOKBACK_DAYS,
        }
    except Exception as error:  # noqa: BLE001 - show a friendly app-level fallback.
        return {
            "articles": [],
            "error": str(error),
            "rss_url": rss_url,
            "search_url": search_url,
            "fetched_at": fetched_at,
            "lookback_days": NEWS_LOOKBACK_DAYS,
        }


def render_header() -> None:
    st.title("Global Sourcing Copilot")
    st.markdown(
        '<p class="app-kicker">Structured workspace for supplier comparison, landed cost, lead time, risk, confidence, and award recommendations.</p>',
        unsafe_allow_html=True,
    )


def render_welcome() -> None:
    st.markdown(
        """
        <section class="intro-panel">
            <h1>Global Sourcing Copilot</h1>
            <p>
                A practical sourcing workspace for comparing suppliers with the same framework an analyst would use:
                requirements, landed cost, total cost of ownership, lead time, capability, risk, data confidence,
                and recommendation logic in one place.
            </p>
            <div class="intro-points">
                <div class="intro-point">
                    <strong>Start with requirements</strong>
                    <span>Capture product, compliance, quality, volume, lead-time, and delivery needs.</span>
                </div>
                <div class="intro-point">
                    <strong>Compare suppliers</strong>
                    <span>Score cost, TCO, capability, risk, financial stability, and contract terms.</span>
                </div>
                <div class="intro-point">
                    <strong>Export a decision</strong>
                    <span>Review the dashboard, flags, and sourcing memo before shortlisting or award.</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    action_cols = st.columns([0.24, 0.24, 0.52])
    if action_cols[0].button("Continue", type="primary", width="stretch"):
        navigate_to_page("Product")
        st.rerun()
    if action_cols[1].button("Load demo", width="stretch"):
        load_demo_data()
        st.rerun()


def render_navigation() -> str:
    render_header()
    action_cols = st.columns([0.58, 0.14, 0.14, 0.14])
    if action_cols[1].button("Overview", width="stretch"):
        show_welcome()
        st.rerun()
    if action_cols[2].button("Load demo", width="stretch"):
        load_demo_data()
        st.rerun()
    if action_cols[3].button("Start fresh", width="stretch"):
        reset_workspace()
        st.rerun()

    if st.session_state.workspace_page not in WORKFLOW_PAGES:
        st.session_state.workspace_page = "Product"
    with st.container(key="workflow_navigation"):
        page = st.radio(
            "Workflow",
            WORKFLOW_PAGES,
            key="workspace_page",
            horizontal=True,
            label_visibility="collapsed",
        )
    return page


def render_summary(metrics: list[dict[str, Any]], review: dict[str, Any]) -> None:
    summary = recommendation_summary(metrics)
    completed_fields, total_fields = requirement_progress(st.session_state.requirement)
    cols = st.columns(4)
    if not metrics:
        cols[0].metric("Workflow", "1", "Define product")
        cols[1].metric("Requirement fields", f"{completed_fields}/{total_fields}", "Complete intake")
        cols[2].metric("Suppliers added", len(st.session_state.suppliers), "Add 2+ options")
        cols[3].metric("Recommendation", "Not ready", review["risk_tier"])
        return

    cols[0].metric(
        "Best overall",
        summary["best_overall"]["supplier_name"] if summary["best_overall"] else "No supplier",
        f"{summary['best_overall']['final_score'] if summary['best_overall'] else 0}/100 score",
    )
    cols[1].metric(
        "Lowest landed cost",
        format_currency(summary["lowest_cost"]["total_landed_cost"]) if summary["lowest_cost"] else "n/a",
        summary["lowest_cost"]["supplier_name"] if summary["lowest_cost"] else "Add suppliers",
    )
    cols[2].metric(
        "Fastest lead time",
        format_days(summary["fastest_lead_time"]["total_lead_time"])
        if summary["fastest_lead_time"]
        else "n/a",
        summary["fastest_lead_time"]["supplier_name"] if summary["fastest_lead_time"] else "Add suppliers",
    )
    cols[3].metric("Active suppliers", len(st.session_state.suppliers), review["risk_tier"])


def render_guide(requirement: dict[str, Any], metrics: list[dict[str, Any]]) -> None:
    completed_fields, total_fields = requirement_progress(requirement)
    suppliers_count = len(st.session_state.suppliers)

    st.subheader("Workflow Guide")
    st.caption("Use this workflow to build a sourcing recommendation from your own inputs.")

    step_cols = st.columns(4)
    step_cols[0].metric("1. Product intake", f"{completed_fields}/{total_fields}", "required fields")
    step_cols[1].metric("2. Suppliers", suppliers_count, "options added")
    step_cols[2].metric("3. Framework", "Ready" if suppliers_count else "Waiting", "editable table")
    step_cols[3].metric("4. Memo", "Ready" if metrics else "Waiting", "after scoring")

    st.markdown("### Recommended path")
    st.markdown(
        """
        1. Open **Product** and enter the product, volume, quality, compliance, lead-time, and delivery requirements, or upload a sourcing Excel file to prefill matching fields.
        2. Open **Suppliers** and add suppliers manually, or use **Add sample supplier** for clearly labeled placeholder options.
        3. Open **Framework** and fill in cost, lead-time, capability, risk, logistics, and contract assumptions.
        4. Open **Weights** to tune the category weights and individual field weights.
        5. Open **Dashboard** to compare landed cost, total cost of ownership, lead time, risk, and supplier score.
        6. Open **Export** to download the supplier table and sourcing memo.
        7. Open **News** to scan current sourcing, trade, logistics, and supplier-risk updates when you want external context.
        """
    )

    st.markdown("### Optional demo")
    st.write("Use the demo only if you want to see the full dashboard behavior before entering real sourcing data.")
    demo_col, fresh_col = st.columns(2)
    demo_col.button("Load demo data", type="primary", width="stretch", on_click=load_demo_data)
    fresh_col.button(
        "Start with product intake",
        width="stretch",
        on_click=navigate_to_page,
        args=("Product",),
    )


def render_excel_importer() -> None:
    with st.expander("Upload sourcing Excel file", expanded=False):
        st.caption(
            "Upload an .xlsx workbook to extract matching product requirements and supplier rows. Empty or unmatched fields stay blank."
        )
        uploaded_file = st.file_uploader(
            "Sourcing Excel workbook",
            type=["xlsx", "xlsm"],
            key="sourcing_excel_upload",
        )
        if uploaded_file is None:
            return

        parsed = parse_sourcing_workbook(uploaded_file.getvalue())
        if parsed["errors"]:
            st.error(parsed["errors"][0])
            return

        req_count = len(parsed["requirement"])
        supplier_count = len(parsed["suppliers"])
        summary_cols = st.columns(2)
        summary_cols[0].metric("Requirement fields found", req_count)
        summary_cols[1].metric("Supplier rows found", supplier_count)

        if req_count == 0 and supplier_count == 0:
            st.info(
                "No matching fields were found. Try headers like Product Name, Quantity, Target Cost, Supplier Name, Country, Unit Cost, MOQ, or Lead Time."
            )
            return

        if req_count:
            st.markdown("#### Requirement preview")
            requirement_preview = pd.DataFrame(
                [
                    {"Field": key.replace("_", " ").title(), "Value": value}
                    for key, value in parsed["requirement"].items()
                ]
            )
            st.dataframe(requirement_preview, width="stretch", hide_index=True)

        if supplier_count:
            st.markdown("#### Supplier preview")
            supplier_preview = pd.DataFrame(
                [
                    {
                        "Supplier": supplier["name"],
                        "Country": supplier["country"],
                        "Region": supplier["region"],
                        "Capacity": supplier["annual_capacity"] or "",
                        "Confidence": supplier["confidence_level"],
                    }
                    for supplier in parsed["suppliers"]
                ]
            )
            st.dataframe(supplier_preview.head(25), width="stretch", hide_index=True)

        if st.button("Apply extracted data", type="primary", width="stretch"):
            apply_sourcing_import(parsed)
            st.success(
                f"Applied {req_count} requirement fields and {supplier_count} supplier rows from the workbook."
            )


def render_intake(requirement: dict[str, Any], review: dict[str, Any]) -> None:
    st.subheader("Product Requirement Intake")
    st.caption("Define the product, quality, compliance, demand, and delivery constraints.")
    render_excel_importer()

    col1, col2 = st.columns(2)
    with col1:
        requirement["product_name"] = st.text_input("Product name", requirement["product_name"])
        requirement["quantity"] = st.number_input("Quantity", min_value=0, step=1000, value=int(requirement["quantity"]))
        requirement["required_lead_time"] = st.number_input(
            "Required lead time", min_value=0, step=1, value=int(requirement["required_lead_time"])
        )
        requirement["criticality"] = st.selectbox(
            "Criticality level",
            CRITICALITY_LEVELS,
            index=CRITICALITY_LEVELS.index(requirement["criticality"]),
        )
    with col2:
        requirement["product_category"] = st.text_input("Product category", requirement["product_category"])
        requirement["target_cost"] = st.number_input(
            "Target cost", min_value=0.0, step=0.25, value=float(requirement["target_cost"])
        )
        requirement["forecasted_demand"] = st.number_input(
            "Forecasted demand", min_value=0, step=1000, value=int(requirement["forecasted_demand"])
        )
        requirement["delivery_location"] = st.text_input("Delivery location", requirement["delivery_location"])

    requirement["product_specs"] = st.text_area("Product specs", requirement["product_specs"], height=90)
    col3, col4 = st.columns(2)
    with col3:
        requirement["quality_requirements"] = st.text_area(
            "Quality requirements", requirement["quality_requirements"], height=100
        )
        requirement["approved_materials"] = st.text_area(
            "Approved materials", requirement["approved_materials"], height=100
        )
    with col4:
        requirement["compliance_requirements"] = st.text_area(
            "Compliance requirements", requirement["compliance_requirements"], height=100
        )
        requirement["technical_drawings"] = st.text_area(
            "Technical drawings link or notes", requirement["technical_drawings"], height=100
        )
    requirement["packaging_requirements"] = st.text_area(
        "Packaging requirements", requirement["packaging_requirements"], height=90
    )

    st.markdown("### Requirement Review")
    review_cols = st.columns(4)
    review_cols[0].write("**Missing information**")
    review_cols[0].write("\n".join(f"- {item}" for item in review["missing"]) or "No major missing fields.")
    review_cols[1].write("**Potential sourcing risks**")
    review_cols[1].write("\n".join(f"- {item}" for item in review["risks"]) or "No material risks detected.")
    review_cols[2].write("**Questions for suppliers**")
    review_cols[2].write("\n".join(f"- {item}" for item in review["questions"][:4]))
    review_cols[3].write("**Suggested strategy**")
    review_cols[3].write(review["strategy"])
    st.session_state.requirement = requirement


def render_supplier_discovery(requirement: dict[str, Any]) -> None:
    st.subheader("Supplier Discovery")
    st.caption("Add suppliers manually or create clearly labeled sample suppliers for testing.")
    if st.button("Add sample supplier", type="primary"):
        template = deepcopy(SAMPLE_SUPPLIERS[len(st.session_state.suppliers) % len(SAMPLE_SUPPLIERS)])
        category = requirement.get("product_category") or "target product"
        template.update(
            {
                    "id": f"sample-supplier-{len(st.session_state.suppliers) + 1}",
                "name": f"{category} Sample Supplier {len(st.session_state.suppliers) + 1}",
                "country": "Manual verification needed",
                "region": "Suggested region",
                "website": "Unavailable online",
                "product_match": f"Sample match for {category}. Verify capability before outreach.",
                "certifications": "Unavailable Online",
                "annual_capacity": max(50000, int(numeric(requirement.get("forecasted_demand")))),
                "customer_notes": "Sample supplier generated from the product category. Treat as placeholder data only.",
                "confidence_level": "AI Estimate",
            }
        )
        template["values"]["unit_cost"] = float(numeric(requirement.get("target_cost")) or 8.5)
        template["values"]["certification_risk"] = 4
        template["values"]["audit_result_risk"] = 4
        template["values"]["documentation_ability"] = 2
        template["values"]["contract_payment_terms"] = "Unknown; request in RFQ"
        st.session_state.suppliers.append(template)
        st.success("Added a sample supplier. Manual verification required.")

    for idx, supplier in enumerate(st.session_state.suppliers):
        with st.expander(f"{supplier['name']} - {supplier['confidence_level']}", expanded=idx < 3):
            col1, col2 = st.columns(2)
            supplier["name"] = col1.text_input("Supplier name", supplier["name"], key=f"name_{supplier['id']}")
            supplier["confidence_level"] = col2.selectbox(
                "Confidence level",
                CONFIDENCE_LEVELS,
                index=CONFIDENCE_LEVELS.index(supplier["confidence_level"]),
                key=f"confidence_{supplier['id']}",
            )
            supplier["country"] = col1.text_input("Country", supplier["country"], key=f"country_{supplier['id']}")
            supplier["region"] = col2.text_input("Region", supplier["region"], key=f"region_{supplier['id']}")
            supplier["website"] = col1.text_input("Website", supplier["website"], key=f"website_{supplier['id']}")
            supplier["annual_capacity"] = col2.number_input(
                "Estimated annual capacity",
                min_value=0,
                step=1000,
                value=int(supplier["annual_capacity"]),
                key=f"capacity_{supplier['id']}",
            )
            supplier["product_match"] = st.text_area(
                "Product match", supplier["product_match"], key=f"match_{supplier['id']}"
            )
            supplier["certifications"] = st.text_input(
                "Certifications", supplier["certifications"], key=f"certs_{supplier['id']}"
            )
            supplier["customer_notes"] = st.text_area(
                "Current customer notes", supplier["customer_notes"], key=f"notes_{supplier['id']}"
            )
            if st.button("Remove supplier", key=f"remove_{supplier['id']}"):
                st.session_state.suppliers.pop(idx)
                st.rerun()

    st.markdown("### Add supplier")
    with st.form("add_supplier_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Supplier name")
        country = col2.text_input("Country")
        region = col1.text_input("Region")
        website = col2.text_input("Website")
        product_match = st.text_input("Product match")
        certifications = st.text_input("Certifications")
        annual_capacity = st.number_input("Estimated annual capacity", min_value=0, step=1000)
        confidence = st.selectbox("Confidence level", CONFIDENCE_LEVELS, index=4)
        customer_notes = st.text_area("Current customer notes")
        submitted = st.form_submit_button("Add supplier")
        if submitted and name.strip():
            st.session_state.suppliers.append(
                {
                    "id": f"supplier-{len(st.session_state.suppliers) + 1}",
                    "name": name,
                    "country": country,
                    "region": region,
                    "website": website,
                    "product_match": product_match,
                    "certifications": certifications,
                    "annual_capacity": int(annual_capacity),
                    "customer_notes": customer_notes,
                    "confidence_level": confidence,
                    "values": default_values(),
                }
            )
            st.success("Supplier added.")


def render_framework_table() -> None:
    st.subheader("Global Sourcing Framework Table")
    if not st.session_state.suppliers:
        st.info("Add at least one supplier in Supplier Discovery before editing the framework table.")
        return

    selected_label = st.selectbox(
        "Framework category",
        [section["label"] for section in FRAMEWORK_SECTIONS.values()],
    )
    section_key = next(
        key for key, section in FRAMEWORK_SECTIONS.items() if section["label"] == selected_label
    )
    section = FRAMEWORK_SECTIONS[section_key]
    st.caption(section["description"])

    rows = []
    for supplier in st.session_state.suppliers:
        row = {"Supplier": supplier["name"], "Confidence Level": supplier["confidence_level"]}
        for key, label, _kind in section["fields"]:
            row[label] = supplier["values"].get(key, "")
        rows.append(row)
    edited = st.data_editor(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key=f"framework_{section_key}",
    )

    for idx, supplier in enumerate(st.session_state.suppliers):
        if idx >= len(edited):
            continue
        supplier["name"] = str(edited.at[idx, "Supplier"])
        supplier["confidence_level"] = normalize_confidence_level(edited.at[idx, "Confidence Level"])
        for key, label, kind in section["fields"]:
            value = edited.at[idx, label]
            supplier["values"][key] = str(value) if kind == "text" else numeric(value)


def render_scoring(metrics: list[dict[str, Any]]) -> None:
    st.subheader("Scoring Weights")
    st.caption(
        "Tune how the sourcing framework scores suppliers. Risk inputs are inverted so lower risk improves score."
    )
    category_tab, field_tab, scorecard_tab = st.tabs(
        ["Scoring Weights", "Field weights", "Scorecard"]
    )

    with category_tab:
        st.markdown("### Scoring Weights")
        st.write("Category weights control how each major scoring dimension contributes to the final supplier score.")
        col1, col2 = st.columns([0.35, 0.65])
        with col1:
            if st.button("Reset category weights"):
                st.session_state.weights = deepcopy(DEFAULT_WEIGHTS)
                sync_category_weight_widgets()
                st.rerun()
        with col2:
            st.info("The default model totals 100% and follows the scoring framework in the guide.")

        for key, label in WEIGHT_LABELS.items():
            st.session_state.weights[key] = st.number_input(
                label,
                min_value=0,
                max_value=100,
                value=int(st.session_state.weights[key]),
                step=1,
                key=f"weight_{key}",
            )
        weight_total = sum(st.session_state.weights.values())
        st.metric("Total weight", f"{weight_total}%")
        if weight_total != 100:
            st.warning("Weights should equal 100% for the clearest audit trail. The app normalizes the score if they do not.")
        else:
            st.success("Weights total 100%.")

    with field_tab:
        st.write(
            "Field weights control how strongly each framework input affects its category. Use 0 to ignore a field, 1 for normal importance, and higher values for stronger emphasis."
        )
        field_cols = st.columns([0.35, 0.35, 0.30])
        section_options = ["All categories"] + [section["label"] for section in FRAMEWORK_SECTIONS.values()]
        selected_label = field_cols[0].selectbox(
            "Framework category",
            section_options,
            key="field_weight_category_filter",
        )
        max_weight = field_cols[1].number_input(
            "Maximum field weight",
            min_value=1.0,
            max_value=25.0,
            value=10.0,
            step=1.0,
        )
        if field_cols[2].button("Reset field weights", width="stretch"):
            st.session_state.field_weights = default_field_weights()
            st.session_state.field_weight_editor_version += 1
            st.rerun()

        selected_section_key = None
        if selected_label != "All categories":
            selected_section_key = next(
                key for key, section in FRAMEWORK_SECTIONS.items() if section["label"] == selected_label
            )

        rows = []
        for field in all_framework_fields():
            if selected_section_key and field["section_key"] != selected_section_key:
                continue
            rows.append(
                {
                    "Key": field["key"],
                    "Section": field["section"],
                    "Field": field["label"],
                    "Type": FIELD_KIND_LABELS.get(field["kind"], field["kind"]),
                    "Weight": float(st.session_state.field_weights.get(field["key"], 1.0)),
                }
            )

        edited = st.data_editor(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
            disabled=["Section", "Field", "Type"],
            column_config={
                "Key": None,
                "Weight": st.column_config.NumberColumn(
                    "Weight",
                    min_value=0.0,
                    max_value=float(max_weight),
                    step=0.25,
                    format="%.2f",
                ),
            },
            key=f"field_weights_{selected_label}_{st.session_state.field_weight_editor_version}",
        )

        changed = False
        for _idx, row in edited.iterrows():
            key = str(row["Key"])
            next_weight = field_weight({"weight": row["Weight"]}, "weight")
            if st.session_state.field_weights.get(key, 1.0) != next_weight:
                st.session_state.field_weights[key] = next_weight
                changed = True
        if changed:
            st.rerun()

        st.caption(
            "Cost and lead-time field weights influence the score basis. The dashboard still displays actual additive cost and lead-time totals."
        )

    with scorecard_tab:
        score_df = metrics_dataframe(metrics)
        if not score_df.empty:
            st.dataframe(format_scorecard_dataframe(score_df), width="stretch", hide_index=True)
        else:
            st.info("Add suppliers to calculate scores.")


def format_field_value(value: Any, kind: str) -> str:
    if kind == "currency":
        return format_currency(numeric(value))
    if kind == "days":
        return format_days(numeric(value))
    if kind in {"score", "risk"}:
        return f"{bounded_score(value):.1f}/5"
    if kind == "number":
        return f"{numeric(value):,.0f}"
    return clean_cell(value) or "Blank"


def section_breakdown_dataframe(
    supplier: dict[str, Any], section_key: str, field_weights: dict[str, float]
) -> pd.DataFrame:
    rows = []
    for key, label, kind in FRAMEWORK_SECTIONS[section_key]["fields"]:
        value = supplier["values"].get(key, "")
        adjusted_score = ""
        if kind == "risk":
            adjusted_score = f"{convert_risk_to_score(bounded_score(value)):.1f}/5"
        elif kind == "score":
            adjusted_score = f"{bounded_score(value):.1f}/5"
        rows.append(
            {
                "Factor": label,
                "Input": format_field_value(value, kind),
                "Score Used": adjusted_score,
                "Field Weight": field_weight(field_weights, key),
            }
        )
    return pd.DataFrame(rows)


def render_score_explanations() -> None:
    st.markdown("### How the Supplier Score is Calculated")
    for explanation in SCORE_EXPLANATIONS:
        with st.expander(explanation["title"]):
            st.markdown(f"**What it measures:** {explanation['measures']}")
            st.markdown(f"**Subfactors included:** {explanation['subfactors']}")
            st.markdown(f"**Direction:** {explanation['direction']}")
            st.markdown(f"**Calculation:** {explanation['calculation']}")
            st.markdown(f"**Why it matters:** {explanation['why']}")


def render_supplier_detail_sections(
    metrics: list[dict[str, Any]], suppliers: list[dict[str, Any]]
) -> None:
    st.markdown("### Supplier Detail Breakdowns")
    metric_lookup = {metric["supplier_id"]: metric for metric in metrics}
    for supplier in suppliers:
        metric = metric_lookup.get(supplier["id"])
        if not metric:
            continue
        title = f"{supplier['name']} - Score Breakdown"
        with st.expander(title):
            st.markdown(
                f"**Recommendation:** {metric['recommendation']}  \n"
                f"**Final score:** {metric['final_score']}/100  \n"
                f"**Data confidence:** {metric['confidence_level']} ({metric['data_confidence_score']}/5)"
            )
            if metric["manual_review_flags"]:
                st.warning("; ".join(metric["manual_review_flags"]))
            else:
                st.success("No manual review flags generated.")

            cost_cols = st.columns(4)
            cost_cols[0].metric("Landed / unit", format_currency(metric["total_landed_cost"]))
            cost_cols[1].metric("TCO / unit", format_currency(metric["total_cost_of_ownership"]))
            cost_cols[2].metric("Lead time", format_days(metric["total_lead_time"]))
            cost_cols[3].metric("Final score", f"{metric['final_score']}/100")

            st.markdown("#### Cost breakdown")
            st.dataframe(
                section_breakdown_dataframe(supplier, "cost", st.session_state.field_weights),
                width="stretch",
                hide_index=True,
            )

            st.markdown("#### Lead time breakdown")
            st.dataframe(
                section_breakdown_dataframe(supplier, "lead_time", st.session_state.field_weights),
                width="stretch",
                hide_index=True,
            )

            score_sections = [
                ("capability", "Capability subfactor scores"),
                ("quality_risk", "Quality risk subfactor scores"),
                ("compliance", "Compliance subfactor scores"),
                ("geopolitical_risk", "Geopolitical risk subfactor scores"),
                ("logistics", "Logistics risk subfactor scores"),
                ("financial_stability", "Financial stability subfactor scores"),
                ("contract", "Contract terms subfactor scores"),
            ]
            for section_key, label in score_sections:
                st.markdown(f"#### {label}")
                st.dataframe(
                    section_breakdown_dataframe(supplier, section_key, st.session_state.field_weights),
                    width="stretch",
                    hide_index=True,
                )

            st.markdown("#### Sourcing notes")
            st.write(supplier.get("customer_notes") or "No sourcing notes entered.")


def render_supplier_scorecard(metrics: list[dict[str, Any]], suppliers: list[dict[str, Any]]) -> None:
    st.markdown("### Supplier scorecard")
    score_df = metrics_dataframe(metrics)
    if score_df.empty:
        st.info("Add suppliers to calculate the scorecard.")
        return
    st.dataframe(format_scorecard_dataframe(score_df), width="stretch", hide_index=True)
    render_supplier_detail_sections(metrics, suppliers)
    render_score_explanations()


def render_weekly_news() -> None:
    st.subheader("Weekly Sourcing News")
    st.caption("Current external news from the past 30 days, cached for one week to keep the app quick and stable.")

    control_cols = st.columns([0.35, 0.45, 0.20])
    topic = control_cols[0].selectbox("News focus", list(NEWS_TOPICS.keys()) + ["Custom"])
    default_query = NEWS_TOPICS.get(topic, NEWS_TOPICS["Global sourcing"])
    query = control_cols[1].text_input("Search terms", value=default_query)
    article_limit = control_cols[2].number_input("Articles", min_value=3, max_value=12, value=8, step=1)

    refresh_col, source_col = st.columns([0.25, 0.75])
    if refresh_col.button("Refresh news now", width="stretch"):
        fetch_weekly_news.clear()
        st.rerun()

    news = fetch_weekly_news(query.strip() or NEWS_TOPICS["Global sourcing"], int(article_limit))
    source_col.markdown(f"[Open Google News search from past 30 days]({news['search_url']})")
    st.caption(f"Showing articles from the past {news['lookback_days']} days. Last checked: {news['fetched_at']}")

    if news["error"]:
        st.warning("The news feed could not be reached right now. Try refreshing later.")
        st.caption(news["error"])
        return

    if not news["articles"]:
        st.info("No matching articles from the past 30 days were returned. Try broader sourcing or supply chain terms.")
        return

    for article in news["articles"]:
        with st.container(border=True):
            title = article["title"]
            link = article["link"]
            if link:
                st.markdown(f"**[{title}]({link})**")
            else:
                st.markdown(f"**{title}**")
            st.caption(f"{article['source']} | {article['published']}")


def render_dashboard(metrics: list[dict[str, Any]]) -> None:
    st.subheader("Dashboard")
    if not metrics:
        st.info("The dashboard is blank until you add suppliers and framework assumptions.")
        st.markdown(
            """
            **Recommended next steps**

            1. Complete Product.
            2. Add at least two suppliers.
            3. Fill in cost and lead-time assumptions in Framework.
            4. Return here for charts and scoring.
            """
        )
        return

    score_df = metrics_dataframe(metrics)

    col1, col2 = st.columns(2)
    fig_score = px.bar(
        score_df.sort_values("Final Score", ascending=False),
        x="Supplier",
        y="Final Score",
        color="Final Score",
        title="Final supplier score",
        color_continuous_scale=["#dc2626", "#f59e0b", "#0f766e"],
        text="Final Score",
    )
    fig_score.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    fig_score.update_traces(textposition="outside")
    col1.plotly_chart(fig_score, width="stretch")

    fig_landed = px.bar(
        score_df.sort_values("Landed / Unit"),
        x="Supplier",
        y="Landed / Unit",
        title="Total landed cost per unit",
        color="Landed / Unit",
        color_continuous_scale=["#0f766e", "#f59e0b", "#dc2626"],
    )
    fig_landed.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    col2.plotly_chart(fig_landed, width="stretch")

    col3, col4 = st.columns(2)
    fig_tco = px.bar(
        score_df.sort_values("TCO / Unit"),
        x="Supplier",
        y="TCO / Unit",
        title="Total cost of ownership per unit",
        color="TCO / Unit",
        color_continuous_scale=["#0f766e", "#f59e0b", "#dc2626"],
    )
    fig_tco.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    col3.plotly_chart(fig_tco, width="stretch")

    lead_df = score_df[["Supplier", "Lead Time Days"]]
    fig_lead = px.bar(
        lead_df,
        x="Supplier",
        y="Lead Time Days",
        title="Lead time comparison",
        color="Lead Time Days",
        color_continuous_scale=["#0f766e", "#f59e0b", "#dc2626"],
    )
    fig_lead.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    col4.plotly_chart(fig_lead, width="stretch")

    heatmap = pd.DataFrame(
        [
            {
                "Supplier": metric["supplier_name"],
                "Quality Risk": metric["quality_risk_average"],
                "Compliance Risk": metric["compliance_risk_average"],
                "Geopolitical Risk": metric["geopolitical_risk_average"],
                "Logistics Risk": metric["logistics_risk_average"],
                "Financial Stability Risk": 6 - metric["financial_stability_score"],
            }
            for metric in metrics
        ]
    ).set_index("Supplier")
    fig_heat = px.imshow(
        heatmap,
        text_auto=".1f",
        aspect="auto",
        title="Risk heatmap",
        color_continuous_scale=["#10b981", "#f59e0b", "#dc2626"],
        zmin=1,
        zmax=5,
    )
    fig_heat.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20))

    radar_fig = go.Figure()
    for metric in metrics:
        dimensions = list(metric["dimension_scores"].keys())
        values = list(metric["dimension_scores"].values())
        radar_fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=dimensions + [dimensions[0]],
                fill="toself",
                name=short_name(metric["supplier_name"]),
            )
        )
    radar_fig.update_layout(
        title="Radar comparison",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=420,
        margin=dict(l=20, r=20, t=55, b=20),
    )

    col5, col6 = st.columns(2)
    col5.plotly_chart(fig_heat, width="stretch")
    col6.plotly_chart(radar_fig, width="stretch")

    render_supplier_scorecard(metrics, st.session_state.suppliers)


def render_insights(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> None:
    st.subheader("Sourcing Notes")
    st.caption("Rule-based review notes. Validate supplier data manually before final award.")
    if not suppliers:
        st.info("Insights will appear after you add product requirements and supplier options.")
        return
    for insight in build_insights(requirement, suppliers, metrics):
        st.warning(insight)


def render_recommendation(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> None:
    st.subheader("Final Sourcing Recommendation")
    if not suppliers:
        st.info("The recommendation memo will be generated after you add suppliers and scoring assumptions.")
        return
    memo = generate_memo(requirement, suppliers, metrics)
    st.text_area("Recommendation memo", memo, height=460)
    col1, col2 = st.columns(2)
    col1.download_button(
        "Download supplier comparison CSV",
        data=comparison_csv(suppliers, metrics),
        file_name="supplier-comparison.csv",
        mime="text/csv",
        width="stretch",
    )
    col2.download_button(
        "Download recommendation memo",
        data=memo,
        file_name="sourcing-recommendation.txt",
        mime="text/plain",
        width="stretch",
    )


def main() -> None:
    add_css()
    initialize_state()
    sync_weight_inputs()

    requirement = st.session_state.requirement
    suppliers = st.session_state.suppliers
    weights = st.session_state.weights
    field_weights = st.session_state.field_weights
    metrics = calculate_metrics(
        suppliers,
        weights,
        numeric(requirement.get("quantity")),
        field_weights,
        requirement,
    )
    review = analyze_requirement(requirement)

    if not st.session_state.app_started:
        render_welcome()
        st.caption("Session data stays in this Streamlit session. Use demo data only when you want a sample case.")
        return

    page = render_navigation()
    render_summary(metrics, review)
    st.divider()

    if page == "Dashboard":
        render_dashboard(metrics)
    elif page == "Product":
        render_intake(requirement, review)
    elif page == "Suppliers":
        render_supplier_discovery(requirement)
    elif page == "Framework":
        render_framework_table()
    elif page == "Weights":
        render_scoring(metrics)
    elif page == "Notes":
        render_insights(requirement, suppliers, metrics)
    elif page == "Export":
        render_recommendation(requirement, suppliers, metrics)
    elif page == "News":
        render_weekly_news()

    st.caption(
        "This Streamlit app uses session state. Demo data is optional. Weekly news uses public RSS; no backend integrations are connected."
    )


if __name__ == "__main__":
    main()
