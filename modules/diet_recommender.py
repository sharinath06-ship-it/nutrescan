"""
ICMR/WHO based personalized diet and nutrition recommendation.
"""


def get_nutrient_requirements(age, gender, disease=None):
    """
    Get daily nutrient requirements based on ICMR/WHO guidelines.

    Args:
        age: Age in years
        gender: 'Male' or 'Female'
        disease: Disease condition (e.g., 'Diabetes', 'Hypertension', 'Anemia')

    Returns:
        dict with nutrient requirements
    """
    # Base requirements (ICMR RDA for Indian adults)
    is_male = gender.lower() == "male"
    is_adult = 19 <= age <= 50

    # Calories (kcal/day)
    if is_adult:
        calories = 2500 if is_male else 2000
    elif age > 50:
        calories = 2300 if is_male else 1900
    else:
        calories = 2800 if is_male else 2200

    # Protein (g/day)
    protein = 60 if is_male else 50
    if age > 50:
        protein = 55 if is_male else 45

    # Fiber (g/day)
    fiber = 30

    # Iron (mg/day) - higher for females
    iron = 15 if is_male else 21
    if age > 50:
        iron = 12 if is_male else 10

    # Calcium (mg/day)
    calcium = 1000

    # Vitamin C (mg/day)
    vitamin_c = 40

    # Vitamin A (mcg/day)
    vitamin_a = 600 if is_male else 500

    # Folic acid (mcg/day)
    folic_acid = 200

    # Zinc (mg/day)
    zinc = 12 if is_male else 8

    # Vitamin D (mcg/day)
    vitamin_d = 5

    # Adjustments for diseases
    if disease:
        disease_lower = disease.lower()
        if "diabetes" in disease_lower:
            calories = int(calories * 0.85)
            fiber = 40
            carb_note = "Limit refined carbs, prefer complex carbs"
        elif "hypertension" in disease_lower or "blood pressure" in disease_lower:
            calories = int(calories * 0.9)
            sodium_limit = "Limit sodium to <2g/day"
        elif "anemia" in disease_lower or "anaemia" in disease_lower:
            iron = 30
            vitamin_c = 100
            folic_acid = 400
        elif "obesity" in disease_lower or "weight" in disease_lower:
            calories = int(calories * 0.75)
            fiber = 40
        elif "heart" in disease_lower or "cardiac" in disease_lower:
            calories = int(calories * 0.85)
            fiber = 35
        elif "kidney" in disease_lower:
            protein = int(protein * 0.7)
        elif "thyroid" in disease_lower:
            calories = int(calories * 0.9)

    return {
        "calories": calories,
        "protein": protein,
        "fiber": fiber,
        "iron": iron,
        "calcium": calcium,
        "vitamin_c": vitamin_c,
        "vitamin_a": vitamin_a,
        "folic_acid": folic_acid,
        "zinc": zinc,
        "vitamin_d": vitamin_d,
    }


def get_diet_recommendations(age, gender, disease=None):
    """
    Get personalized diet recommendations based on ICMR/WHO guidelines.

    Returns:
        dict with diet recommendations
    """
    is_male = gender.lower() == "male"

    # Base recommendations (ICMR food groups)
    recommendations = {
        "grains_cereals": {
            "servings": 6 if is_male else 5,
            "examples": ["Whole wheat roti", "Brown rice", "Oats", "Ragi", "Jowar", "Bajra", "Quinoa"],
            "note": "Choose whole grains over refined (avoid maida, white bread)",
        },
        "pulses_legumes": {
            "servings": 2,
            "examples": ["Moong dal", "Chana dal", "Rajma", "Chickpeas", "Sprouted pulses"],
            "note": "Include sprouted pulses for better nutrient absorption",
        },
        "vegetables": {
            "servings": 4 if is_male else 3,
            "examples": ["Spinch (palak)", "Fenugreek (methi)", "Carrot", "Beetroot", "Bitter gourd (karela)", "Green leafy vegetables"],
            "note": "Include 50g+ green leafy vegetables daily (iron + folate)",
        },
        "fruits": {
            "servings": 2,
            "examples": ["Seasonal fruits", "Guava", "Amla", "Citrus fruits (lemon, orange)", "Papaya"],
            "note": "Whole fruits preferred over juice for fiber",
        },
        "milk_dairy": {
            "servings": 3,
            "examples": ["Plain curd (dahi)", "Buttermilk (chaas)", "Paneer (homemade)", "Milk (200ml)"],
            "note": "Choose unsweetened dairy products",
        },
        "nuts_seeds": {
            "servings": 1,
            "examples": ["Almonds (5-6)", "Walnuts (2)", "Flaxseeds", "Sesame seeds", "Pumpkin seeds"],
            "note": "Rich in omega-3 fatty acids and zinc",
        },
        "oils_fats": {
            "servings": 3,
            "examples": ["Cold-pressed mustard oil", "Cold-pressed coconut oil", "Sesame oil", "Ghee (1 tsp)"],
            "note": "Use in moderation; avoid vanaspati and trans fats",
        },
        "water": {
            "servings": 8,
            "examples": ["Water", "Buttermilk (chaas)", "Coconut water", "Lemon water"],
            "note": "Hydrate adequately throughout the day",
        },
    }

    # Disease-specific adjustments
    if disease:
        disease_lower = disease.lower()
        if "diabetes" in disease_lower:
            recommendations["grains_cereals"]["note"] = "Limit refined carbs; prefer ragi, jowar, brown rice"
            recommendations["vegetables"]["examples"].append("Bitter gourd (karela) - blood sugar friendly")
            recommendations["fruits"]["note"] = "Avoid high-sugar fruits (mango, banana); prefer guava, apple, berries"
            recommendations["grains_cereals"]["servings"] = 4
        elif "hypertension" in disease_lower or "blood pressure" in disease_lower:
            recommendations["vegetables"]["examples"].append("Beetroot - helps lower blood pressure")
            recommendations["water"]["examples"].append("Coconut water - natural electrolyte")
            recommendations["oils_fats"]["note"] = "Limit salt; use rock salt (sendha namak) in moderation"
        elif "anemia" in disease_lower or "anaemia" in disease_lower:
            recommendations["pulses_legumes"]["examples"].append("Spinach dal - iron rich")
            recommendations["fruits"]["examples"].append("Amla - vitamin C helps iron absorption")
            recommendations["vegetables"]["examples"].append("Beetroot - iron rich")
            recommendations["nuts_seeds"]["examples"].append("Sesame seeds - iron rich")
        elif "obesity" in disease_lower or "weight" in disease_lower:
            recommendations["grains_cereals"]["servings"] = 4
            recommendations["vegetables"]["servings"] = 5
            recommendations["fruits"]["servings"] = 1
            recommendations["oils_fats"]["servings"] = 2
            recommendations["water"]["note"] = "Drink water before meals to reduce appetite"
        elif "heart" in disease_lower or "cardiac" in disease_lower:
            recommendations["oils_fats"]["examples"] = ["Cold-pressed sesame oil", "Cold-pressed coconut oil", "Ghee (1 tsp)"]
            recommendations["nuts_seeds"]["examples"] = ["Walnuts", "Flaxseeds", "Almonds"]
            recommendations["grains_cereals"]["note"] = "Include oats, ragi, jowar for heart health"
            recommendations["oils_fats"]["servings"] = 2
        elif "kidney" in disease_lower:
            recommendations["pulses_legumes"]["servings"] = 1
            recommendations["milk_dairy"]["servings"] = 2
            recommendations["fruits"]["examples"].append("Apple, grapes, berries")
        elif "thyroid" in disease_lower:
            recommendations["pulses_legumes"]["examples"].append("Chickpeas - iodine and selenium")
            recommendations["vegetables"]["examples"].append("Drumstick leaves - iron and calcium")

    return recommendations


def get_foods_to_avoid(disease=None):
    """Get foods to avoid based on disease."""
    common_avoid = [
        "Trans fats (vanaspati, fried snacks)",
        "Excess sugar and sweets",
        "Excess salt",
        "Processed and packaged foods",
        "Refined flour (maida)",
        "Soft drinks and sugary beverages",
        "Alcohol",
        "Smoking",
    ]

    if disease:
        disease_lower = disease.lower()
        if "diabetes" in disease_lower:
            common_avoid.extend([
                "White rice, white bread",
                "Mangoes, bananas (excess)",
                "Fruit juices",
                "Sugary snacks and desserts",
            ])
        elif "hypertension" in disease_lower or "blood pressure" in disease_lower:
            common_avoid.extend([
                "Excess salt, pickles, papad",
                "Canned and processed foods",
                "Excess oil and ghee",
                "Excess caffeine",
            ])
        elif "anemia" in disease_lower or "anaemia" in disease_lower:
            common_avoid.extend([
                "Tea and coffee (inhibit iron absorption)",
                "Excess calcium with iron-rich meals",
                "Processed cereals",
            ])
        elif "heart" in disease_lower or "cardiac" in disease_lower:
            common_avoid.extend([
                "Saturated fats",
                "Red meat (excess)",
                "Fried foods",
                "Canned soups (high sodium)",
            ])
        elif "kidney" in disease_lower:
            common_avoid.extend([
                "High-sodium foods",
                "High-potassium foods (banana, orange, potato)",
                "High-phosphorus foods (colas, processed foods)",
                "Excess protein",
            ])
        elif "thyroid" in disease_lower:
            common_avoid.extend([
                "Raw cruciferous vegetables (excess)",
                "Soy products (excess)",
                "Gluten (if sensitive)",
            ])

    return common_avoid
