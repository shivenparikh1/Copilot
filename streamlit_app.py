from __future__ import annotations

from copy import deepcopy
from io import StringIO
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Global Sourcing Copilot",
    layout="wide",
    initial_sidebar_state="expanded",
)


CONFIDENCE_LEVELS = [
    "Verified",
    "Estimated",
    "AI Suggested",
    "Needs Manual Review",
    "Unavailable Online",
]

CRITICALITY_LEVELS = ["Low", "Medium", "High", "Critical"]

DEFAULT_WEIGHTS = {
    "landed_cost": 20,
    "tco": 15,
    "lead_time": 15,
    "capability": 15,
    "quality_risk": 15,
    "geopolitical_risk": 10,
    "logistics": 5,
    "contract": 5,
}

WEIGHT_LABELS = {
    "landed_cost": "Total Landed Cost",
    "tco": "Total Cost of Ownership",
    "lead_time": "Lead Time",
    "capability": "Supplier Capability",
    "quality_risk": "Quality Risk",
    "geopolitical_risk": "Geopolitical Risk",
    "logistics": "Logistics Complexity",
    "contract": "Contract Terms",
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
            ("financial_stability", "Financial stability score", "score"),
            ("scaling_ability", "Scaling ability score", "score"),
            ("engineering_support", "Engineering support score", "score"),
            ("compliance_understanding", "Compliance understanding score", "score"),
            ("documentation_ability", "Documentation ability score", "score"),
            ("single_factory_dependency", "Single factory dependency score", "score"),
            ("backup_capacity", "Backup capacity score", "score"),
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
    "geopolitical_risk": {
        "label": "Geopolitical Risk",
        "description": "Country and trade exposure scores from 1 low to 5 high.",
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
        ],
    },
    "logistics": {
        "label": "Logistics Complexity",
        "description": "Logistics and import complexity scores from 1 low to 5 high.",
        "fields": [
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
    "contract": {
        "label": "Contract Terms",
        "description": "Commercial terms and contract quality assumptions.",
        "fields": [
            ("contract_payment_terms", "Payment terms", "text"),
            ("contract_moq", "MOQ", "number"),
            ("volume_discounts", "Volume discounts", "text"),
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
    "contract_payment_terms": "Net 45 after inspection",
    "contract_moq": 25000,
    "volume_discounts": "2% over 75k units",
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
            "production_lead_time": 30,
            "transit_time": 22,
            "buffer_time": 6,
            "volume_capability": 5,
            "scaling_ability": 4,
            "engineering_support": 4,
            "backup_capacity": 4,
            "port_congestion_risk": 2,
            "contract_payment_terms": "Net 60 after PPAP approval",
            "contract_moq": 30000,
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
        "confidence_level": "Needs Manual Review",
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
            "production_lead_time": 24,
            "raw_materials_lead_time": 12,
            "transit_time": 26,
            "buffer_time": 9,
            "quality_certification": 3,
            "compliance_understanding": 3,
            "documentation_ability": 3,
            "defect_rate_risk": 3,
            "certification_risk": 4,
            "traceability_risk": 3,
            "audit_result_risk": 3,
            "trade_war_exposure": 4,
            "tariff_risk": 4,
            "export_control_risk": 3,
            "government_policy_risk": 3,
            "single_country_dependency_risk": 4,
            "duties_taxes_risk": 4,
            "contract_payment_terms": "30% deposit, balance before shipment",
            "contract_moq": 40000,
            "volume_discounts": "4% over 120k units",
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
        "confidence_level": "Estimated",
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
            "defect_rate_risk": 2,
            "process_control_risk": 2,
            "warranty_claim_risk": 1,
            "trade_war_exposure": 1,
            "tariff_risk": 1,
            "export_control_risk": 1,
            "port_disruption_risk": 1,
            "currency_instability_risk": 3,
            "single_country_dependency_risk": 2,
            "incoterms_complexity": 1,
            "ocean_freight_risk": 1,
            "port_congestion_risk": 1,
            "freight_forwarder_requirement": 1,
            "import_documentation_risk": 1,
            "duties_taxes_risk": 1,
            "contract_payment_terms": "Net 30 after receipt",
            "contract_moq": 15000,
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
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        [data-testid="stSidebar"] { background: #020617; }
        [data-testid="stSidebar"] * { color: #e2e8f0; }
        .small-muted { color: #64748b; font-size: 0.9rem; }
        .risk-low { color: #047857; font-weight: 700; }
        .risk-med { color: #b45309; font-weight: 700; }
        .risk-high { color: #b91c1c; font-weight: 700; }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 1rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        }
        div[data-testid="stMetric"] * {
            color: #0f172a !important;
        }
        div[data-testid="stMetricDelta"] * {
            color: #047857 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state() -> None:
    if "requirement" not in st.session_state:
        st.session_state.requirement = deepcopy(SAMPLE_REQUIREMENT)
    if "suppliers" not in st.session_state:
        st.session_state.suppliers = deepcopy(SAMPLE_SUPPLIERS)
    if "weights" not in st.session_state:
        st.session_state.weights = deepcopy(DEFAULT_WEIGHTS)


def numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def supplier_numeric(supplier: dict[str, Any], key: str) -> float:
    return numeric(supplier["values"].get(key))


def format_currency(value: float) -> str:
    if abs(value) >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def format_days(value: float) -> str:
    return f"{value:,.0f} days"


def short_name(name: str) -> str:
    parts = [part for part in name.split() if len(part) > 2]
    return " ".join(parts[:2]) or name


def average_section(supplier: dict[str, Any], section_key: str) -> float:
    fields = FRAMEWORK_SECTIONS[section_key]["fields"]
    keys = [key for key, _label, kind in fields if kind in {"score", "risk"}]
    if not keys:
        return 0.0
    return sum(supplier_numeric(supplier, key) for key in keys) / len(keys)


def average_contract_score(supplier: dict[str, Any]) -> float:
    fields = FRAMEWORK_SECTIONS["contract"]["fields"]
    scored = [(key, kind) for key, _label, kind in fields if kind in {"score", "risk"}]
    if not scored:
        return 0.0
    total = 0.0
    for key, kind in scored:
        value = supplier_numeric(supplier, key)
        total += 6 - value if kind == "risk" else value
    return total / len(scored)


def score_to_100(score: float) -> float:
    return max(0.0, min(100.0, ((score - 1) / 4) * 100))


def risk_to_100(risk: float) -> float:
    return max(0.0, min(100.0, ((5 - risk) / 4) * 100))


def lower_is_better(value: float, values: list[float]) -> float:
    low = min(values)
    high = max(values)
    if high == low:
        return 88.0
    return round(100 - ((value - low) / (high - low)) * 70)


def calculate_metrics(
    suppliers: list[dict[str, Any]], weights: dict[str, float], quantity: float
) -> list[dict[str, Any]]:
    base_metrics = []
    for supplier in suppliers:
        landed = sum(supplier_numeric(supplier, key) for key in LANDED_COST_KEYS)
        tco = landed + sum(supplier_numeric(supplier, key) for key in OWNERSHIP_COST_KEYS)
        lead_time = sum(supplier_numeric(supplier, key) for key in LEAD_TIME_KEYS)
        base_metrics.append(
            {
                "supplier_id": supplier["id"],
                "supplier_name": supplier["name"],
                "total_landed_cost": landed,
                "total_cost_of_ownership": tco,
                "total_order_cost": landed * quantity,
                "total_order_tco": tco * quantity,
                "total_lead_time": lead_time,
                "capability_average": average_section(supplier, "capability"),
                "quality_risk_average": average_section(supplier, "quality_risk"),
                "geopolitical_risk_average": average_section(supplier, "geopolitical_risk"),
                "logistics_risk_average": average_section(supplier, "logistics"),
                "contract_score_average": average_contract_score(supplier),
            }
        )

    landed_values = [metric["total_landed_cost"] for metric in base_metrics]
    tco_values = [metric["total_cost_of_ownership"] for metric in base_metrics]
    lead_values = [metric["total_lead_time"] for metric in base_metrics]
    total_weight = max(sum(float(value) for value in weights.values()), 1)

    for metric in base_metrics:
        landed_score = lower_is_better(metric["total_landed_cost"], landed_values)
        tco_score = lower_is_better(metric["total_cost_of_ownership"], tco_values)
        lead_score = lower_is_better(metric["total_lead_time"], lead_values)
        capability_score = score_to_100(metric["capability_average"])
        quality_score = risk_to_100(metric["quality_risk_average"])
        geopolitical_score = risk_to_100(metric["geopolitical_risk_average"])
        logistics_score = risk_to_100(metric["logistics_risk_average"])
        contract_score = score_to_100(metric["contract_score_average"])
        metric["dimension_scores"] = {
            "Cost": round((landed_score + tco_score) / 2),
            "Lead Time": round(lead_score),
            "Capability": round(capability_score),
            "Quality": round(quality_score),
            "Geopolitical": round(geopolitical_score),
            "Logistics": round(logistics_score),
            "Contract": round(contract_score),
        }
        metric["final_score"] = round(
            (
                landed_score * weights["landed_cost"]
                + tco_score * weights["tco"]
                + lead_score * weights["lead_time"]
                + capability_score * weights["capability"]
                + quality_score * weights["quality_risk"]
                + geopolitical_score * weights["geopolitical_risk"]
                + logistics_score * weights["logistics"]
                + contract_score * weights["contract"]
            )
            / total_weight
        )
    return base_metrics


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
        + metric["geopolitical_risk_average"]
        + metric["logistics_risk_average"],
        reverse=True,
    )
    return {
        "best_overall": by_score[0],
        "lowest_cost": by_cost[0],
        "fastest_lead_time": by_lead[0],
        "highest_risk": by_risk[0],
        "backup_supplier": next(
            (metric for metric in by_score if metric["supplier_id"] != by_score[0]["supplier_id"]),
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
    if numeric(requirement.get("required_lead_time")) < 45:
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
    if fastest and fastest["dimension_scores"]["Cost"] < 70 and fastest != lowest:
        insights.append("This supplier has the shortest lead time but weaker cost performance.")
    for supplier in suppliers:
        if (
            supplier["confidence_level"] in {"Needs Manual Review", "Unavailable Online"}
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
        f"{supplier['name']}: {supplier['confidence_level']}"
        for supplier in suppliers
        if supplier["confidence_level"] != "Verified"
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
            f"Backup supplier recommendation: {backup['supplier_name'] if backup else 'Add another qualified supplier before award'}.",
            "",
            f"Cost summary: Lowest landed cost is {lowest['supplier_name'] if lowest else 'n/a'} at {format_currency(lowest['total_landed_cost']) if lowest else 'n/a'} per unit. Best overall supplier TCO is {format_currency(best['total_cost_of_ownership']) if best else 'n/a'} per unit.",
            f"Lead time summary: Fastest option is {fastest['supplier_name'] if fastest else 'n/a'} at {format_days(fastest['total_lead_time']) if fastest else 'n/a'}.",
            f"Major risks: Highest combined risk is {highest_risk['supplier_name'] if highest_risk else 'n/a'}; review quality, geopolitical, and logistics assumptions before award.",
            f"Manual review items: {'; '.join(manual_items) if manual_items else 'No non-verified suppliers flagged.'}",
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
                "Score": metric["final_score"],
                "Landed / unit": metric["total_landed_cost"],
                "TCO / unit": metric["total_cost_of_ownership"],
                "Order landed": metric["total_order_cost"],
                "Order TCO": metric["total_order_tco"],
                "Lead time days": metric["total_lead_time"],
                "Quality risk": metric["quality_risk_average"],
                "Geopolitical risk": metric["geopolitical_risk_average"],
                "Logistics risk": metric["logistics_risk_average"],
            }
        )
    return pd.DataFrame(rows)


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
            "Total Landed Cost": metric.get("total_landed_cost", ""),
            "Total Cost of Ownership": metric.get("total_cost_of_ownership", ""),
            "Total Lead Time": metric.get("total_lead_time", ""),
            "Final Score": metric.get("final_score", ""),
        }
        for key, label, _kind in fields:
            row[label] = supplier["values"].get(key, "")
        rows.append(row)
    buffer = StringIO()
    pd.DataFrame(rows).to_csv(buffer, index=False)
    return buffer.getvalue()


def render_header() -> None:
    st.title("Global Sourcing Copilot")
    st.caption(
        "AI-assisted sourcing workspace for requirements, supplier comparison, landed cost, risk, and recommendation memo."
    )


def render_sidebar() -> str:
    st.sidebar.title("Global Sourcing Copilot")
    st.sidebar.caption("Streamlit MVP with sample data and editable local session state.")
    page = st.sidebar.radio(
        "Workspace",
        [
            "Dashboard",
            "Product Intake",
            "Supplier Discovery",
            "Framework Table",
            "Scoring Model",
            "AI Insights",
            "Recommendation & Export",
        ],
    )
    st.sidebar.info(
        "Supplier data can be Verified, Estimated, AI Suggested, Needs Manual Review, or Unavailable Online. Human qualification is still required."
    )
    return page


def render_summary(metrics: list[dict[str, Any]], review: dict[str, Any]) -> None:
    summary = recommendation_summary(metrics)
    cols = st.columns(4)
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


def render_intake(requirement: dict[str, Any], review: dict[str, Any]) -> None:
    st.subheader("Product Requirement Intake")
    st.caption("Define the product, quality, compliance, demand, and delivery constraints.")
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

    st.markdown("### AI Requirement Review")
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
    st.caption("Add suppliers manually or create clearly labeled sample suggestions.")
    if st.button("AI Suggested Supplier", type="primary"):
        template = deepcopy(SAMPLE_SUPPLIERS[len(st.session_state.suppliers) % len(SAMPLE_SUPPLIERS)])
        category = requirement.get("product_category") or "target product"
        template.update(
            {
                "id": f"ai-suggested-{len(st.session_state.suppliers) + 1}",
                "name": f"{category} Sample Supplier {len(st.session_state.suppliers) + 1}",
                "country": "Manual verification needed",
                "region": "AI suggested region",
                "website": "Unavailable online",
                "product_match": f"Sample match for {category}. Verify capability before outreach.",
                "certifications": "Unavailable Online",
                "annual_capacity": max(50000, int(numeric(requirement.get("forecasted_demand")))),
                "customer_notes": "AI suggested placeholder generated from product category. Treat as sample data only.",
                "confidence_level": "AI Suggested",
            }
        )
        template["values"]["unit_cost"] = float(numeric(requirement.get("target_cost")) or 8.5)
        template["values"]["certification_risk"] = 4
        template["values"]["audit_result_risk"] = 4
        template["values"]["documentation_ability"] = 2
        template["values"]["contract_payment_terms"] = "Unknown; request in RFQ"
        st.session_state.suppliers.append(template)
        st.success("Added a sample AI suggested supplier. Manual verification required.")

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
        confidence = st.selectbox("Confidence level", CONFIDENCE_LEVELS, index=3)
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
        supplier["confidence_level"] = str(edited.at[idx, "Confidence Level"])
        for key, label, kind in section["fields"]:
            value = edited.at[idx, label]
            supplier["values"][key] = str(value) if kind == "text" else numeric(value)


def render_scoring(metrics: list[dict[str, Any]]) -> None:
    st.subheader("Supplier Scoring Model")
    st.caption("Adjust the default sourcing weights. Risk scores are inverted so lower risk improves score.")
    col1, col2 = st.columns([0.35, 0.65])
    with col1:
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
            st.warning("Weights do not need to total 100, but 100 is easiest to audit.")

    with col2:
        score_df = metrics_dataframe(metrics)
        if not score_df.empty:
            display_df = score_df.copy()
            money_cols = ["Landed / unit", "TCO / unit", "Order landed", "Order TCO"]
            for col in money_cols:
                display_df[col] = display_df[col].map(format_currency)
            display_df["Lead time days"] = display_df["Lead time days"].map(lambda value: f"{value:.0f}")
            st.dataframe(display_df, width="stretch", hide_index=True)
        else:
            st.info("Add suppliers to calculate scores.")


def render_dashboard(metrics: list[dict[str, Any]]) -> None:
    st.subheader("Dashboard")
    if not metrics:
        st.info("Add suppliers to populate the dashboard.")
        return

    score_df = metrics_dataframe(metrics)
    cost_df = score_df[["Supplier", "Landed / unit", "TCO / unit"]].melt(
        id_vars="Supplier", var_name="Cost type", value_name="USD per unit"
    )
    lead_df = score_df[["Supplier", "Lead time days"]]

    col1, col2 = st.columns(2)
    fig_cost = px.bar(
        cost_df,
        x="Supplier",
        y="USD per unit",
        color="Cost type",
        barmode="group",
        title="Total landed cost vs total cost of ownership",
        color_discrete_sequence=["#0f766e", "#2563eb"],
    )
    fig_cost.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20))
    col1.plotly_chart(fig_cost, width="stretch")

    fig_lead = px.bar(
        lead_df,
        x="Supplier",
        y="Lead time days",
        title="Lead time comparison",
        color="Lead time days",
        color_continuous_scale=["#0f766e", "#f59e0b", "#dc2626"],
    )
    fig_lead.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    col2.plotly_chart(fig_lead, width="stretch")

    heatmap = score_df.set_index("Supplier")[
        ["Quality risk", "Geopolitical risk", "Logistics risk"]
    ]
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

    col3, col4 = st.columns(2)
    col3.plotly_chart(fig_heat, width="stretch")
    col4.plotly_chart(radar_fig, width="stretch")

    st.markdown("### Supplier scorecard")
    display_df = score_df.copy()
    display_df["Landed / unit"] = display_df["Landed / unit"].map(format_currency)
    display_df["TCO / unit"] = display_df["TCO / unit"].map(format_currency)
    display_df["Order landed"] = display_df["Order landed"].map(format_currency)
    display_df["Order TCO"] = display_df["Order TCO"].map(format_currency)
    st.dataframe(display_df, width="stretch", hide_index=True)


def render_insights(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> None:
    st.subheader("AI Insight Panels")
    st.caption("Rule-based placeholder logic. Validate supplier data manually before final award.")
    for insight in build_insights(requirement, suppliers, metrics):
        st.warning(insight)


def render_recommendation(
    requirement: dict[str, Any], suppliers: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> None:
    st.subheader("Final Sourcing Recommendation")
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
    page = render_sidebar()
    render_header()

    requirement = st.session_state.requirement
    suppliers = st.session_state.suppliers
    weights = st.session_state.weights
    metrics = calculate_metrics(suppliers, weights, numeric(requirement.get("quantity")))
    review = analyze_requirement(requirement)
    render_summary(metrics, review)
    st.divider()

    if page == "Dashboard":
        render_dashboard(metrics)
    elif page == "Product Intake":
        render_intake(requirement, review)
    elif page == "Supplier Discovery":
        render_supplier_discovery(requirement)
    elif page == "Framework Table":
        render_framework_table()
    elif page == "Scoring Model":
        render_scoring(metrics)
    elif page == "AI Insights":
        render_insights(requirement, suppliers, metrics)
    elif page == "Recommendation & Export":
        render_recommendation(requirement, suppliers, metrics)

    st.caption(
        "This Streamlit MVP uses sample data and session state. It does not call a backend or live AI API."
    )


if __name__ == "__main__":
    main()
