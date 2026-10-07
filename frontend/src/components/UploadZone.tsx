import { useCallback, useRef, useState } from "react";

interface Props {
  disabled: boolean;
  onFile: (file: File) => void;
}

export function UploadZone({ disabled, onFile }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  return (
    <div
      className={`upload-zone${dragOver ? " drag-over" : ""}${disabled ? " disabled" : ""}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(e) => handleFiles(e.target.files)}
      />
      <p className="upload-hint">点击或拖拽上传 PDF</p>
      <p className="upload-sub">支持混合尺寸与旋转页面；加密或损坏文件将提示具体原因</p>
    </div>
  );
}
