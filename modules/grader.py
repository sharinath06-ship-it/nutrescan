def calculate_grade(results):

    penalty = 0

    for item in results:

        penalty += int(item["grade_penalty"])

    if penalty <= 2:
        return "A"

    elif penalty <= 5:
        return "B"

    elif penalty <= 8:
        return "C"

    elif penalty <= 12:
        return "D"

    else:
        return "F"