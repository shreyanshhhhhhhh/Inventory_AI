"""Load reproducible demo data for a business.

Usage:
    python scripts/seed_demo.py --email owner@example.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

import app.models  # noqa: F401
from app.db import SessionLocal
from app.models import User
from app.services.demo_seed import DemoSeedError, load_demo_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Load demo data for a business.")
    parser.add_argument("--email", required=True, help="Owner email for the target business.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None or user.business_id is None:
            print(f"No business user found for {args.email}", file=sys.stderr)
            return 1
        result = load_demo_data(
            session,
            business_id=user.business_id,
            actor_user_id=user.id,
        )
    except DemoSeedError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    finally:
        session.close()

    print("Demo data loaded:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
