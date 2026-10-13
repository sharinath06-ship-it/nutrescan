import pandas as pd
import re
from rapidfuzz import fuzz

db = pd.read_csv("database/ingredients.csv")


def normalize_text(text):
    """
    Normalize text before matching.
    """

    text = str(text).lower()

    # Replace punctuation with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fuzzy_find(text, term, threshold=85):
    """
    Check whether a term approximately exists in OCR text.
    """

    text = normalize_text(text)
    term = normalize_text(term)

    # Exact match first
    if term in text:
        return True, 100

    # Compare against individual words/windows
    words = text.split()

    term_words = term.split()
    term_length = len(term_words)

    if term_length == 0:
        return False, 0

    best_score = 0

    for i in range(len(words) - term_length + 1):

        window = " ".join(
            words[i:i + term_length]
        )

        score = fuzz.ratio(term, window)

        if score > best_score:
            best_score = score

    return best_score >= threshold, best_score


def check_ingredients(text):

    found = []
    matched = set()

    for _, row in db.iterrows():

        ingredient = str(
            row["ingredient"]
        ).lower().strip()

        # Check main ingredient
        detected, score = fuzzy_find(
            text,
            ingredient,
            threshold=85
        )

        # Check aliases if main ingredient wasn't found
        if not detected:

            aliases = str(
                row["aliases"]
            ).split(",")

            for alias in aliases:

                alias = alias.strip()

                if not alias:
                    continue

                detected, score = fuzzy_find(
                    text,
                    alias,
                    threshold=85
                )

                if detected:
                    break

        if detected and ingredient not in matched:

            matched.add(ingredient)

            found.append({

                "ingredient": row["ingredient"],

                "category": row["category"],

                "risk_level": row["risk_level"],

                "health_impact": row["health_impact"],

                "fssai": row["fssai"],

                "fda": row["fda"],

                "eu_status": row["eu_status"],

                "countries_restricted":
                    row["countries_restricted"],

                "alternative":
                    row["alternative"],

                "avoid_for":
                    row["avoid_for"],

                "description":
                    row["description"],

                "grade_penalty":
                    row["grade_penalty"],

                "match_score":
                    score
            })

    return found