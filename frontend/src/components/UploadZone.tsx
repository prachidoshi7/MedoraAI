import { useCallback, useEffect, useRef, useState } from 'react';
import type { ScanType } from '../types';

interface UploadZoneProps {
  onAnalyze: (file: File) => void;
  isLoading: boolean;
  scanType: ScanType;
}

const formatSize = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function UploadZone({ onAnalyze, isLoading, scanType }: UploadZoneProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => {
    if (preview?.startsWith('blob:')) URL.revokeObjectURL(preview);
  }, [preview]);

  const clearFile = () => {
    setFile(null);
    setPreview(null);
    setError('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const selectFile = useCallback((nextFile: File) => {
    const extension = nextFile.name.split('.').pop()?.toLowerCase();
    const supported = ['image/png', 'image/jpeg'].includes(nextFile.type) || extension === 'dcm';
    if (!supported) {
      setError('Choose a PNG, JPEG, or DICOM file.');
      return;
    }
    if (nextFile.size > 20 * 1024 * 1024) {
      setError('This file is larger than the 20 MB limit.');
      return;
    }

    setError('');
    setFile(nextFile);
    setPreview(nextFile.type.startsWith('image/') ? URL.createObjectURL(nextFile) : null);
  }, []);

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) selectFile(dropped);
  };

  return (
    <div className="upload-control">
      {!file ? (
        <div
          className={`drop-zone${dragging ? ' is-dragging' : ''}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click();
          }}
          onDrop={handleDrop}
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
        >
          <span className="upload-glyph" aria-hidden="true">
            <svg viewBox="0 0 32 32"><path d="M16 22V7m0 0-6 6m6-6 6 6M7 21v4h18v-4" /></svg>
          </span>
          <h3>{scanType === 'chest_xray' ? 'Upload one frontal chest X-ray' : 'Upload one brain MRI slice'}</h3>
          <p>Drag and drop, or <u>browse your files</u></p>
          <span className="file-formats">PNG · JPEG · DICOM &nbsp;/&nbsp; MAX 20 MB</span>
          <span className="file-formats">Screenshots, posters, report pages and collages are rejected</span>
        </div>
      ) : (
        <div className="selected-file">
          <div className={`selected-file__preview${preview ? '' : ' selected-file__preview--dicom'}`}>
            {preview ? <img src={preview} alt="Selected scan preview" /> : (
              <div><strong>DCM</strong><span>DICOM study</span></div>
            )}
          </div>
          <div className="selected-file__details">
            <div>
              <p className="eyebrow">Ready to process</p>
              <h3>{file.name}</h3>
              <span>{formatSize(file.size)} · {file.type || 'DICOM'}</span>
            </div>
            <button className="text-button" type="button" onClick={clearFile}>Remove</button>
          </div>
          <button
            className="button button--primary button--wide"
            type="button"
            onClick={() => onAnalyze(file)}
            disabled={isLoading}
          >
            <span>{isLoading ? 'Processing study…' : 'Process this study'}</span>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
          </button>
        </div>
      )}

      {error && <div className="form-error upload-error" role="alert">{error}</div>}
      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.dcm"
        hidden
        onChange={(event) => event.target.files?.[0] && selectFile(event.target.files[0])}
      />
    </div>
  );
}
