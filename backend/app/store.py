"""内存态任务存储：上传的原稿与拼版结果，带过期清理。

所有数据仅保存在内存中，不落盘；处理失败时不产生任何半成品文件。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

TTL_SECONDS = 30 * 60  # 30 分钟过期


@dataclass
class DocumentEntry:
    data: bytes
    filename: str
    info: dict
    created: float = field(default_factory=time.time)


@dataclass
class JobEntry:
    pdf_bytes: bytes
    meta: dict
    created: float = field(default_factory=time.time)


class Store:
    def __init__(self, ttl: int = TTL_SECONDS) -> None:
        self._ttl = ttl
        self._documents: dict[str, DocumentEntry] = {}
        self._jobs: dict[str, JobEntry] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.time()
        for table in (self._documents, self._jobs):
            expired = [k for k, v in table.items() if now - v.created > self._ttl]
            for k in expired:
                del table[k]

    def put_document(self, data: bytes, filename: str, info: dict) -> str:
        with self._lock:
            self._purge()
            doc_id = uuid.uuid4().hex
            self._documents[doc_id] = DocumentEntry(data=data, filename=filename, info=info)
            return doc_id

    def get_document(self, doc_id: str) -> DocumentEntry | None:
        with self._lock:
            self._purge()
            return self._documents.get(doc_id)

    def put_job(self, pdf_bytes: bytes, meta: dict) -> str:
        with self._lock:
            self._purge()
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = JobEntry(pdf_bytes=pdf_bytes, meta=meta)
            return job_id

    def get_job(self, job_id: str) -> JobEntry | None:
        with self._lock:
            self._purge()
            return self._jobs.get(job_id)


store = Store()
