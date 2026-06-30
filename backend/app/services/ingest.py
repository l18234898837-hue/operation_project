from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag import (
    DocumentStatus,
    KbDocument,
    KbDocumentSegment,
    ParseTask,
    ParseTaskStatus,
)
from app.services.keyword_index import build_keyword_text
from app.services.markdown_chunker import chunk_markdown


@dataclass(frozen=True)
class MarkdownDocument:
    path: Path
    title: str
    content: str
    file_sha256: str


class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


_NUMERIC_PREFIX_RE = re.compile(r"^\d+[\s_.-]*")


def load_markdown_documents(directory: Path) -> list[MarkdownDocument]:
    documents: list[MarkdownDocument] = []

    for path in sorted(directory.glob("*.md")):
        if not path.is_file():
            continue
        content_bytes = path.read_bytes()
        documents.append(
            MarkdownDocument(
                path=path,
                title=_title_from_path(path),
                content=content_bytes.decode("utf-8"),
                file_sha256=hashlib.sha256(content_bytes).hexdigest(),
            )
        )

    return documents


# 异步函数：导入单个md文档到知识库，返回文档UUID主键
# session：SQLAlchemy数据库会话
# document：封装md文件路径、内容、哈希、标题的MarkdownDocument对象
# embedding_client：向量生成客户端（遵循EmbeddingClient协议，SiliconFlowEmbeddingClient实现）
# embedding_model：当前使用的向量模型名称，存入分片表做版本区分
async def import_markdown_document(
    session: Session,
    document: MarkdownDocument,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> uuid.UUID:
    document_id, _created = await import_markdown_document_with_result(
        session=session,
        document=document,
        embedding_client=embedding_client,
        embedding_model=embedding_model,
    )
    return document_id


async def import_markdown_document_with_result(
    session: Session,
    document: MarkdownDocument,
    embedding_client: EmbeddingClient,
    embedding_model: str,
) -> tuple[uuid.UUID, bool]:
    # 记录函数开始时间，用于计算解析总耗时(毫秒)
    started = time.perf_counter()
    # 声明文档主表实例变量，初始为空
    kb_document: KbDocument | None = None
    # 声明解析任务实例变量，初始为空
    task: ParseTask | None = None
    # 标记是否可以把失败状态写入数据库；只有文档、任务flush到数据库后才置为True
    can_persist_failure = False

    try:
        # ====================== 1. 文件查重：通过sha256判断文档是否已导入 ======================
        # 查询kb_document表，匹配当前文件sha256哈希值
        existing = session.execute(
            select(KbDocument).where(KbDocument.file_sha256 == document.file_sha256)
        ).scalar_one_or_none()
        # 查到已存在文档，直接返回已有文档ID，跳过全部导入逻辑，避免重复入库
        if existing is not None:
            return existing.id, False

        # ====================== 2. 创建知识库文档主记录 ======================
        kb_document = KbDocument(
            title=document.title,                          # 文档标题（去除文件名数字前缀）
            source_path=str(document.path),                 # md文件本地路径
            file_name=document.path.name,                   # 原始文档文件名，用于问答引用展示
            file_sha256=document.file_sha256,              # 文件哈希，用于全局去重
            file_type="markdown",                           # 文件类型标记
            status=DocumentStatus.processing,                # 状态：处理中
            enabled=True,                                   # 默认启用，检索可命中
            error_message=None,                             # 暂无错误信息
            document_metadata={"source_file_name": document.path.name}, # 扩展元数据：原始文件名
        )
        # 将文档对象加入会话缓存，暂不提交数据库
        session.add(kb_document)
        # flush：强制写入数据库，立刻生成kb_document.id（UUID主键），后续任务/分片需要关联该ID
        session.flush()

        # ====================== 3. 创建文档解析任务记录 ======================
        task = ParseTask(
            document_id=kb_document.id,                    # 关联当前文档主键
            status=ParseTaskStatus.running,                 # 任务状态：运行中
            retry_count=0,                                  # 重试次数初始0
            error_message=None,                             # 无报错
            started_at=datetime.now(UTC),                   # 任务开始时间（UTC标准时间）
        )
        session.add(task)
        session.flush()
        # 文档、任务已写入数据库，后续异常可以更新失败状态并提交
        can_persist_failure = True

        # ====================== 4. Markdown文本分片（按标题层级切割chunk） ======================
        # 调用分片工具，把完整md文本拆分成多个结构化分片对象
        chunks = chunk_markdown(document.content, source_title=document.title)
        # 分片为空，抛出异常，进入except失败分支
        if not chunks:
            raise ValueError(f"No chunks produced for {document.path.name}")

        # ====================== 5. 批量调用向量接口生成1024维向量 ======================
        # 提取所有分片的检索文本，批量请求向量接口（批量调用减少网络开销）
        embeddings = await embedding_client.embed([chunk.indexed_text for chunk in chunks])
        # 校验返回向量数量和分片数量一致，防止接口返回数据缺失
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"Expected {len(chunks)} embeddings, got {len(embeddings)}"
            )

        # ====================== 6. 循环写入所有分片+向量到kb_document_segment ======================
        # zip绑定分片与对应向量，chunk_index记录分片在文档内序号
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            session.add(
                KbDocumentSegment(
                    document_id=kb_document.id,            # 关联所属文档
                    chunk_index=chunk_index,               # 分片序号，同一文档内唯一
                    heading_path=chunk.heading_path,        # 层级标题路径（如03_线缆接头 > 4.绝缘阻抗）
                    section_title=chunk.section_title,      # 当前分片小标题
                    raw_text=chunk.raw_text,               # 原始未清洗文本
                    clean_text=chunk.clean_text,           # 清洗后展示文本
                    indexed_text=chunk.indexed_text,        # 用于向量/关键词检索的完整文本
                    keyword_text=build_keyword_text(chunk.indexed_text), # 分词关键词文本，供PG全文检索
                    token_count=None,                      # 预留token统计字段，暂不填充
                    char_count=chunk.char_count,           # 分片字符总数
                    embedding_model=embedding_model,       # 生成向量使用的模型名
                    embedding=embedding,                   # 1024维浮点向量数组
                    segment_metadata=chunk.metadata,       # 分片扩展自定义元数据
                )
            )

        # ====================== 7. 全部分片入库完成，更新文档、任务为成功状态 ======================
        kb_document.status = DocumentStatus.ready          # 文档状态改为就绪，可参与检索
        kb_document.segment_count = len(chunks)            # 填充文档总分片数量
        kb_document.error_message = None                   # 清空错误信息
        task.status = ParseTaskStatus.success              # 任务状态：成功
        task.error_message = None                         # 清空任务报错
        task.finished_at = datetime.now(UTC)               # 任务结束UTC时间
        task.duration_ms = _duration_ms(started)           # 计算总耗时毫秒

        # 提交本次会话所有新增/修改数据到数据库（文档、任务、所有分片一次性落库）
        session.commit()
        # 返回当前文档唯一ID，供外层脚本打印输出
        return kb_document.id, True

    # ====================== 异常捕获分支：导入流程任意步骤报错执行 ======================
    except Exception as exc:
        # 前置判断：如果还没flush文档/任务，无法更新失败状态，直接回滚会话并抛出异常
        if not can_persist_failure or kb_document is None or task is None:
            _rollback_if_available(session)
            raise
        # 文档、任务已存在，更新状态为failed并保存错误信息到数据库
        _mark_failed(
            session=session,
            kb_document=kb_document,
            task=task,
            error_message=str(exc),
            started=started,
        )
        # 抛出原异常，外层脚本捕获打印报错
        raise


def _title_from_path(path: Path) -> str:
    return _NUMERIC_PREFIX_RE.sub("", path.stem).strip()


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _mark_failed(
    session: Session,
    kb_document: KbDocument,
    task: ParseTask,
    error_message: str,
    started: float,
) -> None:
    kb_document.status = DocumentStatus.failed
    kb_document.error_message = error_message
    task.status = ParseTaskStatus.failed
    task.error_message = error_message
    task.finished_at = datetime.now(UTC)
    task.duration_ms = _duration_ms(started)
    try:
        session.commit()
    except Exception:
        _rollback_if_available(session)


def _rollback_if_available(session: Session) -> None:
    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        rollback()
