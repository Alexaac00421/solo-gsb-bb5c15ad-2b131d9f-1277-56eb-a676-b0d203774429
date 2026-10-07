"""拼版核心逻辑与 API 测试。"""

from __future__ import annotations

import fitz
import pytest
from fastapi.testclient import TestClient

from app.imposition import (
    ImposeOptions,
    ImpositionError,
    impose_pdf,
    inspect_pdf,
    open_source_pdf,
)
from app.main import app

client = TestClient(app)


def make_pdf(page_sizes: list[tuple[float, float]], rotations: dict[int, int] | None = None) -> bytes:
    """生成测试 PDF：每页画一个带页码的矩形，支持指定尺寸与旋转。"""
    doc = fitz.open()
    for i, (w, h) in enumerate(page_sizes):
        page = doc.new_page(width=w, height=h)
        page.draw_rect(fitz.Rect(10, 10, w - 10, h - 10), color=(1, 0, 0), width=2)
        page.insert_text((w / 2 - 10, h / 2), str(i + 1), fontsize=24)
        if rotations and i in rotations:
            page.set_rotation(rotations[i])
    data = doc.tobytes()
    doc.close()
    return data


def make_encrypted_pdf(password: str = "secret") -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    out = fitz.open()
    out.insert_pdf(doc)
    data = out.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password,
    )
    doc.close()
    out.close()
    return data


# ---------- 版序 ----------

def plan_pages(opts: ImposeOptions, page_count: int):
    from app.imposition import build_sheet_plans

    sheets, sig_count, blanks = build_sheet_plans(page_count, opts)
    return sheets, sig_count, blanks


def test_single_signature_4_pages():
    opts = ImposeOptions(signature_pages=4)
    sheets, sigs, blanks = plan_pages(opts, 4)
    assert sigs == 1 and blanks == 0 and len(sheets) == 1
    sh = sheets[0]
    assert (sh.front_left, sh.front_right) == (3, 0)  # 4,1
    assert (sh.back_left, sh.back_right) == (1, 2)    # 2,3


def test_single_signature_8_pages():
    opts = ImposeOptions(signature_pages=8)
    sheets, sigs, blanks = plan_pages(opts, 8)
    assert sigs == 1 and blanks == 0 and len(sheets) == 2
    assert (sheets[0].front_left, sheets[0].front_right) == (7, 0)  # 8,1
    assert (sheets[0].back_left, sheets[0].back_right) == (1, 6)    # 2,7
    assert (sheets[1].front_left, sheets[1].front_right) == (5, 2)  # 6,3
    assert (sheets[1].back_left, sheets[1].back_right) == (3, 4)    # 4,5


def test_last_signature_padded_to_multiple_of_4_not_borrowed():
    # 10 页、每帖 8：第一帖 8 页，第二帖 2 页补白到 4（而不是借第一帖的页）
    opts = ImposeOptions(signature_pages=8)
    sheets, sigs, blanks = plan_pages(opts, 10)
    assert sigs == 2 and blanks == 2
    sig1 = [s for s in sheets if s.signature == 0]
    sig2 = [s for s in sheets if s.signature == 1]
    assert len(sig1) == 2 and len(sig2) == 1
    # 第二帖：页 9,10 + 2 个补白 -> front [None, 9], back [10, None]
    sh = sig2[0]
    assert (sh.front_left, sh.front_right) == (None, 8)
    assert (sh.back_left, sh.back_right) == (9, None)
    # 第一帖不受影响
    assert (sig1[0].front_left, sig1[0].front_right) == (7, 0)


def test_right_binding_mirrors_left_right():
    opts = ImposeOptions(signature_pages=4, binding="right")
    sheets, _, _ = plan_pages(opts, 4)
    sh = sheets[0]
    assert (sh.front_left, sh.front_right) == (0, 3)  # 1,4
    assert (sh.back_left, sh.back_right) == (2, 1)    # 3,2


def test_folded_reading_order_matches_source():
    # 模拟折手：每帖内先按纸张顺序读 front_right/back_left（书帖前半），
    # 再按相反顺序读 back_right/front_left（书帖后半），即得原稿页序
    opts = ImposeOptions(signature_pages=16)
    page_count = 40
    sheets, _, _ = plan_pages(opts, page_count)
    by_sig: dict[int, list] = {}
    for sh in sheets:
        by_sig.setdefault(sh.signature, []).append(sh)
    reading: list[int | None] = []
    for sig_sheets in by_sig.values():
        reading.extend(p for sh in sig_sheets for p in (sh.front_right, sh.back_left))
        reading.extend(p for sh in reversed(sig_sheets) for p in (sh.back_right, sh.front_left))
    real = [p for p in reading if p is not None]
    assert real == list(range(page_count))


# ---------- 文件校验 ----------

def test_encrypted_pdf_reports_reason():
    with pytest.raises(ImpositionError, match="加密"):
        open_source_pdf(make_encrypted_pdf())


def test_corrupt_pdf_reports_reason():
    with pytest.raises(ImpositionError, match="损坏|有效"):
        open_source_pdf(b"this is not a pdf at all")


def test_empty_pdf_rejected():
    # 手工构造 0 页 PDF（fitz 无法直接保存 0 页文档）
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
        b"trailer << /Root 1 0 R >>\n"
    )
    with pytest.raises(ImpositionError, match="不含任何页面"):
        open_source_pdf(data)


# ---------- 端到端 ----------

def test_impose_mixed_sizes_and_rotations():
    # 混合尺寸 + 部分页面旋转 90°
    sizes = [(595, 842), (842, 595), (612, 792), (500, 500), (595, 842), (400, 700)]
    pdf = make_pdf(sizes, rotations={1: 90, 3: 270})
    info = inspect_pdf(pdf)
    assert info["page_count"] == 6
    assert info["pages"][1]["rotation"] == 90
    # 旋转 90° 后有效宽高互换
    assert info["pages"][1]["width_mm"] < info["pages"][1]["height_mm"]

    result = impose_pdf(pdf, ImposeOptions(signature_pages=4, paper="A4"))
    assert result.sheet_count == 2  # 6 页 -> 两帖(4+4，第二帖补 2 白)
    assert result.blank_count == 2
    out = fitz.open(stream=result.pdf_bytes, filetype="pdf")
    assert out.page_count == 4  # 每张纸正/反两页
    # 每页都应有内容或为空页，纸张横向
    assert out[0].rect.width > out[0].rect.height
    out.close()


def test_rotated_source_page_lands_upright_in_cell():
    # 横向原稿 + /Rotate 90 -> 有效竖向，应竖直填满版心（内容框高 > 宽）
    pdf = make_pdf([(842, 595)], rotations={0: 90})
    result = impose_pdf(pdf, ImposeOptions(signature_pages=4, duplex="short-edge"))
    out = fitz.open(stream=result.pdf_bytes, filetype="pdf")
    # 第 1 页在第二张纸正面右格（帖内页序 4,1 / 2,3：页 1 在 front_right）
    # 4 页一帖共 1 张纸：front=[4,1] -> 页 1 在第 0 张正面右侧
    front = out[0]
    bboxes = [d["rect"] for d in front.get_drawings()]
    assert bboxes, "正面应包含原稿内容"
    box = bboxes[0]
    assert box.height > box.width  # 竖向放置
    # 内容应在纸张右半部分
    assert box.x0 > front.rect.width / 2
    out.close()


def test_impose_output_pages_have_content_except_blanks():
    pdf = make_pdf([(595, 842)] * 5)
    result = impose_pdf(pdf, ImposeOptions(signature_pages=4))
    out = fitz.open(stream=result.pdf_bytes, filetype="pdf")
    # 5 页 -> 两帖：帖1 满(4)，帖2 一页补到 4（3 个补白）
    assert result.blank_count == 3
    # 第一张正面（页 4,1）应有绘图内容
    assert out[0].get_drawings() or out[0].get_text()
    out.close()


# ---------- API ----------

def test_api_upload_impose_preview_download():
    pdf = make_pdf([(595, 842)] * 9)
    r = client.post("/api/documents", files={"file": ("t.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    doc_id = r.json()["document_id"]
    assert r.json()["page_count"] == 9

    r = client.post(f"/api/documents/{doc_id}/impose", json={
        "paper": "A4", "binding": "left", "signature_pages": 8,
        "duplex": "long-edge", "margin_mm": 8,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signature_count"] == 2
    assert body["blank_count"] == 3  # 第二帖 1 页补到 4
    assert body["sheet_count"] == 3
    job_id = body["job_id"]

    r = client.get(f"/api/jobs/{job_id}/previews/0/front")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    r = client.get(f"/api/jobs/{job_id}/previews/2/back")
    assert r.status_code == 200
    r = client.get(f"/api/jobs/{job_id}/download")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_api_encrypted_upload_422():
    r = client.post(
        "/api/documents",
        files={"file": ("enc.pdf", make_encrypted_pdf(), "application/pdf")},
    )
    assert r.status_code == 422
    assert "加密" in r.json()["detail"]


def test_api_corrupt_upload_422():
    r = client.post("/api/documents", files={"file": ("bad.pdf", b"garbage", "application/pdf")})
    assert r.status_code == 422
    assert "损坏" in r.json()["detail"] or "有效" in r.json()["detail"]


def test_api_rejects_non_pdf_extension():
    r = client.post("/api/documents", files={"file": ("a.txt", b"%PDF-1.4", "text/plain")})
    assert r.status_code == 400


def test_api_expired_document_404():
    r = client.post("/api/documents/nonexistent/impose", json={})
    assert r.status_code == 404
