import sqlite3

DB = "database/nutriscan.db"

def save_scan(email, product, grade, ingredients):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO history
        (email, product, grade, ingredients)
        VALUES (?,?,?,?)
        """,
        (email, product, grade, ingredients)
    )

    conn.commit()
    conn.close()


def get_history(email):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT product,
               grade,
               ingredients,
               scan_date
        FROM history
        WHERE email=?
        ORDER BY scan_date DESC
        """,
        (email,)
    )

    data = cursor.fetchall()

    conn.close()

    return data