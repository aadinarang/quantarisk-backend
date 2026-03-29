import os
import pytest
import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_quantarisk.db"

from app.db import Base, engine, SessionLocal, Symbol, PriceRecord
from app.main import app, get_db


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_test_data(db):
    db.add(Symbol(symbol="AAPL", name="Apple Inc."))
    db.commit()

    base = datetime.date(2025, 1, 1)
    for i in range(60):
        price = 150.0 + i * 0.5
        db.add(PriceRecord(
            symbol="AAPL",
            date=base + datetime.timedelta(days=i),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price,
            volume=1_000_000,
        ))
    db.commit()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    seed_test_data(db)
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

    # Dispose engine to release all connections before deleting file
    engine.dispose()

    if os.path.exists("./test_quantarisk.db"):
        os.remove("./test_quantarisk.db")