# ============================================================
# NutriScan - Ingredient Text Cleaner
# ============================================================

import re


# ============================================================
# INGREDIENT HEADER WORDS
# ============================================================

INGREDIENT_HEADERS = [
    "ingredient",
    "ingredients",
    "ingredlent",
    "ingredlents",
    "ingredlient",
    "ingredlients",
    "ngredient",
    "ngredients",
]


# ============================================================
# SECTION STOP WORDS
# ============================================================

STOP_WORDS = [
    "nutrition facts",
    "nutritional information",
    "nutritional facts",
    "nutrition information",
    "energy",
    "calories",
    "protein",
    "total fat",
    "saturated fat",
    "trans fat",
    "cholesterol",
    "carbohydrate",
    "dietary fiber",
    "sugars",
    "added sugar",
    "serving size",
    "per serving",
    "manufactured by",
    "marketed by",
    "manufactured",
    "customer care",
    "customer service",
    "fssai",
    "lic no",
    "license number",
    "net weight",
    "net wt",
    "best before",
    "use before",
    "expiry",
    "expires",
    "mrp",
    "batch no",
    "batch number",
    "mfg",
    "mfd",
    "date of manufacture",
    "storage instructions",
    "keep refrigerated",
    "barcode",
    "scan the qr",
    "www",
    "http",
]


# ============================================================
# OCR CORRECTIONS
# ============================================================

OCR_REPLACEMENTS = {

    "ingredlents": "ingredients",
    "ingredlent": "ingredient",
    "ingredlients": "ingredients",
    "ingredlient": "ingredient",

    "ing redients": "ingredients",

    "vegetabie": "vegetable",
    "vegetab1e": "vegetable",
    "veqetable": "vegetable",

    "oii": "oil",
    "sait": "salt",
    "suqar": "sugar",

    "maitodextrin": "maltodextrin",
    "maitodextrine": "maltodextrine",

    "monosodium glutamate": "monosodium glutamate",
}


# ============================================================
# NON-INGREDIENT PHRASES
# ============================================================

IGNORE_PHRASES = [
    "manufactured by",
    "marketed by",
    "customer care",
    "customer service",
    "nutrition facts",
    "nutritional information",
    "nutritional facts",
    "nutrition information",
    "energy",
    "calories",
    "protein",
    "total fat",
    "saturated fat",
    "trans fat",
    "cholesterol",
    "total carbohydrate",
    "carbohydrate",
    "dietary fiber",
    "added sugar",
    "serving size",
    "per serving",
    "per 100g",
    "fssai",
    "lic no",
    "license number",
    "barcode",
    "scan the qr",
    "best before",
    "use before",
    "net weight",
    "net wt",
    "mrp",
    "batch",
    "email",
    "www",
]


# ============================================================
# BASIC NORMALIZATION
# ============================================================

def normalize_ocr_text(text):

    if not text:
        return ""

    text = str(text)

    for wrong, correct in OCR_REPLACEMENTS.items():

        text = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            text,
            flags=re.IGNORECASE
        )

    # URLs
    text = re.sub(
        r"https?://\S+",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Email
    text = re.sub(
        r"\S+@\S+",
        " ",
        text
    )

    # OCR separators
    text = text.replace("|", ",")
    text = text.replace(";", ",")
    text = text.replace("•", ",")
    text = text.replace("·", ",")

    # Normalize brackets
    text = text.replace("(", ",")
    text = text.replace(")", ",")

    # Normalize whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CLEAN LINE
# ============================================================

def clean_line(line):

    if line is None:
        return ""

    line = normalize_ocr_text(
        line
    )

    line = line.strip()

    if not line:
        return ""

    # Remove repeated commas
    line = re.sub(
        r",\s*,+",
        ",",
        line
    )

    return line.strip(" ,.-")


# ============================================================
# INGREDIENT HEADER
# ============================================================

def is_ingredient_header(line):

    if not line:
        return False

    lower = normalize_ocr_text(
        line
    ).lower()

    for header in INGREDIENT_HEADERS:

        if re.search(
            rf"\b{re.escape(header)}\b",
            lower
        ):
            return True

    return False


# ============================================================
# STOP SECTION
# ============================================================

def is_stop_line(line):

    if not line:
        return False

    lower = line.lower().strip()

    for word in STOP_WORDS:

        if word in lower:
            return True

    return False


# ============================================================
# METADATA CHECK
# ============================================================

def looks_like_metadata(text):

    if not text:
        return True

    lower = text.lower().strip()

    if len(lower) < 2:
        return True

    for phrase in IGNORE_PHRASES:

        if phrase in lower:
            return True

    if "@" in lower:
        return True

    if "http://" in lower:
        return True

    if "https://" in lower:
        return True

    # Mostly numbers
    letters = sum(
        character.isalpha()
        for character in lower
    )

    digits = sum(
        character.isdigit()
        for character in lower
    )

    if digits > letters and digits > 3:
        return True

    return False


# ============================================================
# CLEAN INGREDIENT
# ============================================================

def clean_ingredient(text):

    if not text:
        return ""

    text = normalize_ocr_text(
        text
    )

    text = text.strip()

    # Remove leading punctuation
    text = text.strip(
        " ,:;|-_"
    )

    # Remove unwanted phrases
    for phrase in IGNORE_PHRASES:

        text = re.sub(
            re.escape(phrase),
            " ",
            text,
            flags=re.IGNORECASE
        )

    # Remove measurements
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:g|mg|kg|ml|kcal|%)\b",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Normalize whitespace
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip(
        " ,:;.-"
    )


# ============================================================
# SPLIT INGREDIENTS
# ============================================================

def split_ingredients(line):

    if not line:
        return []

    line = clean_line(
        line
    )

    if not line:
        return []

    # --------------------------------------------------------
    # Commas are the main ingredient separator
    # --------------------------------------------------------

    parts = re.split(
        r",+",
        line
    )

    results = []

    for part in parts:

        part = clean_ingredient(
            part
        )

        if not part:
            continue

        if looks_like_metadata(
            part
        ):
            continue

        if len(part) < 2:
            continue

        # Need at least alphabetic content
        letters = sum(
            character.isalpha()
            for character in part
        )

        if letters < 2:
            continue

        results.append(
            part
        )

    return results


# ============================================================
# EXTRACT TEXT AFTER INGREDIENT HEADER
# ============================================================

def extract_after_header(line):

    if not line:
        return []

    match = re.search(
        r"ingred(?:i|l)ents?"
        r"\s*[:\-]?\s*(.*)",
        line,
        flags=re.IGNORECASE
    )

    if not match:
        return []

    remaining = match.group(
        1
    ).strip()

    if not remaining:
        return []

    return split_ingredients(
        remaining
    )


# ============================================================
# KNOWN INGREDIENT TERMS
# ============================================================

COMMON_INGREDIENT_WORDS = [

    # Base food ingredients
    "potato",
    "potatoes",
    "maize",
    "corn",
    "rice",
    "wheat",
    "flour",
    "wheat flour",
    "rice flour",
    "corn flour",
    "starch",
    "modified starch",

    # Oils
    "vegetable oil",
    "palm oil",
    "palmolein",
    "sunflower oil",
    "rice bran oil",
    "cottonseed oil",
    "corn oil",
    "soybean oil",
    "groundnut oil",
    "canola oil",
    "hydrogenated oil",
    "partially hydrogenated oil",

    # Sweeteners
    "sugar",
    "glucose",
    "glucose syrup",
    "fructose",
    "dextrose",
    "maltose",
    "maltodextrin",
    "maltodextrine",

    # Salt / seasonings
    "salt",
    "iodized salt",
    "spices",
    "spice",
    "onion",
    "garlic",
    "chilli",
    "chili",
    "tomato",
    "cumin",
    "pepper",
    "black pepper",
    "turmeric",
    "coriander",
    "ginger",

    # Dairy
    "milk",
    "milk solids",
    "milk powder",
    "skimmed milk powder",
    "cheese",
    "cheese powder",
    "whey",
    "whey powder",
    "butter",

    # Acidity regulators
    "acidity regulator",
    "citric acid",
    "lactic acid",
    "malic acid",
    "tartaric acid",
    "phosphoric acid",

    # Flavour
    "flavour",
    "flavor",
    "flavouring",
    "flavoring",
    "artificial flavour",
    "artificial flavor",
    "natural flavour",
    "natural flavor",

    # MSG / additives
    "monosodium glutamate",
    "msg",
    "sodium glutamate",
    "flavour enhancer",
    "flavor enhancer",

    # Preservatives
    "preservative",
    "sodium benzoate",
    "potassium sorbate",
    "sorbic acid",
    "benzoic acid",

    # Antioxidants
    "antioxidant",
    "bha",
    "bht",
    "tocopherol",
    "citric acid",

    # Emulsifiers
    "emulsifier",
    "lecithin",
    "soy lecithin",
    "mono and diglycerides",

    # Colours
    "colour",
    "color",
    "caramel colour",
    "caramel color",
    "annatto",
    "tartrazine",
    "sunset yellow",
    "brilliant blue",
    "ponceau 4r",
]


# ============================================================
# FIND KNOWN INGREDIENTS
# ============================================================

def find_known_ingredients(text):

    if not text:
        return []

    normalized = normalize_ocr_text(
        text
    )

    lower = normalized.lower()

    found = []

    # Longest terms first so that
    # "palm oil" is found before "oil".
    terms = sorted(
        COMMON_INGREDIENT_WORDS,
        key=len,
        reverse=True
    )

    for ingredient in terms:

        pattern = (
            r"\b"
            + re.escape(
                ingredient.lower()
            )
            + r"\b"
        )

        if re.search(
            pattern,
            lower
        ):

            found.append(
                ingredient
            )

    return found


# ============================================================
# FALLBACK OCR SCAN
# ============================================================

def fallback_scan_ocr(ocr_text):

    if not ocr_text:
        return []

    text = normalize_ocr_text(
        ocr_text
    )

    candidates = []

    # --------------------------------------------------------
    # Known ingredients
    # --------------------------------------------------------

    candidates.extend(
        find_known_ingredients(
            text
        )
    )

    # --------------------------------------------------------
    # Comma-separated fragments
    # --------------------------------------------------------

    fragments = re.split(
        r",+",
        text
    )

    for fragment in fragments:

        fragment = clean_ingredient(
            fragment
        )

        if not fragment:
            continue

        if looks_like_metadata(
            fragment
        ):
            continue

        # Avoid huge packaging sentences
        if len(fragment) > 100:
            continue

        if len(fragment) >= 3:

            candidates.append(
                fragment
            )

    return candidates


# ============================================================
# MAIN INGREDIENT EXTRACTION
# ============================================================

def extract_ingredients(ocr_text):

    if not ocr_text:
        return []

    # --------------------------------------------------------
    # Convert OCR into lines
    # --------------------------------------------------------

    if isinstance(
        ocr_text,
        str
    ):

        raw_lines = (
            ocr_text.splitlines()
        )

    elif isinstance(
        ocr_text,
        list
    ):

        raw_lines = ocr_text

    else:

        raw_lines = [
            str(ocr_text)
        ]

    # --------------------------------------------------------
    # Clean lines
    # --------------------------------------------------------

    lines = []

    for raw_line in raw_lines:

        line = clean_line(
            raw_line
        )

        if line:
            lines.append(
                line
            )

    if not lines:
        return []

    ingredients = []

    inside_ingredient_section = False
    found_header = False

    # ========================================================
    # PRIMARY EXTRACTION
    # ========================================================

    for line in lines:

        normalized = normalize_ocr_text(
            line
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        if is_ingredient_header(
            normalized
        ):

            found_header = True
            inside_ingredient_section = True

            ingredients.extend(
                extract_after_header(
                    normalized
                )
            )

            continue

        # ----------------------------------------------------
        # Ingredient section
        # ----------------------------------------------------

        if inside_ingredient_section:

            if is_stop_line(
                normalized
            ):

                inside_ingredient_section = False

                continue

            ingredients.extend(
                split_ingredients(
                    normalized
                )
            )

    # ========================================================
    # FALLBACK
    # ========================================================

    full_text = "\n".join(
        lines
    )

    # If no header or extraction was weak,
    # scan the complete OCR text.
    if (
        not found_header
        or len(ingredients) < 3
    ):

        ingredients.extend(
            fallback_scan_ocr(
                full_text
            )
        )

    # ========================================================
    # KNOWN INGREDIENT SEARCH
    # ========================================================

    ingredients.extend(
        find_known_ingredients(
            full_text
        )
    )

    # ========================================================
    # FINAL DEDUPLICATION
    # ========================================================

    final = []

    seen = set()

    for ingredient in ingredients:

        ingredient = clean_ingredient(
            ingredient
        )

        if not ingredient:
            continue

        if looks_like_metadata(
            ingredient
        ):
            continue

        key = ingredient.lower()

        if key in seen:
            continue

        seen.add(key)

        final.append(
            ingredient
        )

    return final


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample = """
    MARKETED BY ITC LIMITED

    INGREDIENTS: Potato, Vegetable Oil,
    Sugar, Salt, Maltodextrin, Spices,
    Acidity Regulator, Monosodium Glutamate,
    Artificial Flavour, Antioxidant

    ENERGY 534 kcal
    PROTEIN 7.4 g

    CUSTOMER CARE 1800XXXX
    """

    print()
    print("=" * 60)
    print("TEXT CLEANER TEST")
    print("=" * 60)

    result = extract_ingredients(
        sample
    )

    for index, item in enumerate(
        result,
        start=1
    ):

        print(
            f"{index}. {item}"
        )

    print()
    print(
        "Total ingredients:",
        len(result)
    )