def recommend(results):

    alternatives = []

    seen = set()

    for item in results:

        alt = item["alternative"]

        if alt not in seen:

            alternatives.append(alt)

            seen.add(alt)

    return alternatives