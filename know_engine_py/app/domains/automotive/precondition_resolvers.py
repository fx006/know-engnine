from __future__ import annotations

from collections.abc import Callable, Awaitable
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from know_engine_py.app.models.automotive import CarInfoModel, MyCarModel
from know_engine_py.app.rag.state import AgentState

ResolverFunc = Callable[..., Awaitable[list[dict[str, Any]]]]


class AutomotivePreconditionResolverRegistry:
    """汽车领域前置条件 resolver 白名单。

    clarify_node 只拿 resolver 名称调用这里；真正查 my_car / car_info 的逻辑
    收敛在汽车领域包内，避免 LangGraph 主链路硬编码汽车业务表。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._resolvers: dict[str, ResolverFunc] = {
            "automotive_my_car": self._resolve_my_car,
            "automotive_car_info": self._resolve_car_info,
        }

    async def resolve(
        self,
        resolver_name: str,
        *,
        user_id: str,
        entity_value: str | None,
        state: AgentState,
        check: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """按白名单 resolver 名称查询候选项。"""
        resolver = self._resolvers.get(resolver_name)
        if resolver is None:
            raise ValueError(f"不支持的前置条件 resolver：{resolver_name}")

        return await resolver(
            user_id=user_id,
            entity_value=entity_value,
            state=state,
            check=check,
        )

    async def _resolve_my_car(
        self,
        *,
        user_id: str,
        entity_value: str | None,
        state: AgentState,
        check: dict[str, Any],
    ) -> list[dict[str, Any]]:
        limit = _get_limit(check, default=20)

        stmt = (
            select(MyCarModel)
            .where(MyCarModel.user_id == user_id)
            .where(MyCarModel.deleted == 0)
            .order_by(MyCarModel.updated_at.desc())
            .limit(limit)
        )

        if entity_value:
            stmt = stmt.where(MyCarModel.car_id == entity_value)

        result = await self.db.execute(stmt)
        cars = result.scalars().all()

        return [_my_car_to_card_item(car) for car in cars]

    async def _resolve_car_info(
        self,
        *,
        user_id: str,
        entity_value: str | None,
        state: AgentState,
        check: dict[str, Any],
    ) -> list[dict[str, Any]]:
        limit = _get_limit(check, default=20)

        stmt = (
            select(CarInfoModel)
            .where(CarInfoModel.deleted == 0)
            .order_by(CarInfoModel.updated_at.desc())
            .limit(limit)
        )

        keyword = (entity_value or "").strip()
        if keyword:
            like_value = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    CarInfoModel.brand.ilike(like_value),
                    CarInfoModel.model_name.ilike(like_value),
                    CarInfoModel.full_name.ilike(like_value),
                )
            )

        result = await self.db.execute(stmt)
        cars = result.scalars().all()

        return [_car_info_to_card_item(car) for car in cars]


def _get_limit(check: dict[str, Any], *, default: int) -> int:
    raw_limit = check.get("limit", default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return default

    return max(1, min(limit, 50))


def _my_car_to_card_item(car: MyCarModel) -> dict[str, Any]:
    return {
        "carId": car.car_id,
        "fullName": car.full_name,
        "plateNumber": car.plate_number,
        "imageUrl": car.image_url,
    }


def _car_info_to_card_item(car: CarInfoModel) -> dict[str, Any]:
    return {
        "infoId": car.info_id,
        "brand": car.brand,
        "modelName": car.model_name,
        "fullName": car.full_name,
        "guidePrice": _decimal_to_str(car.guide_price),
        "imageUrl": car.image_url,
    }


def _decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)