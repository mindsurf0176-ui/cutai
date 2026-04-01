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

        // Auanalysis
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

  // Backend check removed - show upload UI always

  return (
    <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          flex flex-col items-center justify-center w-full h-full cursor-pointer
          transition-all duration-300 ease-out group
          ${dragging
            ? 'bg-violet-500/5'
            : ''
          }
        `}
      >
      <div className={`flex flex-col items-center justify-center px-16 py-14 rounded-3xl border border-dashed transition-all duration-300 ${dragging ? 'border-violet-500/60 scale-[1.02]' : 'border-white/[0.07] group-hover:border-white/15'}`}>
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={handleInputChange}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-4 w-full px-12">
            <Film size={40} className="text-[#ffffff] animate-pulse" />
            <p className="text-sm text-[#a1a1aa]">
              Uploading {selectedFile?.name}...
            </p>
            <Progress.Root
              className="relative w-full h-2 overflow-hidden rounded-md bg-[#000000]"
              value={state.uploadProgress}
            >
              <Progress.Indicator
                className="h-full bg-[#ffffff] transition-[width] duration-300 ease-out rounded-md"
                style={{ width: `${state.uploadProgress}%` }}
              />
            </Progress.Root>
            <p className="text-xs text-[#a1a1aa]">{state.uploadProgress}%</p>
          </div>
        ) : selectedFile ? (
          <div className="flex flex-col items-center gap-3">
            <Film size={40} className="text-[#ffffff]" />
            <p className="text-sm font-medium">{selectedFile.name}</p>
            <p className="text-xs text-[#a1a1aa]">
              {formatFileSize(selectedFile.size)}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-5">
            <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-violet-500/10 group-hover:border-violet-500/30 transition-all duration-300">
              <Upload size={24} className="text-white/30 group-hover:text-violet-400 transition-colors duration-300" />
            </div>
            <div className="text-center">
              <p className="text-[15px] font-semibold text-white/70">Drop video here</p>
              <p className="text-[13px] text-white/30 mt-1">or click to browse</p>
            </div>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="flex items-center gap-2 text-sm text-red-500 mt-4">
          <AlertCircle size={16} />
          <span>{uploadError}</span>
        </div>
      )}
      </div>
  );
}
