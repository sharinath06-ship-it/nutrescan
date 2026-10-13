from modules.detector import fuzzy_find


tests = [
    ("sugar", "sugar"),
    ("suger", "sugar"),
    ("maltodextrme", "maltodextrin"),
    ("sodum chloride", "sodium chloride"),
    ("palm fat powdr", "palm fat powder"),
    ("flavour enhancer 635", "flavour enhancer 635")
]


for text, expected in tests:

    found, score = fuzzy_find(
        text,
        expected,
        threshold=80
    )

    print("--------------------------------")
    print("OCR text :", text)
    print("Database :", expected)
    print("Matched  :", found)
    print("Score    :", score)