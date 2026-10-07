"""骑马钉小册子拼版核心逻辑。

使用 PyMuPDF 完成：
- 读取混合尺寸 / 带旋转角度的 PDF 页面；
- 按每帖 4/8/16 页分帖，每帖独立补白至 4 的倍数，帖间不借页；
- 生成骑马钉版序（折手后页序与原稿一致）；
- 原稿页面等比缩入版心（半张纸的单元格），正反面对位；
- 按双面翻转方式（长边/短边）旋转背面内容。
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field

import fitz  # PyMuPDF

MM_TO_PT = 72.0 / 25.4

# 纸张（竖向尺寸，单位 mm），拼版时一律横向使用
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
    "Tabloid": (279.4, 431.8),
}

SIGNATURE_SIZES = (4, 8, 16)
BINDING_SIDES = ("left", "right")
DUPLEX_MODES = ("long-edge", "short-edge")


class ImpositionError(Exception):
    """可预期的业务错误（加密、损坏、参数非法等），message 面向用户。"""


@dataclass
class SheetPlan:
    """一张纸的两面。left/right 为全局页码（0 基），None 表示补白。"""

    front_left: int | None
    front_right: int | None
    back_left: int | None
    back_right: int | None
    signature: int  # 第几帖（0 基）


@dataclass
class ImposeOptions:
    paper: str = "A4"
    binding: str = "left"          # left / right（装订边）
    signature_pages: int = 8       # 每帖页数 4/8/16
    duplex: str = "long-edge"      # 打印机双面翻转方式
    margin_mm: float = 8.0         # 版心内边距


@dataclass
class ImposeResult:
    pdf_bytes: bytes
    sheets: list[SheetPlan] = field(default_factory=list)
    signature_count: int = 0
    blank_count: int = 0
    sheet_count: int = 0


def _validate_options(opts: ImposeOptions) -> None:
    if opts.paper not in PAPER_SIZES:
        raise ImpositionError(f"不支持的纸张：{opts.paper}")
    if opts.binding not in BINDING_SIDES:
        raise ImpositionError(f"不支持的装订方向：{opts.binding}")
    if opts.signature_pages not in SIGNATURE_SIZES:
        raise ImpositionError(f"每帖页数须为 4/8/16，收到：{opts.signature_pages}")
    if opts.duplex not in DUPLEX_MODES:
        raise ImpositionError(f"不支持的双面翻转方式：{opts.duplex}")
    if not (0.0 <= opts.margin_mm <= 30.0):
        raise ImpositionError("版心边距须在 0–30 mm 之间")


def open_source_pdf(data: bytes) -> fitz.Document:
    """打开上传的 PDF，加密/损坏时抛出带明确原因的 ImpositionError。"""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # fitz.FileDataError 等
        raise ImpositionError(f"文件损坏或不是有效的 PDF：{exc}") from exc
    if doc.needs_pass:
        # 先尝试空口令（部分文件仅设所有者口令）
        if doc.authenticate("") == 0:
            doc.close()
            raise ImpositionError("文件已加密（需要打开口令），请先解密后再上传")
    if doc.is_encrypted:
        doc.close()
        raise ImpositionError("文件使用了不支持的加密方式，请先解密后再上传")
    if doc.page_count == 0:
        doc.close()
        raise ImpositionError("PDF 不含任何页面")
    return doc


def inspect_pdf(data: bytes) -> dict:
    """返回页数与每页尺寸/旋转信息，供前端展示。"""
    doc = open_source_pdf(data)
    try:
        pages = []
        for page in doc:
            rect = page.rect  # 已计入 /Rotate 的有效尺寸
            pages.append(
                {
                    "width_mm": round(rect.width / MM_TO_PT, 1),
                    "height_mm": round(rect.height / MM_TO_PT, 1),
                    "rotation": page.rotation,
                }
            )
        return {"page_count": doc.page_count, "pages": pages}
    finally:
        doc.close()


def build_sheet_plans(page_count: int, opts: ImposeOptions) -> tuple[list[SheetPlan], int, int]:
    """生成每张纸正/反面的页码排布。

    返回 (sheets, signature_count, blank_count)。
    每帖 sig 页，最后一帖不足时独立补白至 4 的倍数，帖间不借页。
    """
    sig = opts.signature_pages
    sheets: list[SheetPlan] = []
    blank_count = 0
    sig_count = math.ceil(page_count / sig)

    for s in range(sig_count):
        start = s * sig
        real = min(sig, page_count - start)          # 本帖实际页数
        padded = max(4, math.ceil(real / 4) * 4)     # 独立补白至 4 的倍数
        blank_count += padded - real

        def label(k: int) -> int | None:
            """帖内 1 基页码 -> 全局 0 基页码，超出实际页为补白。"""
            return (start + k - 1) if k <= real else None

        for i in range(padded // 4):
            fl, fr = padded - 2 * i, 2 * i + 1
            bl, br = 2 * i + 2, padded - 2 * i - 1
            if opts.binding == "right":  # 右装订：左右镜像
                fl, fr = fr, fl
                bl, br = br, bl
            sheets.append(
                SheetPlan(
                    front_left=label(fl),
                    front_right=label(fr),
                    back_left=label(bl),
                    back_right=label(br),
                    signature=s,
                )
            )
    return sheets, sig_count, blank_count


def _paper_rect(opts: ImposeOptions) -> fitz.Rect:
    w_mm, h_mm = PAPER_SIZES[opts.paper]
    # 横向使用：长边水平
    width, height = max(w_mm, h_mm) * MM_TO_PT, min(w_mm, h_mm) * MM_TO_PT
    return fitz.Rect(0, 0, width, height)


def _cell_rects(sheet: fitz.Rect, margin_mm: float) -> tuple[fitz.Rect, fitz.Rect]:
    """左右两个版心（含内边距）。"""
    m = margin_mm * MM_TO_PT
    mid = sheet.width / 2
    left = fitz.Rect(m, m, mid - m, sheet.height - m)
    right = fitz.Rect(mid + m, m, sheet.width - m, sheet.height - m)
    return left, right


def _place(out_page: fitz.Page, src: fitz.Document, pno: int | None,
           cell: fitz.Rect, rotate: int) -> None:
    """把原稿一页等比缩入版心；补白页留空。"""
    if pno is None:
        return
    # 源页旋转已在 _normalize_rotation 中烘焙；keep_proportion 保证等比居中放入版心
    out_page.show_pdf_page(cell, src, pno, rotate=rotate, keep_proportion=True)


def _normalize_rotation(doc: fitz.Document) -> None:
    """把源页的 /Rotate 烘焙进页面内容（show_pdf_page 不会自动应用旋转）。"""
    for page in doc:
        if page.rotation:
            page.remove_rotation()


def impose_pdf(data: bytes, opts: ImposeOptions) -> ImposeResult:
    """核心入口：上传字节 -> 可打印 PDF 字节。"""
    _validate_options(opts)
    src = open_source_pdf(data)
    try:
        _normalize_rotation(src)
        sheets, sig_count, blank_count = build_sheet_plans(src.page_count, opts)
        sheet_rect = _paper_rect(opts)
        left_cell, right_cell = _cell_rects(sheet_rect, opts.margin_mm)
        # 长边翻转（沿水平长边翻纸）时背面需旋转 180° 才能与正面对位
        back_rotate = 180 if opts.duplex == "long-edge" else 0

        out = fitz.open()
        try:
            for sh in sheets:
                front = out.new_page(width=sheet_rect.width, height=sheet_rect.height)
                _place(front, src, sh.front_left, left_cell, 0)
                _place(front, src, sh.front_right, right_cell, 0)
                back = out.new_page(width=sheet_rect.width, height=sheet_rect.height)
                _place(back, src, sh.back_left, left_cell, back_rotate)
                _place(back, src, sh.back_right, right_cell, back_rotate)

            buf = io.BytesIO()
            out.save(buf, garbage=4, deflate=True)
            pdf_bytes = buf.getvalue()
        finally:
            out.close()
    finally:
        src.close()

    return ImposeResult(
        pdf_bytes=pdf_bytes,
        sheets=sheets,
        signature_count=sig_count,
        blank_count=blank_count,
        sheet_count=len(sheets),
    )


def render_preview(pdf_bytes: bytes, page_index: int, zoom: float = 1.4) -> bytes:
    """把成品 PDF 的某一页渲染成 PNG（用于正/反面预览）。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if not (0 <= page_index < doc.page_count):
            raise ImpositionError(f"预览页码越界：{page_index}")
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()
