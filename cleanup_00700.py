from backend.database import engine
from sqlalchemy import text

def cleanup():
    with engine.connect() as conn:
        # Delete entries that are clearly wrong (e.g. 4.5M shares or 583B shares or 21B shares)
        # Or just delete all pdf-parser entries for 00700 to re-run
        conn.execute(text("DELETE FROM financialfundamentals WHERE symbol LIKE '%00700%' AND data_source = 'pdf-parser'"))
        conn.commit()
        print("Cleaned up 00700 entries from pdf-parser.")

if __name__ == "__main__":
    cleanup()
