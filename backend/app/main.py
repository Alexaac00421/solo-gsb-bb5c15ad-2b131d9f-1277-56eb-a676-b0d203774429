"""FastAPI 入口：上传检查、拼版、预览、下载。"""

from __future__ import annotations

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .imposition import (
    DUPLEX_MODES,
    PAPER_SIZES,
    SIGNATURE_SIZES,
    ImposeOptions,
    ImpositionError,
    impose_pdf,
    inspect_pdf,
    render_preview,
)
from .store import store

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

app = FastAPI(title="骑马钉拼版", version="1.0.0")

# 默认同源（nginx 反代 /api），CORS 仅供本地前后端分离开发
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OptionsResponse(BaseModel):
    papers: list[str]
    signature_sizes: list[int]
    duplex_modes: list[str]


class ImposeRequest(BaseModel):
    paper: str = "A4"
    binding: str = "left"
    signature_pages: int = 8
    duplex: str = "long-edge"
    margin_mm: float = Field(default=8.0, ge=0.0, le=30.0)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/options", response_model=OptionsResponse)
def options() -> OptionsResponse:
    return OptionsResponse(
        papers=list(PAPER_SIZES.keys()),
        signature_sizes=list(SIGNATURE_SIZES),
        duplex_modes=list(DUPLEX_MODES),
    )


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """上传并校验 PDF：加密/损坏在此即报明原因，且不留半成品。"""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过大小限制（{MAX_UPLOAD_MB} MB）")
    try:
        info = inspect_pdf(data)
    except ImpositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    doc_id = store.put_document(data, file.filename or "document.pdf", info)
    return {"document_id": doc_id, "filename": file.filename, **info}


@app.post("/api/documents/{document_id}/impose")
def impose(document_id: str, req: ImposeRequest) -> dict:
    entry = store.get_document(document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="原稿不存在或已过期，请重新上传")
    opts = ImposeOptions(
        paper=req.paper,
        binding=req.binding,
        signature_pages=req.signature_pages,
        duplex=req.duplex,
        margin_mm=req.margin_mm,
    )
    try:
        result = impose_pdf(entry.data, opts)
    except ImpositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # 防御：任何意外失败都不留半成品
        raise HTTPException(status_code=500, detail=f"拼版失败：{exc}") from exc

    def pno(n: int | None) -> int | None:
        return None if n is None else n + 1  # 对外展示用 1 基页码

    meta = {
        "sheet_count": result.sheet_count,
        "signature_count": result.signature_count,
        "blank_count": result.blank_count,
        "sheets": [
            {
                "signature": sh.signature + 1,
                "front": [pno(sh.front_left), pno(sh.front_right)],
                "back": [pno(sh.back_left), pno(sh.back_right)],
            }
            for sh in result.sheets
        ],
    }
    job_id = store.put_job(result.pdf_bytes, meta)
    return {"job_id": job_id, **meta}


@app.get("/api/jobs/{job_id}/previews/{sheet_index}/{side}")
def preview(job_id: str, sheet_index: int, side: str) -> Response:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side 须为 front 或 back")
    sheet_count = job.meta["sheet_count"]
    if not (0 <= sheet_index < sheet_count):
        raise HTTPException(status_code=404, detail="纸张序号越界")
    page_index = sheet_index * 2 + (0 if side == "front" else 1)
    try:
        png = render_preview(job.pdf_bytes, page_index)
    except ImpositionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png")


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str) -> Response:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return Response(
        content=job.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="booklet.pdf"'},
    )
