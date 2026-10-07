import type { ImposeOptions } from "../api";

interface Props {
  value: ImposeOptions;
  disabled: boolean;
  onChange: (next: ImposeOptions) => void;
  onSubmit: () => void;
  submitting: boolean;
}

const PAPERS = ["A4", "A3", "A5", "Letter", "Tabloid"];

export function OptionsForm({ value, disabled, onChange, onSubmit, submitting }: Props) {
  const set = <K extends keyof ImposeOptions>(key: K, v: ImposeOptions[K]) =>
    onChange({ ...value, [key]: v });

  return (
    <section className="options">
      <h2>拼版选项</h2>
      <div className="options-grid">
        <label>
          纸张
          <select
            value={value.paper}
            disabled={disabled}
            onChange={(e) => set("paper", e.target.value)}
          >
            {PAPERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>

        <label>
          装订方向
          <select
            value={value.binding}
            disabled={disabled}
            onChange={(e) => set("binding", e.target.value as "left" | "right")}
          >
            <option value="left">左装订</option>
            <option value="right">右装订</option>
          </select>
        </label>

        <label>
          每帖页数
          <select
            value={value.signature_pages}
            disabled={disabled}
            onChange={(e) => set("signature_pages", Number(e.target.value))}
          >
            {[4, 8, 16].map((n) => (
              <option key={n} value={n}>
                {n} 页 / 帖
              </option>
            ))}
          </select>
        </label>

        <label>
          双面翻转方式
          <select
            value={value.duplex}
            disabled={disabled}
            onChange={(e) => set("duplex", e.target.value as "long-edge" | "short-edge")}
          >
            <option value="long-edge">长边翻转</option>
            <option value="short-edge">短边翻转</option>
          </select>
        </label>

        <label>
          版心边距（mm）
          <input
            type="number"
            min={0}
            max={30}
            step={1}
            value={value.margin_mm}
            disabled={disabled}
            onChange={(e) => set("margin_mm", Number(e.target.value))}
          />
        </label>
      </div>

      <p className="options-note">
        纸张横向使用；选择「长边翻转」时背面将自动旋转 180° 以保证正反对位。
        每帖独立补白至 4 的倍数，帖间不借页。
      </p>

      <button className="primary" disabled={disabled || submitting} onClick={onSubmit}>
        {submitting ? "拼版中…" : "开始拼版"}
      </button>
    </section>
  );
}
