
from sqlmodel import SQLModel
from backend.database import engine
from backend.option_models import OptionCSPCandidate

def init_db():
    print("Initializing CSP Table...")
    SQLModel.metadata.create_all(engine)
    print("✅ CSP Candidate Table Created (options_csp_candidates)")

if __name__ == "__main__":
    init_db()
