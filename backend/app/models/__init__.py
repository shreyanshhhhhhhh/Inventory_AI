"""SQLAlchemy models.

Domain tables are added in later steps. Importing this package registers
models on ``Base.metadata`` once they exist.
"""

from app.db import Base

__all__ = ["Base"]
