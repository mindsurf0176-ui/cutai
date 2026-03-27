import { useCallback, useRef, useState } from 'react';
import { Upload, Film, AlertCircle } from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';
import { useApp } from '../store';
import { uploadVideo, getVideoInfo, analyzeVideo } from '../api';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export default function DropZone() {
  const { state, dispatch } = useApp();
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.type.startsWith('video/')) {
        setUploadError('Please select a video file');
        return;
      }
      setSelectedFile(file);
      setUploadError(null);
      setUploading(true);
      dispatch({ type: 'SET_UPLOAD_PROGRESS', progress: 0 });

      try {
        const { video_id } = await uploadVideo(file, (progress) => {
          dispatch({ type: 'SET_UPLOAD_PROGRESS', progress });
        });

        const videoInfo = await getVideoInfo(video_id);
        dispatch({ type: 'SET_VIDEO', videoId: video_id, videoInfo });

        // Auto-start analysis
        const { job_id } = await analyzeVideo(video_id);
        dispatch({
          type: 'SET_ACTIVE_JOB',
          job: { job_id, type: 'analysis', status: 'running', progress: 0 },
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        setUploadError(msg);
        dispatch({ type: 'SET_ERROR', error: msg });
      } finally {
        setUploading(false);
      }
    },
    [dispatch]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleClick = () => inputRef.current?.click();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  if (!state.backendOnline) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-[var(--text-secondary)]">
        <AlertCircle size={48} className="text-[var(--warning)]" />
        <p className="text-lg font-medium">Backend is offline</p>
        <p className="text-sm">Start the CutAI server at port 18910 to continue</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          flex flex-col items-center justify-center w-full max-w-lg aspect-video
          rounded-2xl border-2 border-dashed cursor-pointer
          transition-all duration-200
          ${dragging
            ? 'border-[var(--accent)] bg-[var(--accent)]/10 scale-[1.02]'
            : 'border-[var(--bg-tertiary)] bg-[var(--bg-secondary)] hover:border-[var(--accent)]/50 hover:bg-[var(--bg-tertiary)]'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={handleInputChange}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-4 w-full px-12">
            <Film size={40} className="text-[var(--accent)] animate-pulse" />
            <p className="text-sm text-[var(--text-secondary)]">
              Uploading {selectedFile?.name}...
            </p>
            <Progress.Root
              className="relative w-full h-2 overflow-hidden rounded-full bg-[var(--bg-primary)]"
              value={state.uploadProgress}
            >
              <Progress.Indicator
                className="h-full bg-[var(--accent)] transition-[width] duration-300 ease-out rounded-full"
                style={{ width: `${state.uploadProgress}%` }}
              />
            </Progress.Root>
            <p className="text-xs text-[var(--text-secondary)]">{state.uploadProgress}%</p>
          </div>
        ) : selectedFile ? (
          <div className="flex flex-col items-center gap-3">
            <Film size={40} className="text-[var(--accent)]" />
            <p className="text-sm font-medium">{selectedFile.name}</p>
            <p className="text-xs text-[var(--text-secondary)]">
              {formatFileSize(selectedFile.size)}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Upload size={40} className="text-[var(--text-secondary)]" />
            <p className="text-sm font-medium">Drop your video here</p>
            <p className="text-xs text-[var(--text-secondary)]">or click to browse</p>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="flex items-center gap-2 text-sm text-[var(--error)]">
          <AlertCircle size={16} />
          <span>{uploadError}</span>
        </div>
      )}
    </div>
  );
}
