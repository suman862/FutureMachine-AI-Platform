
import { useEffect, useRef, useState } from 'react'

import {
  Activity, AudioLines, Bot, ChevronDown, CircleHelp,
  Camera, FileImage, ImagePlus, Menu, MessageSquare, Mic,
  MoreHorizontal, Paperclip, Plus, Send, Settings2,
  Sparkles, SquarePen, StopCircle, Trash2, X, Zap
} from 'lucide-react'

const MODES = [
  { id: 'text', label: 'Text', model: 'Qwen 2.5', icon: MessageSquare },
  { id: 'vision', label: 'Vision', model: 'SmolVLM', icon: FileImage },
  { id: 'audio', label: 'Audio', model: 'Whisper', icon: AudioLines },
]

const suggestions = [
  {
    icon: Sparkles,
    title: 'Explain a complex topic',
    text: 'Explain how transformer models work in simple terms.'
  },
  {
    icon: FileImage,
    title: 'Understand an image',
    text: 'Describe the objects and important details in this image.'
  },
  {
    icon: AudioLines,
    title: 'Transcribe audio',
    text: 'Upload an audio file to transcribe it.'
  },
  {
    icon: Zap,
    title: 'Explore AI engineering',
    text: 'How do I design a scalable multimodal AI system?'
  },
]

function App() {
  const [mode, setMode] = useState('text')
  const [visionModel, setVisionModel] = useState('smolvlm')
  const [messages, setMessages] = useState([])
  const [prompt, setPrompt] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [history, setHistory] = useState([])
  const [maxTokens, setMaxTokens] = useState(256)
  const [temperature, setTemperature] = useState(0.7)

  // Microphone recording state
  const [isRecording, setIsRecording] = useState(false)
  const [recordingError, setRecordingError] = useState('')
  const [recordedAudioUrl, setRecordedAudioUrl] = useState('')
  const [isCameraOpen, setIsCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')

  // Refs
  const fileRef = useRef(null)
  const videoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const bottomRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const streamRef = useRef(null)
  const recordedAudioUrlRef = useRef('')

  useEffect(() => {
    return () => {
      cameraStreamRef.current?.getTracks().forEach(track => track.stop())
    }
  }, [])

  const activeMode = MODES.find(item => item.id === mode) || MODES[0]

  // Revoke an existing audio preview URL safely.
  function clearRecordedAudio() {
    if (recordedAudioUrlRef.current) {
      URL.revokeObjectURL(recordedAudioUrlRef.current)
      recordedAudioUrlRef.current = ''
    }

    setRecordedAudioUrl('')
  }

  // Start microphone recording.
  async function startRecording() {
    if (loading || isRecording) return

    try {
      setRecordingError('')
      setFile(null)
      clearRecordedAudio()

      if (
        !navigator.mediaDevices?.getUserMedia ||
        !window.MediaRecorder
      ) {
        throw new Error(
          'Microphone recording is not supported by this browser.'
        )
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      })

      streamRef.current = stream
      audioChunksRef.current = []

      const supportedTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
      ]

      const mimeType = supportedTypes.find(type =>
        MediaRecorder.isTypeSupported(type)
      )

      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      )

      mediaRecorderRef.current = recorder

      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      recorder.onerror = () => {
        setRecordingError('An error occurred while recording audio.')

        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        setIsRecording(false)
      }

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })

        if (blob.size > 0) {
          let extension = 'webm'

          if (blob.type.includes('mp4')) {
            extension = 'm4a'
          } else if (blob.type.includes('ogg')) {
            extension = 'ogg'
          }

          const audioFile = new File(
            [blob],
            `recording-${Date.now()}.${extension}`,
            { type: blob.type }
          )

          setFile(audioFile)

          const previewUrl = URL.createObjectURL(blob)

          recordedAudioUrlRef.current = previewUrl
          setRecordedAudioUrl(previewUrl)
        } else {
          setRecordingError(
            'No audio was captured. Please try again.'
          )
        }

        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        setIsRecording(false)
      }

      recorder.start()
      setIsRecording(true)

    } catch (error) {
      streamRef.current?.getTracks().forEach(track => track.stop())
      streamRef.current = null
      setIsRecording(false)

      setRecordingError(
        error.message || 'Could not access your microphone.'
      )
    }
  }

  // Stop microphone recording.
  function stopRecording() {
    const recorder = mediaRecorderRef.current

    if (recorder && recorder.state === 'recording') {
      recorder.stop()
    }
  }

  // Clean up microphone and audio preview when the component unmounts.
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop()
      }

      streamRef.current?.getTracks().forEach(track => track.stop())

      if (recordedAudioUrlRef.current) {
        URL.revokeObjectURL(recordedAudioUrlRef.current)
        recordedAudioUrlRef.current = ''
      }
    }
  }, [])

  function newChat() {
    if (messages.length) {
      setHistory(prev => [
        {
          id: Date.now(),
          title: messages[0].content.slice(0, 34) || 'New conversation',
        },
        ...prev,
      ])
    }

    if (isRecording) {
      stopRecording()
    }

    setMessages([])
    setPrompt('')
    setFile(null)
    clearRecordedAudio()
    setRecordingError('')
    setMode('text')
  }

  async function sendMessage(text = prompt) {
    const cleanPrompt = text.trim()

    if (loading || isRecording) return

    if (mode === 'text' && !cleanPrompt) return

    if ((mode === 'vision' || mode === 'audio') && !file) return

    const selectedFile = file
    const selectedMode = mode
    const selectedVisionModel = visionModel

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content:
        cleanPrompt ||
        (selectedMode === 'vision'
          ? 'Please analyze this image.'
          : 'Please transcribe this audio.'),
      fileName: selectedFile?.name,
      fileType: selectedFile?.type,
      fileUrl:
        selectedFile && selectedMode === 'vision'
          ? URL.createObjectURL(selectedFile)
          : null,
      mode: selectedMode,
    }

    setMessages(prev => [...prev, userMessage])
    setPrompt('')
    setLoading(true)
    setFile(null)

    try {
      let response

      if (selectedMode === 'text') {
        response = await fetch('/api/v1/text', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            prompt: cleanPrompt,
            max_tokens: Number(maxTokens),
            temperature: Number(temperature),
          }),
        })
      } else {
        const formData = new FormData()

        formData.append('file', selectedFile)

        if (selectedMode === 'vision') {
          formData.append(
            'prompt',
            cleanPrompt || 'Describe this image in detail.'
          )
        }

        const endpoint= 
        selectedMode === 'vision' 
        ? selectedVisionModel === 'resnet50'
          ? 'resnet50'
          :'vision'
        : selectedMode

        response = await fetch(`/api/v1/${endpoint}`, {
          method: 'POST',
          body: formData,
      })
    }

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || data.error || JSON.stringify(data)
        )
      }

      let answer

      if (
         selectedMode === 'vision' &&
         selectedVisionModel === 'resnet50'
         ) {
        const predictions = data.predictions || []

       answer = predictions.length
         ? `Top 5 predictions:\n\n${predictions
        .map(
          (item, index) =>
            `${index + 1}. Class ID ${item.class_id} — ${
              (item.probability * 100).toFixed(2)
                  }%`
             )
           .join('\n')}`
       : 'ResNet50 returned no predictions.'
    } else {
       answer =
         data.text ||
           data.response ||
             'The model returned an empty response.'
}

      if (selectedMode === 'audio') {
        const probability = Number(data.language_probability)

        answer =
          `Language: ${data.language || 'Unknown'}` +
          `${
            Number.isFinite(probability)
              ? ` (${(probability * 100).toFixed(1)}% confidence)`
              : ''
          }` +
          `\n\nTranscription:\n${answer}`
      }

      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: answer,
          mode: selectedMode,
        },
      ])

    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content:
            `Request failed: ${error.message}. ` +
            'Please check that the Gateway and required model service are running.',
          error: true,
          mode: selectedMode,
        },
      ])

    } finally {
      setLoading(false)

      setTimeout(() => {
        bottomRef.current?.scrollIntoView({
          behavior: 'smooth',
        })
      }, 100)
    }
  }

  async function startCamera() {
    try {
      setCameraError('')

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera access is unavailable. Use localhost or HTTPS.')
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      })

      cameraStreamRef.current = stream
      setIsCameraOpen(true)

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.play().catch(() => {})
        }
      }, 100)
    } catch (error) {
      setCameraError(error.message || 'Unable to access the camera.')
    }
  }

  function stopCamera() {
    cameraStreamRef.current?.getTracks().forEach(track => track.stop())
    cameraStreamRef.current = null
    setIsCameraOpen(false)

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }

  function capturePhoto() {
    const video = videoRef.current

    if (!video || !video.videoWidth) {
      setCameraError('Camera is not ready. Please wait a moment.')
      return
    }

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const context = canvas.getContext('2d')
    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(blob => {
      if (!blob) {
        setCameraError('Could not capture the photo.')
        return
      }

      const photo = new File(
        [blob],
        `ishora-camera-${Date.now()}.jpg`,
        { type: 'image/jpeg' }
      )

      stopCamera()
      handleFile(photo)
    }, 'image/jpeg', 0.92)
  }

  function handleFile(selected) {
    if (!selected) return

    const limit = mode === 'vision' ? 10 : 25

    if (selected.size > limit * 1024 * 1024) {
      alert(`File exceeds the ${limit} MB limit.`)

      if (fileRef.current) {
        fileRef.current.value = ''
      }

      return
    }

    clearRecordedAudio()
    setRecordingError('')
    setFile(selected)
  }

  return (
    <div className="app-shell">

      {sidebarOpen && (
        <aside className="sidebar">
          <div className="sidebar-top">

            <div className="brand">
              <div className="brand-icon">
                <img src="/multimodal-logo.svg" alt="Multimodal logo" />
              </div>

              <span>
                Multimodal <b>Inference Platform</b>
              </span>

              <button
                className="icon-btn sidebar-collapse"
                onClick={() => setSidebarOpen(false)}
                title="Close sidebar"
              >
                <Menu size={18} />
              </button>
            </div>

            <button className="new-chat-btn" onClick={newChat}>
              <SquarePen size={17} />
              <span>New chat</span>
              <Plus size={16} className="new-plus" />
            </button>

            <div className="side-label">WORKSPACE</div>

            <div className="side-nav">
              {MODES.map(item => {
                const Icon = item.icon

                return (
                  <button
                    key={item.id}
                    className={`nav-item ${
                      mode === item.id ? 'selected' : ''
                    }`}
                    onClick={() => setMode(item.id)}
                  >
                    <Icon size={17} />
                    <span>{item.label}</span>
                    <span className="nav-model">{item.model}</span>
                  </button>
                )
              })}
            </div>

            <div className="history-heading">
              <span className="side-label">RECENT</span>
              <MoreHorizontal size={17} />
            </div>

            <div className="history-list">
              {history.length === 0 ? (
                <p className="empty-history">
                  Your conversations will appear here.
                </p>
              ) : (
                history.map(item => (
                  <button
                    className="history-item"
                    key={item.id}
                    onClick={() => {
                      setMessages([])
                      setPrompt(item.title)
                    }}
                  >
                    <MessageSquare size={15} />
                    <span>{item.title}</span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="sidebar-bottom">
            <div className="system-status">
              <span className="status-dot" />
              Services connected through Gateway
            </div>

            <button className="profile">
              <div className="avatar">I</div>

              <div className="profile-info">
                <b>ISHORA</b>
                <span>Inference workspace</span>
              </div>

              <Settings2 size={17} />
            </button>
          </div>
        </aside>
      )}

      <main className="main-panel">

        <header className="topbar">
          <div className="topbar-left">

            {!sidebarOpen && (
              <button
                className="icon-btn"
                onClick={() => setSidebarOpen(true)}
              >
                <Menu size={19} />
              </button>
            )}

            <div className="mobile-brand">
              <div className="brand-icon">
                <img src="/multimodal-logo.svg" alt="Multimodal logo" />
              </div>
              Multimodal Inference
            </div>

            <div className="mode-select">
              <button className="mode-button">
                {activeMode.label}
                <span className="model-muted">
                  · {activeMode.model}
                </span>
                <ChevronDown size={15} />
              </button>
            </div>
          </div>

          <div className="topbar-right">
            <span className="gateway-indicator">
              <span className="status-dot" />
              Gateway
            </span>

            <button className="icon-btn" title="Help">
              <CircleHelp size={18} />
            </button>
          </div>
        </header>

        <section className="chat-area">

          {messages.length === 0 ? (
            <div className="welcome">

              <div className="welcome-symbol">
                <Sparkles size={25} />
              </div>

              <div className="eyebrow">
                YOUR MULTIMODAL WORKSPACE
              </div>

              <h1>
                What can I help you <span>build?</span>
              </h1>

              <p className="welcome-subtitle">
                One interface. Multiple models. Explore text,
                vision and audio inference.
              </p>

              <div className="mode-cards">
                {MODES.map(item => {
                  const Icon = item.icon

                  return (
                    <button
                      key={item.id}
                      className={`mode-card ${
                        mode === item.id ? 'active' : ''
                      }`}
                      onClick={() => setMode(item.id)}
                    >
                      <div className="mode-card-icon">
                        <Icon size={19} />
                      </div>

                      <div>
                        <b>{item.label}</b>
                        <span>{item.model}</span>
                      </div>

                      <span className="card-arrow">↗</span>
                    </button>
                  )
                })}
              </div>

              <div className="suggestion-heading">
                GET STARTED
              </div>

              <div className="suggestions">
                {suggestions.map(item => {
                  const Icon = item.icon

                  return (
                    <button
                      key={item.title}
                      className="suggestion"
                      onClick={() => {
                        if (item.title === 'Understand an image') {
                          setMode('vision')
                        } else if (item.title === 'Transcribe audio') {
                          setMode('audio')
                        } else {
                          setMode('text')
                          setPrompt(item.text)
                        }
                      }}
                    >
                      <Icon size={17} />

                      <span>
                        <b>{item.title}</b>
                        <small>{item.text}</small>
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="messages">

              {messages.map(message => (
                <div
                  key={message.id}
                  className={`message-row ${message.role}`}
                >
                  <div className={`message-avatar ${message.role}`}>
                    {message.role === 'assistant' ? (
                      <Sparkles size={16} />
                    ) : (
                      'U'
                    )}
                  </div>

                  <div className="message-content">
                    <div className="message-author">
                      {message.role === 'assistant'
                        ? 'ISHORA'
                        : 'You'}
                      <span>{message.mode}</span>
                    </div>

                    {message.fileUrl && (
                      <img
                        className="message-image"
                        src={message.fileUrl}
                        alt="Uploaded"
                      />
                    )}

                    {message.fileName && !message.fileUrl && (
                      <div className="file-chip">
                        <AudioLines size={15} />
                        {message.fileName}
                      </div>
                    )}

                    <div
                      className={`message-text ${
                        message.error ? 'error-text' : ''
                      }`}
                    >
                      {message.content}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="message-row assistant">
                  <div className="message-avatar assistant">
                    <Sparkles size={16} />
                  </div>

                  <div className="message-content">
                    <div className="message-author">
                      ISHORA
                      <span>{activeMode.model}</span>
                    </div>

                    <div className="typing">
                      <i />
                      <i />
                      <i />
                      <span>Generating response...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </section>

        <footer className="composer-section">

          {mode === 'text' && (
            <div className="generation-settings">
              <label>
                Max tokens
                <select
                  value={maxTokens}
                  onChange={e => setMaxTokens(e.target.value)}
                >
                  <option value="128">128</option>
                  <option value="256">256</option>
                  <option value="512">512</option>
                </select>
              </label>

              <label>
                Temperature
                <select
                  value={temperature}
                  onChange={e => setTemperature(e.target.value)}
                >
                  <option value="0.2">0.2</option>
                  <option value="0.5">0.5</option>
                  <option value="0.7">0.7</option>
                  <option value="1">1.0</option>
                </select>
              </label>
            </div>
          )}
          {/* Audio recording feedback */}
          {mode === 'audio' && (isRecording || recordingError || recordedAudioUrl) && (
            <div className="mb-3 flex flex-wrap items-center gap-3">
              {isRecording && (
                <span className="text-sm text-red-300">● Recording...</span>
              )}
              {recordingError && (
                <span role="alert" className="text-sm text-red-300">
                  {recordingError}
                </span>
              )}
              {recordedAudioUrl && (
                <audio controls src={recordedAudioUrl} className="h-10 max-w-full" />
              )}
            </div>
          )}


          {file && (
            <div className="attachment-preview">
              <div className="attachment-icon">
                {mode === 'vision' ? (
                  <ImagePlus size={17} />
                ) : (
                  <Mic size={17} />
                )}
              </div>

              <span>{file.name}</span>

              <button
                className="icon-btn"
                onClick={() => {
                  setFile(null)
                  clearRecordedAudio()

                  if (fileRef.current) {
                    fileRef.current.value = ''
                  }
                }}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {mode === 'vision' && isCameraOpen && (
            <div className="webcam-panel">
              <video
                ref={videoRef}
                className="webcam-preview"
                autoPlay
                muted
                playsInline
              />
              <div className="webcam-actions">
                <button type="button" onClick={capturePhoto}>
                  <Camera size={16} />
                  Capture Photo
                </button>
                <button type="button" onClick={stopCamera}>
                  <X size={16} />
                  Close Camera
                </button>
              </div>
            </div>
          )}

          {mode === 'vision' && cameraError && (
            <p className="camera-error" role="alert">{cameraError}</p>
          )}

          <div className="composer">

            <input
              ref={fileRef}
              type="file"
              hidden
              accept={
                mode === 'vision'
                  ? 'image/*'
                  : 'audio/*'
              }
              onChange={e => handleFile(e.target.files?.[0])}
            />

            <button
              className="attach-btn"
              onClick={() => fileRef.current?.click()}
              title={
                mode === 'vision'
                  ? 'Attach image'
                  : mode === 'audio'
                    ? 'Upload audio'
                    : 'Choose a mode to upload files'
              }
            >
              <Paperclip size={19} />
            </button>

            {mode === 'audio' && (
              <button
                type="button"
                className={`attach-btn ${isRecording ? 'text-red-400' : ''}`}
                onClick={isRecording ? stopRecording : startRecording}
                title={isRecording ? 'Stop recording' : 'Record audio'}
                aria-label={isRecording ? 'Stop recording' : 'Record audio'}
                disabled={loading}
              >
                {isRecording ? <StopCircle size={19} /> : <Mic size={19} />}
              </button>
            )}

            {mode === 'vision' && (
              <button
                type="button"
                className="attach-btn camera-btn"
                onClick={startCamera}
                title="Take a photo"
                disabled={loading}
              >
                <Camera size={19} />
              </button>
            )}

            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
              placeholder={
                mode === 'text'
                  ? 'Message ISHORA...'
                  : mode === 'vision'
                    ? 'Ask something about your image...'
                    : 'Optional instructions for audio...'
              }
              rows={1}
            />

            <button
              className={`send-btn ${
                mode === 'vision' ? 'vision-send-btn' : ''
              } ${
                loading ||
                isRecording ||
                (mode !== 'text' && !file) ||
                (mode === 'text' && !prompt.trim())
                  ? 'disabled'
                  : ''
              }`}
              disabled={
                loading ||
                isRecording ||
                (mode !== 'text' && !file) ||
                (mode === 'text' && !prompt.trim())
              }
              onClick={() => sendMessage()}
            >
              {mode === 'vision' ? (
                <>
                  <ImagePlus size={16} />
                  <span>Analyze Image</span>
                </>
              ) : (
                <Send size={17} />
              )}
            </button>
          </div>

          <div className="composer-hint">
            <span>
              {mode === 'vision'
                ? 'Image uploads · Maximum 10 MB'
                : mode === 'audio'
                  ? 'Record or upload audio · Maximum 25 MB'
                  : 'Qwen 2.5 · Adjust generation settings above'}
            </span>

            <span>
              Enter to send · Shift + Enter for new line
            </span>
          </div>

          <div className="footer-note">
            ISHORA · Intelligence Across Modalities.
          </div>
        </footer>
      </main>
    </div>
  )
}

export default App
