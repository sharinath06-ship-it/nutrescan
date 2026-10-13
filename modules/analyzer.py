# ============================================================
# NutriScan - Fast Ingredient Analyzer
# ============================================================

import re
from pathlib import Path
from difflib import SequenceMatcher

import pandas as pd


# ============================================================
# PATH
# ============================================================

MODULES_DIR = Path(__file__).resolve().parent

CSV_PATH = MODULES_DIR / "database" / "ingredients.csv"


# ============================================================
# DATABASE CACHE
# ============================================================

_DATABASE = None
_LOOKUP = None


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text).lower()

    text = text.replace("|", " ")
    text = text.replace("_", " ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# LOAD DATABASE
# ============================================================

def load_ingredient_database():

    if not CSV_PATH.exists():

        raise FileNotFoundError(
            f"ingredients.csv not found:\n{CSV_PATH}"
        )

    try:

        df = pd.read_csv(
            CSV_PATH,
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            CSV_PATH,
            encoding="latin1"
        )

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    if "ingredient" not in df.columns:

        raise ValueError(
            "ingredients.csv must contain "
            "'ingredient' column."
        )

    if "aliases" not in df.columns:
        df["aliases"] = ""

    if "category" not in df.columns:
        df["category"] = ""

    df["ingredient"] = (
        df["ingredient"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["aliases"] = (
        df["aliases"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["category"] = (
        df["category"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["ingredient"] != ""
    ].copy()

    return df


# ============================================================
# BUILD FAST LOOKUP
# ============================================================

def build_lookup(df):

    lookup = {}

    for _, row in df.iterrows():

        ingredient = str(
            row["ingredient"]
        ).strip()

        category = str(
            row["category"]
        ).strip()

        aliases = str(
            row["aliases"]
        ).strip()

        item = {
            "ingredient": ingredient,
            "category": category,
            "aliases": aliases
        }

        # Main ingredient
        normalized = normalize_text(
            ingredient
        )

        if normalized:

            lookup[normalized] = item

        # Aliases
        if aliases:

            alias_list = re.split(
                r"[,;|]",
                aliases
            )

            for alias in alias_list:

                alias = alias.strip()

                if not alias:
                    continue

                normalized_alias = normalize_text(
                    alias
                )

                if normalized_alias:

                    lookup[
                        normalized_alias
                    ] = item

    return lookup


# ============================================================
# GET DATABASE
# ============================================================

def get_database():

    global _DATABASE
    global _LOOKUP

    if _DATABASE is None:

        _DATABASE = load_ingredient_database()

        _LOOKUP = build_lookup(
            _DATABASE
        )

    return _DATABASE


# ============================================================
# SIMILARITY
# ============================================================

def similarity_score(
    text,
    candidate
):

    text = normalize_text(text)

    candidate = normalize_text(candidate)

    if not text or not candidate:
        return 0.0

    # Exact
    if text == candidate:
        return 100.0

    # Candidate contained in OCR text
    if candidate in text:
        return 100.0

    # OCR text contained in candidate
    if text in candidate:
        return 90.0

    # Token comparison
    text_tokens = set(
        text.split()
    )

    candidate_tokens = set(
        candidate.split()
    )

    if candidate_tokens:

        common = (
            text_tokens &
            candidate_tokens
        )

        token_score = (
            len(common)
            /
            len(candidate_tokens)
        ) * 100

    else:

        token_score = 0

    # Character comparison
    character_score = (
        SequenceMatcher(
            None,
            text,
            candidate
        ).ratio()
        * 100
    )

    return max(
        token_score,
        character_score
    )


# ============================================================
# ANALYZE
# ============================================================

def analyze_ingredients(
    ingredient_candidates,
    threshold=60
):

    get_database()

    if not ingredient_candidates:
        return []

    if isinstance(
        ingredient_candidates,
        str
    ):

        ingredient_candidates = [
            ingredient_candidates
        ]

    results = []

    seen = set()

    # --------------------------------------------------------
    # PROCESS EACH OCR CANDIDATE
    # --------------------------------------------------------

    for candidate in ingredient_candidates:

        if candidate is None:
            continue

        candidate = str(
            candidate
        ).strip()

        normalized_candidate = normalize_text(
            candidate
        )

        if not normalized_candidate:
            continue

        # ----------------------------------------------------
        # FAST EXACT / ALIAS LOOKUP
        # ----------------------------------------------------

        exact_item = _LOOKUP.get(
            normalized_candidate
        )

        if exact_item:

            key = normalize_text(
                exact_item["ingredient"]
            )

            if key not in seen:

                seen.add(key)

                results.append({
                    "ingredient":
                        exact_item["ingredient"],

                    "ingredient_name":
                        exact_item["ingredient"],

                    "category":
                        exact_item["category"],

                    "matched_text":
                        candidate,

                    "matched_alias":
                        "",

                    "match_score":
                        100.0
                })

            continue

        # ----------------------------------------------------
        # SEARCH DATABASE
        # ----------------------------------------------------

        best_item = None
        best_score = 0.0
        best_alias = ""

        for _, row in _DATABASE.iterrows():

            ingredient = str(
                row["ingredient"]
            ).strip()

            category = str(
                row["category"]
            ).strip()

            aliases = str(
                row["aliases"]
            ).strip()

            # Main ingredient
            score = similarity_score(
                normalized_candidate,
                ingredient
            )

            matched_alias = ""

            # Aliases
            if aliases:

                alias_list = re.split(
                    r"[,;|]",
                    aliases
                )

                for alias in alias_list:

                    alias = alias.strip()

                    if not alias:
                        continue

                    alias_score = similarity_score(
                        normalized_candidate,
                        alias
                    )

                    if alias_score > score:

                        score = alias_score
                        matched_alias = alias

            if score > best_score:

                best_score = score

                best_item = {
                    "ingredient": ingredient,
                    "category": category
                }

                best_alias = matched_alias

        # ----------------------------------------------------
        # ACCEPT MATCH
        # ----------------------------------------------------

        if (
            best_item is not None
            and best_score >= threshold
        ):

            key = normalize_text(
                best_item["ingredient"]
            )

            if key in seen:
                continue

            seen.add(key)

            results.append({

                "ingredient":
                    best_item["ingredient"],

                "ingredient_name":
                    best_item["ingredient"],

                "category":
                    best_item["category"],

                "matched_text":
                    candidate,

                "matched_alias":
                    best_alias,

                "match_score":
                    round(
                        best_score,
                        2
                    )
            })

    # Highest confidence first
    results.sort(
        key=lambda x:
            x["match_score"],
        reverse=True
    )

    return results


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    database = get_database()

    print(
        "Database loaded:",
        len(database)
    )

    test_items = [
        "sugar",
        "salt",
        "vegetable oil",
        "maltodextrin"
    ]

    results = analyze_ingredients(
        test_items
    )

    print()

    for item in results:

        print(
            item
        )