from sqlalchemy import BigInteger,String
from sqlalchemy.orm import Mapped,mapped_column

from know_engine_py.app.models.base import Base,BaseEntity

class DemoEntity(Base,BaseEntity):
    __tablename__ = "demo_entity"

    id: Mapped[int] = mapped_column(
        BigInteger,primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(64),nullable=False
    )

def test_base_entity_provides_common_columns():
    columns = DemoEntity.__table__.columns


    assert "created_at" in columns
    assert "updated_at" in columns
    assert "deleted" in columns
    assert "lock_version" in columns

def test_base_entity_does_not_force_primary_key_name():
    columns = DemoEntity.__table__.columns

    assert "id" in columns
    assert columns["id"].primary_key is True