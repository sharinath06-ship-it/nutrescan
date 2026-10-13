"""
NutriScan Smart Food Swap
Rule-based food categorization and general food-alternative suggestions.
"""

import re

FOOD_CATEGORIES = {
    "Snacks": ["chips", "crisps", "namkeen", "mixture", "puffs", "potato wafers", "snack"],
    "Biscuits and Bakery": ["biscuit", "cookie", "cake", "muffin", "rusk", "bakery"],
    "Breakfast Foods": ["breakfast cereal", "corn flakes", "muesli", "granola", "porridge", "oats", "cereal"],
    "Instant and Ready-to-Eat Foods": ["instant noodles", "noodles", "pasta", "instant soup", "ready to eat", "instant meal"],
    "Beverages": ["soft drink", "soda", "cola", "juice", "fruit drink", "energy drink", "beverage"],
    "Sweets and Confectionery": ["chocolate", "candy", "toffee", "sweet", "laddu", "mithai"],
    "Dairy Products": ["milk", "yogurt", "curd", "cheese", "paneer", "butter"],
    "Condiments and Sauces": ["ketchup", "sauce", "mayonnaise", "chutney", "dressing", "pickle"],
    "Packaged Meals": ["frozen meal", "packed meal", "prepared meal"],
}

ALTERNATIVES = {
    "Snacks": [
        ("Roasted ragi or jowar snacks", "Millets", "A millet-based option; check the label because packaged versions can still contain substantial salt or oil."),
        ("Roasted chickpeas", "Pulses and legumes", "Provides plant protein and fiber; choose lightly salted versions where possible."),
        ("Fresh seasonal fruit", "Fruits", "A minimally processed snack that provides fiber and micronutrients."),
        ("Steamed corn or vegetables", "Vegetables", "Adds vegetables to a snack; added salt, butter, or oil affect nutrition."),
        ("Roasted makhana", "Whole-food snack", "A simple option when prepared with modest amounts of oil and salt."),
    ],
    "Biscuits and Bakery": [
        ("Ragi or whole-grain biscuits with less added sugar", "Millets and whole grains", "Compare the ingredient list, added sugar, and saturated fat; millet biscuits are not automatically healthier."),
        ("Fresh fruit", "Fruits", "A minimally processed alternative with fiber and micronutrients."),
        ("Homemade ragi or jowar roti", "Millets", "A way to include millet instead of some refined-flour bakery foods."),
    ],
    "Breakfast Foods": [
        ("Ragi porridge", "Millets", "Prefer an unsweetened preparation; add fruit if desired."),
        ("Foxtail millet or little millet upma", "Millets", "A savory millet-based meal; adding vegetables increases variety."),
        ("Plain oats with fruit", "Whole grains and fruits", "Choose plain oats rather than heavily sweetened flavored varieties."),
    ],
    "Instant and Ready-to-Eat Foods": [
        ("Vegetable millet khichdi", "Millets, pulses, and vegetables", "Combines grains, pulses, and vegetables; adjust salt and added fat."),
        ("Homemade millet upma with vegetables", "Millets and vegetables", "Lets you control the amount of salt and oil."),
        ("Whole-grain noodles with vegetables and pulses", "Whole grains and vegetables", "A similar meal format; compare sodium in sauces and seasoning."),
    ],
    "Beverages": [
        ("Water or unsweetened sparkling water", "Hydration", "Avoids added sugar when replacing a sugar-sweetened drink."),
        ("Lemon water without added sugar", "Fruit-based drink", "A simple alternative to sweetened beverages."),
        ("Whole fruit instead of fruit drink", "Fruits", "Whole fruit generally retains more intact fiber than juice or fruit drinks."),
    ],
    "Sweets and Confectionery": [
        ("Fresh fruit", "Fruits", "A naturally sweet, minimally processed option that provides fiber."),
        ("Dates with nuts, in a modest portion", "Fruits and nuts", "Can suit some sweet cravings, but dates contain concentrated natural sugars."),
        ("Homemade ragi snack with limited added sugar", "Millets", "A millet-based idea; added sugar and fat still matter."),
    ],
    "Dairy Products": [
        ("Plain, unsweetened curd or yogurt", "Dairy", "Compare added sugar and saturated fat across products."),
        ("Unsweetened fortified plant-based alternative", "Plant-based alternative", "Check protein, calcium, fortification, and added sugar."),
    ],
    "Condiments and Sauces": [
        ("Homemade tomato or vegetable chutney", "Vegetables", "Allows control over salt and added sugar; recipes vary."),
        ("Plain yogurt-based dip", "Dairy", "A possible dip alternative; recipe salt and fat content matter."),
    ],
    "Packaged Meals": [
        ("Vegetable millet khichdi", "Millets, pulses, and vegetables", "A meal combining grains, pulses, and vegetables; adjust salt and oil."),
        ("Homemade dal with vegetables and a millet", "Pulses, vegetables, and millets", "A flexible meal where ingredients and seasoning can be controlled."),
    ],
    "Unclassified": [
        ("Seasonal whole fruit", "Fruits", "A general minimally processed food idea; suitability depends on the product and the person's needs."),
        ("Vegetable and pulse-based meal", "Vegetables and pulses", "A general whole-food idea, not a direct product-for-product comparison."),
        ("Millet-based meal such as ragi porridge or millet khichdi", "Millets", "A way to include millets; choose a preparation suitable for the meal."),
    ],
}

def classify_food(product_name="", ocr_text=""):
    """Return category and heuristic confidence from product name/OCR text."""
    name = str(product_name or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", f"{name} {ocr_text or ''}".lower())
    text = re.sub(r"\s+", " ", text).strip()

    # Product-name matches take precedence over OCR matches.
    for category, terms in FOOD_CATEGORIES.items():
        for term in sorted(terms, key=len, reverse=True):
            if re.search(r"\b" + re.escape(term) + r"\b", name):
                return category, 0.95, term

    for category, terms in FOOD_CATEGORIES.items():
        for term in sorted(terms, key=len, reverse=True):
            if re.search(r"\b" + re.escape(term) + r"\b", text):
                return category, 0.85, term

    return "Unclassified", 0.0, ""

def get_alternatives(category, limit=5):
    """Return up to limit alternative food ideas."""
    items = ALTERNATIVES.get(category, ALTERNATIVES["Unclassified"])
    return [{"name": name, "group": group, "reason": reason}
            for name, group, reason in items[:max(0, int(limit))]]

def recommend_food_swaps(product_name="", ocr_text="", limit=5):
    category, confidence, matched_term = classify_food(product_name, ocr_text)
    return {
        "product_name": product_name or "Unknown product",
        "category": category,
        "confidence": confidence,
        "matched_term": matched_term,
        "alternatives": get_alternatives(category, limit),
        "note": (
            "These are general food ideas, not a medical assessment. "
            "A nutritional comparison requires reliable nutrition information "
            "and comparable serving sizes."
        ),
    }

def render_food_swaps(st, product_name="", ocr_text="", limit=5):
    """Render the Smart Food Swap section in an existing Streamlit app."""
    result = recommend_food_swaps(product_name, ocr_text, limit)
    st.subheader("🌿 NutriScan Smart Food Swap")
    st.markdown(f"**Food category:** {result['category']}")
    if result["confidence"]:
        st.caption(
            f"Category match: {round(result['confidence'] * 100)}% "
            "(simple rule-based estimate, not a calibrated model)"
        )
    else:
        st.info("Category not identified confidently; showing general food ideas.")

    st.markdown("### Suggested alternatives")
    for item in result["alternatives"]:
        with st.container(border=True):
            st.markdown(f"**{item['name']}**")
            st.caption(item["group"])
            st.write(item["reason"])
    st.caption(result["note"])
    return result
