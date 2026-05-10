from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from know_engine_py.app.db.session import create_session_maker_from_engine
from know_engine_py.app.models.base import Base
from know_engine_py.app.models.document import (
    KnowledgeDocumentModel,
    KnowledgeSegmentModel,
    TableMetaModel,
)


async def create_test_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_document_models_can_be_inserted_and_queried():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_maker = create_session_maker_from_engine(engine)

    await create_test_tables(engine)

    async with session_maker() as session:
        document = KnowledgeDocumentModel(
            doc_title="比亚迪汉用户手册.pdf",
            upload_user="user-001",
            doc_url="s3://know-engine/docs/byd-han.pdf",
            converted_doc_url="s3://know-engine/converted/byd-han.md",
            expire_date=date(2026, 12, 31),
            status="CHUNKED",
            accessible_by="public",
            description="汽车知识库样例文档",
            knowledge_base_type="DOCUMENT_SEARCH",
            extension={"isOverride": True, "source": "manual"},
        )
        table_meta = TableMetaModel(
            table_name="vehicle_price",
            description="车型价格表",
            create_sql="CREATE TABLE vehicle_price (...)",
            columns_info=[
                {"name": "model", "type": "varchar", "comment": "车型"},
                {"name": "price", "type": "decimal", "comment": "指导价"},
            ],
        )

        session.add_all([document, table_meta])
        await session.flush()

        segment_2 = KnowledgeSegmentModel(
            text="第二段：动力与续航。",
            chunk_id="chunk-002",
            document_id=document.doc_id,
            chunk_order=2,
            status="STORED",
            skip_embedding=0,
            extra_metadata={"section": "power"},
        )
        segment_1 = KnowledgeSegmentModel(
            text="第一段：车型概览。",
            chunk_id="chunk-001",
            document_id=document.doc_id,
            chunk_order=1,
            status="STORED",
            skip_embedding=0,
            extra_metadata={"section": "overview"},
        )

        session.add_all([segment_2, segment_1])
        await session.commit()

    async with session_maker() as session:
        document = (
            await session.execute(
                select(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.doc_title == "比亚迪汉用户手册.pdf"
                )
            )
        ).scalar_one()

        segments = (
            await session.execute(
                select(KnowledgeSegmentModel)
                .where(KnowledgeSegmentModel.document_id == document.doc_id)
                .order_by(KnowledgeSegmentModel.chunk_order)
            )
        ).scalars().all()

        table_meta = (
            await session.execute(
                select(TableMetaModel).where(
                    TableMetaModel.table_name == "vehicle_price"
                )
            )
        ).scalar_one()

    assert document.status == "CHUNKED"
    assert document.knowledge_base_type == "DOCUMENT_SEARCH"
    assert document.extension["isOverride"] is True

    assert [segment.chunk_id for segment in segments] == ["chunk-001", "chunk-002"]
    assert segments[0].extra_metadata["section"] == "overview"
    assert segments[1].skip_embedding == 0

    assert table_meta.columns_info[0]["name"] == "model"
    assert table_meta.columns_info[1]["comment"] == "指导价"
