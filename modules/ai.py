"""
NutriScan offline ingredient analysis.

Builds the ingredient analysis completely locally - no internet,
no API keys, no external AI services. Three sources are combined:

1. Pre-computed notes for common ingredients (COMMON_INGREDIENTS)
2. Ingredient facts from the built-in offline brain (INGREDIENT_FACTS)
3. A category-based fallback for everything else
"""

try:
    from modules.offline_brain import INGREDIENT_FACTS
except Exception:
    try:
        from offline_brain import INGREDIENT_FACTS
    except Exception:
        INGREDIENT_FACTS = {}


# ============================================================
# PRE-COMPUTED COMMON INGREDIENTS
# ============================================================

COMMON_INGREDIENTS = {
    "sugar": {
        "purpose": "Sweetener and preservative",
        "risk": "Low to Moderate",
        "concerns": "Excess consumption linked to obesity, diabetes, and tooth decay",
        "fssai": "Permitted within limits",
        "interpretation": "Consume in moderation as part of a balanced diet"
    },
    "salt": {
        "purpose": "Flavor enhancer and preservative",
        "risk": "Moderate",
        "concerns": "High intake linked to hypertension and cardiovascular disease",
        "fssai": "Permitted within limits",
        "interpretation": "Limit daily intake to less than 5g per day"
    },
    "wheat flour": {
        "purpose": "Main structural ingredient in baked goods",
        "risk": "Low",
        "concerns": "Gluten content may affect individuals with celiac disease",
        "fssai": "Permitted",
        "interpretation": "Safe for general population; gluten-sensitive individuals should avoid"
    },
    "palm oil": {
        "purpose": "Cooking oil and texture enhancer",
        "risk": "Moderate",
        "concerns": "High in saturated fat; excessive consumption may affect heart health",
        "fssai": "Permitted within limits",
        "interpretation": "Use in moderation; prefer oils with better fatty acid profile"
    },
    "milk powder": {
        "purpose": "Adds creaminess and nutritional value",
        "risk": "Low",
        "concerns": "Lactose intolerance in some individuals",
        "fssai": "Permitted",
        "interpretation": "Good source of calcium and protein"
    },
    "cocoa": {
        "purpose": "Flavor and color in chocolate products",
        "risk": "Low",
        "concerns": "Generally safe; may contain small amounts of caffeine",
        "fssai": "Permitted",
        "interpretation": "Rich in antioxidants; consume in moderation"
    },
    "vanilla": {
        "purpose": "Flavoring agent",
        "risk": "Low",
        "concerns": "Generally recognized as safe",
        "fssai": "Permitted",
        "interpretation": "Safe for consumption"
    },
    "baking soda": {
        "purpose": "Leavening agent",
        "risk": "Low",
        "concerns": "Safe when used in appropriate amounts",
        "fssai": "Permitted",
        "interpretation": "Safe for consumption in normal amounts"
    },
    "citric acid": {
        "purpose": "Preservative and acidity regulator",
        "risk": "Low",
        "concerns": "Generally safe; may erode tooth enamel in excess",
        "fssai": "Permitted",
        "interpretation": "Safe in normal food amounts"
    },
    "water": {
        "purpose": "Solvent and hydration",
        "risk": "Low",
        "concerns": "None when clean",
        "fssai": "Permitted",
        "interpretation": "Essential for life"
    },
    "rice": {
        "purpose": "Primary carbohydrate source",
        "risk": "Low",
        "concerns": "High glycemic index; portion control important",
        "fssai": "Permitted",
        "interpretation": "Staple food; consume in balanced portions"
    },
    "vegetable oil": {
        "purpose": "Cooking medium and texture",
        "risk": "Low to Moderate",
        "concerns": "Type of oil matters; some are high in saturated fats",
        "fssai": "Permitted",
        "interpretation": "Choose oils with healthier fat profiles"
    },
    "maltodextrin": {
        "purpose": "Thickener and filler",
        "risk": "Low to Moderate",
        "concerns": "High glycemic index; may affect blood sugar",
        "fssai": "Permitted",
        "interpretation": "Common in processed foods; moderate consumption advised"
    },
    "soy lecithin": {
        "purpose": "Emulsifier",
        "risk": "Low",
        "concerns": "Generally safe; soy allergy in sensitive individuals",
        "fssai": "Permitted",
        "interpretation": "Safe for most people"
    },
    "ascorbic acid": {
        "purpose": "Antioxidant and preservative",
        "risk": "Low",
        "concerns": "Vitamin C; generally beneficial",
        "fssai": "Permitted",
        "interpretation": "Beneficial nutrient"
    },
    "sodium benzoate": {
        "purpose": "Preservative",
        "risk": "Moderate",
        "concerns": "May form benzene when combined with vitamin C",
        "fssai": "Permitted within limits",
        "interpretation": "Safe within regulatory limits"
    },
    "monosodium glutamate": {
        "purpose": "Flavor enhancer",
        "risk": "Low to Moderate",
        "concerns": "May cause sensitivity in some individuals",
        "fssai": "Permitted within limits",
        "interpretation": "Generally recognized as safe by FDA"
    },
    "caramel color": {
        "purpose": "Coloring agent",
        "risk": "Moderate",
        "concerns": "Some types may contain 4-MEI",
        "fssai": "Permitted within limits",
        "interpretation": "Consume colored foods in moderation"
    },
    "xanthan gum": {
        "purpose": "Thickener and stabilizer",
        "risk": "Low",
        "concerns": "Generally safe",
        "fssai": "Permitted",
        "interpretation": "Safe for consumption"
    },
    "guar gum": {
        "purpose": "Thickener and stabilizer",
        "risk": "Low",
        "concerns": "Generally safe; may cause digestive issues in large amounts",
        "fssai": "Permitted",
        "interpretation": "Safe in normal food amounts"
    }
}


def _get_precomputed_analysis(ingredient_name):
    """Get pre-computed analysis for common ingredients."""
    name = str(ingredient_name).lower().strip()
    return COMMON_INGREDIENTS.get(name)


def _describe_ingredient(item):
    """Build the markdown block for one matched ingredient."""
    name = (
        item.get("ingredient_name")
        or item.get("ingredient")
        or "Unknown"
    )
    category = str(item.get("category") or "").strip()
    data = _get_precomputed_analysis(name)
    fact = str(
        INGREDIENT_FACTS.get(str(name).lower().strip()) or ""
    ).strip()

    if data:
        purpose = data["purpose"]
        concerns = data["concerns"]
        risk = data["risk"]
        fssai = data["fssai"]
        interpretation = data["interpretation"]
    else:
        purpose = (
            f"Used in food products as a {category.lower()}."
            if category
            else "Standard ingredient used in packaged foods."
        )
        concerns = (
            fact
            if fact
            else (
                "No specific concern at normal food levels; "
                "the amount and how often you eat it matter most."
            )
        )
        risk = "Low to Moderate"
        fssai = (
            "Used in food products within applicable FSSAI limits."
        )
        interpretation = (
            "Safe for most people in normal amounts as part "
            "of a balanced diet."
        )

    lines = [
        f"### {str(name).title()}",
        "",
        f"**Purpose:** {purpose}",
        "",
        f"**Health concerns:** {concerns}",
        "",
        f"**Risk level:** {risk}",
        "",
        f"**India / FSSAI status:** {fssai}",
        "",
        f"**Consumer interpretation:** {interpretation}",
        "",
    ]
    return "\n".join(lines)


def _flag_names(keyword_matches):
    """Normalize flagged-keyword items to plain display strings."""
    names = []
    for item in keyword_matches or []:
        if isinstance(item, dict):
            label = (
                item.get("matched_text")
                or item.get("keyword")
                or item.get("text")
                or ""
            )
        else:
            label = str(item)
        label = label.strip()
        if label:
            names.append(label)
    return names


def ask_ai(detected_ingredients, keyword_matches=None):
    """Build a full ingredient analysis fully offline (instant)."""
    if not detected_ingredients:
        return (
            "No ingredients were detected, so NutriScan cannot "
            "generate an ingredient analysis."
        )

    lines = [
        "# NutriScan AI Ingredient Analysis",
        "",
        "## 1. Ingredient-by-Ingredient Analysis",
        "",
    ]

    for item in detected_ingredients:
        lines.append(_describe_ingredient(item))

    lines.append("## 2. Overall Food Assessment")
    lines.append("")

    flagged = _flag_names(keyword_matches)
    if flagged:
        lines.append(
            "Ingredients that deserve attention in this scan: "
            + ", ".join(flagged)
            + "."
        )
        lines.append("")
        lines.append(
            "Try to keep such ingredients occasional rather than "
            "daily, and prefer products with shorter, simpler "
            "ingredient lists."
        )
    else:
        lines.append(
            "The product contains common ingredients that are "
            "generally safe when consumed in moderation."
        )

    lines.append("")
    lines.append("## 3. Sources")
    lines.append("")
    lines.append(
        "- FSSAI (Food Safety and Standards Authority of India)"
    )
    lines.append(
        "- WHO (World Health Organization)"
    )
    lines.append(
        "- ICMR/NIN (Indian Council of Medical Research / "
        "National Institute of Nutrition)"
    )
    return "\n".join(lines)
