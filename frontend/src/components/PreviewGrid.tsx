import type { ImposeResult } from "../api";
import { downloadUrl, previewUrl } from "../api";

interface Props {
  result: ImposeResult;
}

function pageLabel(n: number | null): string {
  return n === null ? "空白" : `第 ${n} 页`;
}

export function PreviewGrid({ result }: Props) {
  return (
    <section className="preview">
      <div className="preview-header">
        <h2>预览与下载</h2>
        <p>
          共 {result.signature_count} 帖 / {result.sheet_count} 张纸，补白{" "}
          {result.blank_count} 页
        </p>
        <a className="primary download" href={downloadUrl(result.job_id)} download="booklet.pdf">
          下载可打印 PDF
        </a>
      </div>

      {result.sheets.map((sheet, i) => (
        <div className="sheet" key={i}>
          <h3>
            第 {i + 1} 张（第 {sheet.signature} 帖）
          </h3>
          <div className="sheet-sides">
            {(["front", "back"] as const).map((side) => (
              <figure key={side}>
                <img
                  src={previewUrl(result.job_id, i, side)}
                  alt={`第 ${i + 1} 张${side === "front" ? "正面" : "背面"}`}
                  loading="lazy"
                />
                <figcaption>
                  {side === "front" ? "正面" : "背面"}：左 {pageLabel(sheet[side][0])} ｜ 右{" "}
                  {pageLabel(sheet[side][1])}
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
