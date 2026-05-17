from decimal import Decimal
from datetime import date

from sqlalchemy import Date, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from know_engine_py.app.models.base import Base, BaseEntity


class CarInfoModel(Base, BaseEntity):
    __tablename__ = "car_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    info_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    guide_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="在售")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class MyCarModel(Base, BaseEntity):
    __tablename__ = "my_car"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    car_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    car_info_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plate_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    vin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    insurance_expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspection_expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class CarOrderModel(Base, BaseEntity):
    __tablename__ = "car_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    car_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    order_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="待支付")
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)