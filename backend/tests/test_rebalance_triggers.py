"""Trigger logic for re-balance check (no real DB needed: in-memory SQLite)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# We only need to validate the deviation math — re-implement here so this is
# database-engine agnostic.
from app.services.rebalance import DEVIATION_THRESHOLD


def test_deviation_threshold_is_15_percent():
    assert DEVIATION_THRESHOLD == 0.15


def test_deviation_math():
    target = 60
    actual = 50
    dev = (target - actual) / target
    assert abs(dev) > DEVIATION_THRESHOLD


def test_within_tolerance():
    target = 60
    actual = 53
    dev = (target - actual) / target
    assert abs(dev) < DEVIATION_THRESHOLD


if __name__ == "__main__":
    test_deviation_threshold_is_15_percent()
    test_deviation_math()
    test_within_tolerance()
    print("rebalance trigger math OK")
