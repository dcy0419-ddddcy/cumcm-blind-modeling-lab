import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def directional(local: float, reference: float) -> dict:
    difference = reference - local
    return {
        "local": local,
        "reference": reference,
        "reference_minus_local": difference,
        "local_lower_than_reference_fraction_of_reference": difference / reference,
        "reference_higher_than_local_fraction_of_local": difference / local,
    }


data = {
    "purpose": "统一首次对照中的百分比分母；不修改冻结数值",
    "q1_annual_total_power_MW": {
        "A0127": directional(35.24859, 36.994507232),
        "A092": directional(35.24859, 38.295),
    },
    "q2_unit_area_power_kW_per_m2": {
        "A0127": directional(0.456337922463, 0.58712005),
        "A092": directional(0.456337922463, 0.7139),
    },
    "q3_unit_area_power_kW_per_m2": {
        "A0127": directional(0.460688109252, 0.530652),
        "A092": directional(0.460688109252, 0.7551),
    },
    "interpretation": {
        "local_lower": "(reference-local)/reference",
        "reference_higher": "(reference-local)/local",
    },
}

(ROOT / "校准百分比-v001.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(data, ensure_ascii=False, indent=2))
