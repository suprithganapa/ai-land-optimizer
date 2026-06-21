"""
claude_auditor.py
Post-NSGA-III Claude AI audit.
Sends layout stats to Claude claude-haiku-4-5-20251001, receives NBC 2016 compliance feedback
and corrective constraint suggestions.

Requires ANTHROPIC_API_KEY environment variable.
Falls back to rule-based check if API key not set.
"""
import os
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"


NBC_RULES = {
    "min_setback_m":          3.0,
    "min_road_width_m":       7.5,
    "min_park_area_pct":      10.0,   # 10% of total area
    "min_plot_area_m2":       50.0,
    "max_plot_area_m2":       4000.0,
    "min_connectivity_pct":   90.0,
    "max_slope_degrees":      15.0,
    "min_green_cover_pct":    10.0,
}


def _rule_based_audit(layout_stats: dict) -> dict:
    """Fallback: deterministic NBC 2016 rule check without Claude."""
    issues      = []
    suggestions = []
    corrections = {}

    park_pct = (layout_stats.get("total_park_area_m2", 0) /
                max(1, layout_stats.get("area_m2", 1)) * 100)
    conn_pct  = layout_stats.get("connectivity_pct", 100)
    eff_score = layout_stats.get("efficiency_score", 70)
    num_plots = layout_stats.get("num_plots", 0)

    if park_pct < NBC_RULES["min_park_area_pct"]:
        issues.append(f"Park area {park_pct:.1f}% below NBC 2016 minimum of 10%")
        suggestions.append("Increase park allocation — reduce plot count by 10-15%")
        corrections["min_park_area_m2"] = round(layout_stats.get("area_m2", 0) * 0.11)

    if conn_pct < NBC_RULES["min_connectivity_pct"]:
        issues.append(f"Plot connectivity {conn_pct}% below 90% threshold")
        suggestions.append("Add secondary access roads to isolated plots")
        corrections["min_road_width_m"] = 9.0

    if num_plots < 3:
        issues.append("Very few plots generated — land may be too small or over-constrained")
        suggestions.append("Reduce setback to 2m if zone allows, or reduce road width to 7.5m")

    if eff_score < 50:
        issues.append(f"Efficiency score {eff_score}% is low — excessive road/park area")
        suggestions.append("Reduce road width to minimum NBC 2016 (7.5m) to reclaim plot area")

    status = "PASS" if not issues else "FAIL"
    verdict = (
        "Layout meets NBC 2016 requirements."
        if not issues else
        f"Found {len(issues)} NBC 2016 issue(s) requiring correction."
    )

    return {
        "status":          status,
        "verdict":         verdict,
        "issues":          issues,
        "suggestions":     suggestions,
        "corrections":     corrections,
        "confidence":      "Rule-based (Claude API not configured)",
        "nbc_score":       max(0, 100 - len(issues) * 20),
        "audit_source":    "Local NBC 2016 Rules",
    }


def _claude_audit(layout_stats: dict, zone_type: str) -> dict:
    """Call Claude API for intelligent NBC 2016 compliance audit."""
    prompt = f"""You are an expert urban planning consultant specializing in Indian real estate and NBC 2016 (National Building Code of India 2016).

Audit this residential colony layout for NBC 2016 compliance:

LAYOUT STATISTICS:
- Total Land Area: {layout_stats.get('area_m2', 0):.0f} m²
- Number of Plots: {layout_stats.get('num_plots', 0)}
- Total Plot Area: {layout_stats.get('total_plot_area_m2', 0):.0f} m²
- Total Park Area: {layout_stats.get('total_park_area_m2', 0):.0f} m²
- Total Road Area: {layout_stats.get('total_road_area_m2', 0):.0f} m²
- Land Utilization Efficiency: {layout_stats.get('efficiency_score', 0)}%
- Plot Connectivity: {layout_stats.get('connectivity_pct', 0)}%
- Road Length: {layout_stats.get('road_length_m', 0):.0f} m
- Zone Type: {zone_type}
- Park Area %: {layout_stats.get('total_park_area_m2', 0) / max(1, layout_stats.get('area_m2', 1)) * 100:.1f}%
- Average Plot Size: {layout_stats.get('total_plot_area_m2', 0) / max(1, layout_stats.get('num_plots', 1)):.0f} m²

NBC 2016 REQUIREMENTS FOR RESIDENTIAL LAYOUTS:
- Minimum setback: 3m from boundary
- Minimum road width: 7.5m (9m preferred for layouts > 1 acre)
- Minimum park/open space: 10% of total area
- Civic amenities: 5% of total area
- All plots must have road access
- Minimum plot size: 50 m²

Respond ONLY with a valid JSON object (no markdown, no explanation):
{{
  "status": "PASS" or "FAIL",
  "verdict": "one sentence summary",
  "nbc_score": 0-100,
  "issues": ["list of specific NBC 2016 violations"],
  "suggestions": ["list of actionable corrections"],
  "corrections": {{"constraint_name": value, ...}},
  "park_compliance": true/false,
  "road_compliance": true/false,
  "connectivity_compliance": true/false,
  "audit_source": "Claude AI NBC 2016 Audit"
}}"""

    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 800,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )

        if r.status_code != 200:
            print(f"  Claude API error {r.status_code}: {r.text[:200]}")
            return None

        content = r.json()["content"][0]["text"].strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)
        result["audit_source"]  = "Claude AI (claude-haiku-4-5-20251001)"
        result["confidence"]    = "High"
        print(f"  🤖 Claude audit: {result.get('status')} — score {result.get('nbc_score')}/100")
        return result

    except Exception as e:
        print(f"  Claude audit error: {e}")
        return None


def audit_layout(layout_stats: dict, zone_type: str = "residential") -> dict:
    """
    Main entry point. Try Claude first, fall back to rule-based.
    """
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-key-here":
        result = _claude_audit(layout_stats, zone_type)
        if result:
            return result

    print("  ℹ️  Using rule-based NBC 2016 audit (set ANTHROPIC_API_KEY for Claude audit)")
    return _rule_based_audit(layout_stats)
