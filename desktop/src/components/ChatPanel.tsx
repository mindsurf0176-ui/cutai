import { useState, useRef, useEffect } from 'react';
import { Send, Upload, Sparkles, Scissors, Subtitles, Clapperboard, Wand2, RefreshCw } from 'lucide-react';
import { useApp } from '../store';
import { createPlan, uploadVideo, getVideoInfo, analyzeVideo } from '../api';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

const SUGGESTIONS = [
  { icon: Scissors, text: 'Remove all silent parts' },
  { icon: Subtitles, text: 'Add subtitles' },
  { icon: Clapperboard, text: 'Make it cinematic' },
  { icon: Wand2, text: 'Speed up boring parts' },
];

interface ChatPanelProps {
  onRetryBackend: () => void;
  retryingBackend: boolean;
}

export default function ChatPanel({ onRetryBackend, retryingBackend }: ChatPanelProps) {
  const { state, dispatch } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = (role: ChatMessage['role'], content: string) => {
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role, content, timestamp: new Date() }]);
  };

  const handleUpload = async (file: File) => {
    if (!file.type.startsWith('video/')) {
      addMessage('system', 'Please select a video file.');
      return;
    }
    addMessage('system', `Uploading ${file.name}...`);
    dispatch({ type: 'SET_UPLOAD_PROGRESS', progress: 0 });
    try {
      const { video_id } = await uploadVideo(file, (progress) => {
        dispatch({ type: 'SET_UPLOAD_PROGRESS', progress });
      });
      const videoInfo = await getVideoInfo(video_id);
      dispatch({ type: 'SET_VIDEO', videoId: video_id, videoInfo });
      addMessage('assistant', `✅ **${file.name}** loaded (${Math.round(videoInfo.duration)}s, ${videoInfo.width}×${videoInfo.height}). What would you like to do with it?`);
      const { job_id } = await analyzeVideo(video_id);
      dispatch({ type: 'SET_ACTIVE_JOB', job: { job_id, type: 'analysis', status: 'running', progress: 0 } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      addMessage('system', `❌ ${msg}`);
      dispatch({ type: 'SET_ERROR', error: msg });
    }
  };

  const handleSend = async (text?: string) => {
    const instruction = text || input;
    if (!instruction.trim()) return;
    if (!text) setInput('');

    addMessage('user', instruction);

    if (!state.videoId) {
      addMessage('assistant', 'Drop a video first, then I can edit it for you.');
      return;
    }

    setLoading(true);
    try {
      const plan = await createPlan(state.videoId, instruction, state.editPlan ?? undefined, state.planningStylePreset?.id);
      dispatch({ type: 'SET_EDIT_PLAN', plan });
      dispatch({ type: 'SET_VIEW', view: 'editor' });

      const opSummary = plan.operations.map((op: { type: string; description?: string }) => `• ${op.type}: ${op.description || ''}`).join('\n');
      addMessage('assistant', `Here's my plan:\n\n${opSummary}\n\nLook good? I can refine it or you can preview.`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create plan';
      addMessage('assistant', `Sorry, something went wrong: ${msg}`);
      dispatch({ type: 'SET_ERROR', error: msg });
    } finally {
      setLoading(false);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="w-[420px] flex flex-col bg-bg-panel border-r border-border flex-shrink-0 h-full">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-5 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="CutAI" className="w-7 h-7 rounded-lg" />
          <span className="text-sm font-bold text-text-primary tracking-tight">CutAI</span>
        </div>
        {state.backendStatus !== 'online' && (
          <button onClick={onRetryBackend} disabled={retryingBackend} className="flex items-center gap-1.5 text-[11px] text-warning font-medium hover:text-text-primary transition-colors">
            <RefreshCw size={11} className={retryingBackend ? 'animate-spin' : ''} />
            {retryingBackend ? 'Connecting...' : 'Offline'}
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center">
              <h2 className="text-lg font-bold text-text-primary mb-2">What do you want to edit?</h2>
              <p className="text-sm text-text-secondary leading-relaxed">
                Drop a video and tell me what to do.<br />
                I'll handle the rest.
              </p>
            </div>

            {/* Upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent text-white font-semibold text-sm hover:bg-accent-hover transition-colors"
            >
              <Upload size={16} />
              Import Video
            </button>

            {/* Suggestions */}
            <div className="w-full space-y-2 mt-2">
              <p className="text-[11px] text-text-muted font-medium uppercase tracking-wider px-1">Try saying</p>
              {SUGGESTIONS.map(({ icon: Icon, text }) => (
                <button
                  key={text}
                  onClick={() => handleSend(text)}
                  disabled={!state.videoId}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-bg-surface border border-border text-sm text-text-secondary hover:text-text-primary hover:border-border-strong transition-all text-left disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Icon size={14} className="text-accent flex-shrink-0" />
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-4 py-2.5 rounded-lg text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-accent text-white rounded-br-sm'
                    : msg.role === 'system'
                    ? 'bg-bg-surface text-text-muted text-xs border border-border'
                    : 'bg-bg-surface text-text-primary border border-border rounded-bl-sm'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="px-4 py-3 rounded-lg bg-bg-surface border border-border">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-border flex-shrink-0">
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-10 h-10 flex items-center justify-center rounded-lg text-text-muted hover:text-text-secondary hover:bg-bg-surface transition-colors flex-shrink-0"
            title="Import video"
          >
            <Upload size={18} />
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={state.videoId ? 'Tell me what to edit...' : 'Import a video first...'}
            className="flex-1 h-10 px-4 rounded-lg bg-bg-surface border border-border text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="w-10 h-10 flex items-center justify-center rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </form>
      </div>

      <input ref={fileInputRef} type="file" accept="video/*" className="hidden" onChange={(e) => {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
      }} />
    </div>
  );
}
