import { useState } from "react";
import type { DocumentInfo, ImposeOptions, ImposeResult } from "./api";
import { ApiError, impose, uploadDocument } from "./api";
import { UploadZone } from "./components/UploadZone";
import { OptionsForm } from "./components/OptionsForm";
import { PreviewGrid } from "./components/PreviewGrid";

const DEFAULT_OPTIONS: ImposeOptions = {
  paper: "A4",
  binding: "left",
  signature_pages: 8,
  duplex: "long-edge",
  margin_mm: 8,
};

export default function App() {
  const [doc, setDoc] = useState<DocumentInfo | null>(null);
  const [options, setOptions] = useState<ImposeOptions>(DEFAULT_OPTIONS);
  const [result, setResult] = useState<ImposeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setDoc(null);
    setResult(null);
    try {
      setDoc(await uploadDocument(file));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败，请重试");
    } finally {
      setBusy(false);
    }
  }

  async function handleImpose() {
    if (!doc) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      setResult(await impose(doc.document_id, options));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "拼版失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <header>
        <h1>骑马钉小册子拼版</h1>
        <p>上传 PDF → 选择纸张与装订方式 → 预览每张纸正反面 → 下载可打印 PDF</p>
      </header>

      <UploadZone disabled={busy} onFile={handleFile} />
      {busy && <p className="status">正在上传并检查文件…</p>}
      {error && <p className="error">⚠ {error}</p>}

      {doc && (
        <section className="doc-info">
          <h2>原稿信息</h2>
          <p>
            {doc.filename}：共 {doc.page_count} 页
          </p>
          <details>
            <summary>逐页尺寸与旋转</summary>
            <table>
              <thead>
                <tr>
                  <th>页码</th>
                  <th>宽 (mm)</th>
                  <th>高 (mm)</th>
                  <th>旋转</th>
                </tr>
              </thead>
              <tbody>
                {doc.pages.map((p, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>{p.width_mm}</td>
                    <td>{p.height_mm}</td>
                    <td>{p.rotation}°</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>
      )}

      {doc && (
        <OptionsForm
          value={options}
          disabled={busy}
          submitting={submitting}
          onChange={setOptions}
          onSubmit={handleImpose}
        />
      )}

      {result && <PreviewGrid result={result} />}
    </main>
  );
}
