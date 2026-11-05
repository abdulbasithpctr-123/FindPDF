import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useRef, useState } from 'react'
import { askQuestion, deleteDocument, uploadPDFs } from './api'
import './App.css'

// Clean up escaped Markdown characters returned by the AI.
function normalizeMarkdown(value = '') {
  return value
    .replace(/\\([\\`*_{}\[\]()#+\-.!>])/g, '$1')
    .replace(/&#x65;/g, 'e')
}

function App() {
  const [files, setFiles] = useState([])
  const [message, setMessage] = useState('')
  const [activePage, setActivePage] = useState('Home')
  const [chats, setChats] = useState([])
  const [activeChat, setActiveChat] = useState(null)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [previewSource, setPreviewSource] = useState(null)
  const fileInputRef = useRef(null)
  const messageInputRef = useRef(null)

  
const selectFiles = async (selectedFiles) => {
  const pdfs = Array.from(selectedFiles || []).filter(
    (file) =>
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf")
  );

  if (!pdfs.length) {
    setStatusMessage("Please choose one or more PDF files.");
    return;
  }

  const existingNames = new Set(
    files.map((file) => file.name?.toLowerCase())
  );

  const newPdfs = pdfs.filter(
    (file) => !existingNames.has(file.name.toLowerCase())
  );

  if (!newPdfs.length) {
    setStatusMessage("Those PDFs are already in your workspace.");
    return;
  }

  setIsUploading(true);
  setStatusMessage("Uploading and processing PDFs...");

  try {
    const result = await uploadPDFs(newPdfs);

    if (!result.documents || !result.documents.length) {
      throw new Error("The backend did not return processed documents.");
    }

    const uploadedDocuments = result.documents.map(
      (document, index) => {
        const returnedName =
          document.name ||
          document.filename ||
          document.file_name ||
          document.original_filename ||
          document.original_name ||
          "";

        const normalizedName = String(returnedName)
          .replace(/\\/g, "/")
          .split("/")
          .pop()
          .toLowerCase();

        const originalFile =
          newPdfs.find(
            (pdf) => pdf.name.toLowerCase() === normalizedName
          ) || newPdfs[index];

        return {
          ...document,
          name: returnedName || originalFile?.name || "Uploaded PDF",
          originalFile,
          localUrl: originalFile
            ? URL.createObjectURL(originalFile)
            : null,
        };
      }
    );

    setFiles((previous) => {
      const existingIds = new Set(
        previous.map((file) => file.id)
      );

      return [
        ...previous,
        ...uploadedDocuments.filter(
          (file) => !existingIds.has(file.id)
        ),
      ];
    });

    setStatusMessage("PDFs uploaded successfully.");
    setActivePage("Documents");
  } catch (error) {
    setStatusMessage(`Upload failed: ${error.message}`);
  } finally {
    setIsUploading(false);
  }
};


  const createChat = () => {
    const chat = {
      id: Date.now(),
      title: 'New conversation',
      messages: [],
    }

    setChats((previous) => [chat, ...previous])
    setActiveChat(chat.id)
    setActivePage('Chat')
  }

  const sendMessage = async (event) => {
    event.preventDefault()

    const text = message.trim()
    if (!text || isSending) return

    if (!files.length) {
      setStatusMessage('Upload at least one PDF before asking a question.')
      return
    }

    let chatId = activeChat

    if (!chatId) {
      chatId = Date.now()

      setChats((previous) => [
        {
          id: chatId,
          title: text.slice(0, 35),
          messages: [{ role: 'user', text }],
        },
        ...previous,
      ])

      setActiveChat(chatId)
    } else {
      setChats((previous) =>
        previous.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                title:
                  chat.title === 'New conversation'
                    ? text.slice(0, 35)
                    : chat.title,
                messages: [...chat.messages, { role: 'user', text }],
              }
            : chat
        )
      )
    }

    setMessage('')
    setActivePage('Chat')
    setIsSending(true)
    setStatusMessage('Searching your PDFs and preparing an answer…')

    try {
      const result = await askQuestion(
        text,
        files.map((file) => file.id)
      )

      setChats((previous) =>
        previous.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                messages: [
                  ...chat.messages,
                  {
                    role: 'assistant',
                    text: result.answer,
                    sources: result.sources || [],
                  },
                ],
              }
            : chat
        )
      )

      setStatusMessage('Answer ready.')
    } catch (error) {
      setChats((previous) =>
        previous.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                messages: [
                  ...chat.messages,
                  {
                    role: 'assistant',
                    text: `I couldn't get an answer: ${error.message}`,
                  },
                ],
              }
            : chat
        )
      )

      setStatusMessage(`Question failed: ${error.message}`)
    } finally {
      setIsSending(false)
    }
  }

  const removeFile = async (index) => {
    const file = files[index]
    if (!file) return

    try {
      await deleteDocument(file.id)
      if (file.localUrl) URL.revokeObjectURL(file.localUrl)
      setFiles((previous) => previous.filter((item) => item.id !== file.id))
      if (previewSource?.document === file.name) setPreviewSource(null)
      setStatusMessage(`Removed ${file.name} from your workspace.`)
    } catch (error) {
      setStatusMessage(`Couldn't remove ${file.name}: ${error.message}`)
    }
  }

  
const openSource = (source) => {
  const getFileName = (value) =>
    String(value || "")
      .replace(/\\/g, "/")
      .split("/")
      .pop()
      .trim()
      .toLowerCase();

  const sourceName = getFileName(
    source.document ||
    source.filename ||
    source.file_name ||
    source.original_filename
  );

  const matchingFile = files.find((file) => {
    const uploadedName = getFileName(file.name);
    const originalName = getFileName(file.originalFile?.name);

    return (
      sourceName &&
      (sourceName === uploadedName ||
        sourceName === originalName)
    );
  });

  if (!matchingFile) {
    setStatusMessage(
      "Could not match this citation to an uploaded PDF. Upload the document again."
    );
    console.error("Citation matching failed:", {
      source,
      uploadedFiles: files,
    });
    return;
  }

  if (!matchingFile.localUrl) {
    setStatusMessage(
      "The original PDF is not available in this browser session."
    );
    console.error("Missing PDF URL:", matchingFile);
    return;
  }

  setPreviewSource({
    ...source,
    localUrl: matchingFile.localUrl,
  });
};



  const formatSize = (bytes) => {
    if (typeof bytes !== 'number' || !Number.isFinite(bytes)) {
      return 'Processed PDF'
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(0)} KB`
    }

    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }

  const navItems = [
    { name: 'Home', icon: '⌂' },
    { name: 'Documents', icon: '▤' },
    { name: 'Chat History', icon: '◷' },
    { name: 'Compare PDFs', icon: '⇄' },
  ]

  const activeConversation = chats.find(
    (chat) => chat.id === activeChat
  )

  return (
    <div className="app-shell">
      {mobileMenu && (
        <button
          className="mobile-overlay"
          aria-label="Close menu"
          onClick={() => setMobileMenu(false)}
        />
      )}

      <aside className={`sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
        <button
          className="mobile-close"
          aria-label="Close menu"
          onClick={() => setMobileMenu(false)}
        >
          ×
        </button>

        <a
          className="brand"
          href="#home"
          onClick={() => setActivePage('Home')}
        >
          <span className="brand-icon">
            <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <path
                d="M5 7.5 13 4l6 3.5 8-3v20l-8 3-6-3.5-8 3v-20Z"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path
                d="M13 4v20m6-16v19"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="m9 13 2 2 4-5m3 9 2 2 4-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="brand-name">
            Find<span>PDF</span>
          </span>
        </a>

        <p className="brand-tagline">Chat · Compare · Understand</p>

        <button className="new-chat" onClick={createChat}>
          <span className="new-chat-plus">＋</span>
          New conversation
          <span className="new-chat-shortcut">⌘ K</span>
        </button>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="navigation">
          {navItems.map((item) => (
            <button
              key={item.name}
              className={`nav-item ${
                activePage === item.name ? 'nav-active' : ''
              }`}
              onClick={() => {
                setActivePage(item.name)
                setMobileMenu(false)

                if (item.name === 'Chat History' && chats.length) {
                  setActiveChat(chats[0].id)
                }
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.name}</span>

              {item.name === 'Documents' && files.length > 0 && (
                <span className="nav-count">{files.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-label document-heading">
          <span>MY DOCUMENTS</span>
          <button
            className="tiny-add"
            aria-label="Add PDF"
            onClick={() => fileInputRef.current?.click()}
          >
            +
          </button>
        </div>

        <input
          ref={fileInputRef}
          className="hidden-input"
          type="file"
          accept=".pdf,application/pdf"
          multiple
          onChange={(event) => {
            selectFiles(event.target.files)
            event.target.value = ''
          }}
        />

        <div className="sidebar-documents">
          {files.length === 0 ? (
            <button
              className="sidebar-empty"
              onClick={() => fileInputRef.current?.click()}
            >
              <span className="empty-file-icon">＋</span>
              <span>
                <strong>Add your first PDF</strong>
                <small>Your files will appear here</small>
              </span>
            </button>
          ) : (
            files.map((file, index) => (
              <div
                className="sidebar-document"
                key={file.id || `${file.name}-${index}`}
              >
                <span className="pdf-icon">PDF</span>

                <button
                  className="sidebar-file-name"
                  title={file.name}
                  onClick={() => setActivePage('Documents')}
                >
                  {file.name}
                </button>

                <button
                  className="remove-file"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => removeFile(index)}
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-label history-heading">RECENT CHATS</div>

        <div className="sidebar-history">
          {chats.length === 0 ? (
            <p className="history-empty">
              Your conversations will appear here.
            </p>
          ) : (
            chats.slice(0, 5).map((chat) => (
              <button
                key={chat.id}
                className={`history-item ${
                  activeChat === chat.id ? 'history-selected' : ''
                }`}
                onClick={() => {
                  setActiveChat(chat.id)
                  setActivePage('Chat')
                }}
              >
                <span>◌</span>
                <span className="history-title">{chat.title}</span>
              </button>
            ))
          )}
        </div>

        <div className="sidebar-storage">
          <div className="storage-label">
            <span>Workspace storage</span>
            <span>{files.length} PDFs</span>
          </div>
          <div className="storage-track">
            <div
              style={{
                width: `${Math.min(files.length * 5, 100)}%`,
              }}
            />
          </div>
          <small>Files selected in this session</small>
        </div>

        <div className="sidebar-profile">
          <div className="profile-avatar">F</div>
          <div className="profile-info">
            <strong>FindPDF Workspace</strong>
            <span>Personal workspace</span>
          </div>
          <span className="online-dot" />
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu-button"
              aria-label="Open menu"
              onClick={() => setMobileMenu(true)}
            >
              ☰
            </button>
            <div className="breadcrumb">
              Workspace <span>/</span> <strong>{activePage}</strong>
            </div>
          </div>

          <button
            className="global-search"
            onClick={() => {
              setActivePage('Chat')
              messageInputRef.current?.focus()
            }}
          >
            <span>⌕</span>
            <span>Ask anything about your documents...</span>
            <kbd>Ctrl K</kbd>
          </button>

          <div className="topbar-right">
            <span className="live-indicator" />
            <span className="preview-label">Local preview</span>
            <div className="top-avatar">F</div>
          </div>
        </header>

        <div className="ambient-orb orb-one" />
        <div className="ambient-orb orb-two" />

        <section className="content" key={activePage}>
          {statusMessage && (
            <div
              className="notice-card"
              role="status"
              style={{ marginBottom: '18px' }}
            >
              <span>{isUploading || isSending ? '◌' : 'ⓘ'}</span>
              <span>{statusMessage}</span>
              <button
                onClick={() => setStatusMessage('')}
                aria-label="Dismiss message"
              >
                ×
              </button>
            </div>
          )}
                    {activePage === 'Home' && (
            <>
              <div className="hero">
                <div className="hero-copy">
                  <div className="welcome-badge">
                    <span className="badge-sparkle">✳</span>
                    YOUR DOCUMENT AI WORKSPACE
                  </div>

                  <h1>
                    Turn your PDFs
                    <br />
                    into <span className="gradient-text">real answers.</span>
                  </h1>

                  <p className="hero-subtitle">
                    Bring your documents together. Ask questions, explore ideas,
                    and discover insights across your PDFs.
                  </p>

                  <div className="hero-actions">
                    <button
                      className="primary-button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                    >
                      <span>↑</span>{' '}
                      {isUploading ? 'Uploading…' : 'Upload PDFs'}{' '}
                      <span className="button-arrow">↗</span>
                    </button>

                    <button
                      className="secondary-button"
                      onClick={() => {
                        setActivePage('Documents')
                        if (!files.length) fileInputRef.current?.click()
                      }}
                    >
                      <span className="play-icon">▷</span> Explore workspace
                    </button>
                  </div>

                  <div className="hero-trust">
                    <div className="trust-item">
                      <span className="trust-icon trust-teal">✓</span>
                      <span>
                        <strong>Source-aware</strong>
                        <small>Grounded in documents</small>
                      </span>
                    </div>

                    <div className="trust-item">
                      <span className="trust-icon trust-purple">⇄</span>
                      <span>
                        <strong>Cross-document</strong>
                        <small>Compare information</small>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="hero-art" aria-hidden="true">
                  <div className="art-glow" />
                  <div className="art-orbit orbit-a" />
                  <div className="art-orbit orbit-b" />
                  <div className="floating-chip chip-top">✦ AI insights</div>
                  <div className="floating-chip chip-bottom">
                    ✓ Source matched
                  </div>

                  <div className="floating-document document-back">
                    <div className="document-top">
                      <span>PDF</span>
                      <i />
                    </div>
                    <div className="document-lines">
                      <i /><i /><i /><i />
                    </div>
                  </div>

                  <div className="floating-document document-middle">
                    <div className="document-top">
                      <span>PDF</span>
                      <i />
                    </div>
                    <div className="document-lines">
                      <i /><i /><i /><i /><i />
                    </div>
                  </div>

                  <div className="floating-document document-front">
                    <div className="document-symbol">✧</div>
                    <div className="document-top">
                      <span>YOUR FILE</span>
                      <i />
                    </div>
                    <div className="document-lines">
                      <i /><i /><i /><i />
                    </div>
                    <div className="document-ai-tag">AI READY</div>
                  </div>

                  <div className="art-spark spark-a">✦</div>
                  <div className="art-spark spark-b">✧</div>
                  <div className="art-spark spark-c">·</div>
                </div>
              </div>

              <div className="feature-grid">
                <button
                  className="feature-card"
                  onClick={() => setActivePage('Chat')}
                >
                  <div className="feature-icon feature-purple">▤</div>
                  <div className="feature-card-content">
                    <h3>Chat with PDFs</h3>
                    <p>Ask natural questions about your documents.</p>
                  </div>
                  <span className="feature-arrow">↗</span>
                </button>

                <button
                  className="feature-card"
                  onClick={() => setActivePage('Compare PDFs')}
                >
                  <div className="feature-icon feature-teal">⇄</div>
                  <div className="feature-card-content">
                    <h3>Compare documents</h3>
                    <p>Explore similarities and differences across files.</p>
                  </div>
                  <span className="feature-arrow">↗</span>
                </button>

                <button
                  className="feature-card"
                  onClick={() => setActivePage('Documents')}
                >
                  <div className="feature-icon feature-amber">✧</div>
                  <div className="feature-card-content">
                    <h3>Find key insights</h3>
                    <p>Keep important information close at hand.</p>
                  </div>
                  <span className="feature-arrow">↗</span>
                </button>

                <button
                  className="feature-card"
                  onClick={() => setActivePage('Chat')}
                >
                  <div className="feature-icon feature-blue">⌕</div>
                  <div className="feature-card-content">
                    <h3>Search & discover</h3>
                    <p>Find the information you're looking for.</p>
                  </div>
                  <span className="feature-arrow">↗</span>
                </button>
              </div>

              <div className="workspace-grid">
                <div className="upload-panel panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Bring your documents</h2>
                      <p>Start by adding one or more PDF files.</p>
                    </div>
                    <span className="panel-heading-icon">↥</span>
                  </div>

                  <label
                    className="large-drop-zone"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault()
                      selectFiles(event.dataTransfer.files)
                    }}
                  >
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      multiple
                      onChange={(event) => {
                        selectFiles(event.target.files)
                        event.target.value = ''
                      }}
                      hidden
                    />

                    <div className="cloud-icon">
                      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
                        <path
                          d="M13 35h22a9 9 0 0 0 1-18 13 13 0 0 0-25-2A10 10 0 0 0 13 35Z"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M24 33V22m0 0-5 5m5-5 5 5"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>

                    <h3>Drop your PDFs here</h3>
                    <p>
                      or <span>browse files</span> from your computer
                    </p>

                    <div className="upload-tags">
                      <span>▤ Multiple PDFs</span>
                      <span>◇ PDF files only</span>
                      <span>✓ Local selection</span>
                    </div>
                  </label>

                  {files.length > 0 && (
                    <div className="upload-summary">
                      <span className="summary-check">✓</span>
                      <span>
                        <strong>
                          {files.length} PDF
                          {files.length !== 1 ? 's' : ''} processed
                        </strong>
                        <small>Ready for the next step</small>
                      </span>
                      <button onClick={() => setActivePage('Documents')}>
                        View files →
                      </button>
                    </div>
                  )}
                </div>

                <div className="activity-panel panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Your workspace</h2>
                      <p>A quick overview of this session.</p>
                    </div>
                    <span className="activity-count">{files.length}</span>
                  </div>

                  <div className="stat-row">
                    <span className="stat-icon stat-teal">▤</span>
                    <div className="stat-copy">
                      <strong>PDF documents</strong>
                      <small>Processed in this session</small>
                    </div>
                    <strong className="stat-number">{files.length}</strong>
                  </div>

                  <div className="stat-row">
                    <span className="stat-icon stat-purple">◌</span>
                    <div className="stat-copy">
                      <strong>Conversations</strong>
                      <small>Your recent chats</small>
                    </div>
                    <strong className="stat-number">{chats.length}</strong>
                  </div>

                  <div className="activity-footer">
                    <span className="live-indicator" />
                    Your workspace is ready
                  </div>
                </div>
              </div>
            </>
          )}

          {activePage === 'Documents' && (
            <div className="page-view">
              <div className="page-title-row">
                <div>
                  <div className="eyebrow">YOUR WORKSPACE</div>
                  <h1 className="page-title">
                    Your <span className="gradient-text">documents.</span>
                  </h1>
                  <p className="page-description">
                    Manage the PDF files processed by FindPDF.
                  </p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  ＋ Add PDFs
                </button>
              </div>

              <div className="document-toolbar">
                <span>
                  ▤ {files.length} document
                  {files.length !== 1 ? 's' : ''}
                </span>
                <span className="toolbar-note">
                  PDF files · Current session
                </span>
              </div>

              {files.length === 0 ? (
                <div className="empty-state panel">
                  <div className="empty-state-icon">▤</div>
                  <h2>Your library starts here</h2>
                  <p>Add PDF files to see them in your document library.</p>
                  <button
                    className="primary-button"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    ↑ Choose PDF files
                  </button>
                </div>
              ) : (
                <div className="documents-grid">
                  {files.map((file, index) => (
                    <div
                      className="document-card panel"
                      key={file.id || `${file.name}-${index}`}
                    >
                      <div className="document-card-top">
                        <span className="pdf-icon large-pdf">PDF</span>
                        <button
                          className="remove-file"
                          onClick={() => removeFile(index)}
                          aria-label={`Remove ${file.name}`}
                        >
                          ×
                        </button>
                      </div>

                      <h3 title={file.name}>{file.name}</h3>
                      <p>
                        {formatSize(file.size)} · {file.pages ?? '—'} pages
                      </p>

                      <div className="document-card-footer">
                        <span className="document-local-dot" />
                        Processed by FindPDF
                      </div>

                      <button
                        className="document-action"
                        onClick={() => {
                          setActivePage('Chat')
                          setMessage(`Summarize ${file.name}`)
                        }}
                      >
                        Ask about this PDF <span>→</span>
                      </button>
                    </div>
                  ))}
                
                </div>
              )}

              {files.length > 0 && (
                <div className="ask-all-pdfs">
                  <div className="ask-all-pdfs-text">
                    <h3>Ready to explore your documents?</h3>
                    <p>
                      Ask questions and get answers from all your uploaded PDFs.
                    </p>
                  </div>

                  <button
                    className="ask-all-pdfs-button"
                    onClick={() => {
                      setMessage('')
                      setActivePage('Chat')
                    }}
                  >
                    ✦ Ask from These PDFs <span>→</span>
                  </button>
                </div>
              )}
            </div>
          )}

                    {activePage === 'Chat' && (
            <div className="page-view chat-page">
              <div className="eyebrow">DOCUMENT ASSISTANT</div>

              <h1 className="page-title">
                Let's find <span className="gradient-text">answers.</span>
              </h1>

              <p className="page-description">
                Ask questions and get answers from your uploaded PDFs.
              </p>

              {files.length === 0 && (
                <div className="notice-card">
                  <span>ⓘ</span>
                  Add PDF files before asking a question.
                  <button onClick={() => fileInputRef.current?.click()}>
                    Add PDFs
                  </button>
                </div>
              )}

              {activeConversation?.messages?.length > 0 && (
                <div className="message-list">
                  {activeConversation.messages.map((item, index) => (
                    <div
                      className={`message-bubble ${item.role}`}
                      key={`${item.text}-${index}`}
                    >
                      <span className="message-role">
                        {item.role === 'user' ? 'YOU' : 'FINDPDF'}
                      </span>

                      {item.role === 'assistant' ? (
                        <div className="markdown-content">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {normalizeMarkdown(item.text)}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <p>{item.text}</p>
                      )}

                      {item.sources?.length > 0 && (
                        <div className="message-sources">
                          <strong>Sources</strong>
                          {item.sources.map((source, sourceIndex) => (
                            <div
                              className="source-card"
                              key={`${source.document}-${source.page}-${sourceIndex}`}
                            >
                              <button
                                type="button"
                                className="source-open-button"
                                onClick={() => openSource(source)}
                                title="Open this page in the original PDF"
                              >
                                <span className="source-pdf-icon">PDF</span>
                                <span className="source-title">
                                  <strong>{source.document}</strong>
                                  <small>Page {source.page} · View source</small>
                                </span>
                                <span className="source-arrow">↗</span>
                              </button>
                              <p className="source-excerpt">{source.excerpt}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}

                  {isSending && (
                    <div className="message-bubble assistant">
                      <span className="message-role">FINDPDF</span>
                      <p>Reading your documents and preparing an answer…</p>
                    </div>
                  )}
                </div>
              )}

              <div className="chat-suggestions">
                <button
                  onClick={() =>
                    setMessage('Summarize the main points in my PDFs')
                  }
                >
                  ✧ Summarize my documents
                </button>

                <button
                  onClick={() =>
                    setMessage(
                      'Compare the key differences between my PDFs'
                    )
                  }
                >
                  ⇄ Compare documents
                </button>

                <button
                  onClick={() =>
                    setMessage(
                      'Find the most important information in my PDFs'
                    )
                  }
                >
                  ⌕ Find key information
                </button>
              </div>

              <form className="chat-composer" onSubmit={sendMessage}>
                <textarea
                  ref={messageInputRef}
                  rows={2}
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                  placeholder="Ask anything about your documents..."
                  aria-label="Ask anything about your documents"
                />

                <div className="composer-footer">
                  <span>↵ Send · Shift + ↵ New line</span>
                  <button
                    type="submit"
                    className="send-button"
                    aria-label="Send message"
                    disabled={isSending || !message.trim() || !files.length}
                  >
                    {isSending ? '…' : '↑'}
                  </button>
                </div>
              </form>

              <p className="privacy-note">
                Answers are generated from retrieved excerpts in your uploaded
                PDFs. Check the source passages to verify important details.
              </p>
            </div>
          )}

          {activePage === 'Compare PDFs' && (
            <div className="page-view">
              <div className="eyebrow">CROSS-DOCUMENT ANALYSIS</div>

              <h1 className="page-title">
                See the <span className="gradient-text">connections.</span>
              </h1>

              <p className="page-description">
                Bring documents together to investigate similarities and
                differences.
              </p>

              <div className="compare-panel panel">
                <div className="compare-icon">⇄</div>
                <h2>Compare your PDFs</h2>
                <p>
                  Select at least two PDF documents to prepare a comparison
                  question.
                </p>

                <div className="compare-file-list">
                  {files.length === 0 ? (
                    <span className="compare-empty">
                      No PDF files selected yet.
                    </span>
                  ) : (
                    files.map((file) => (
                      <div className="compare-file" key={file.id}>
                        <span className="pdf-icon">PDF</span>
                        <span>{file.name}</span>
                        <span className="document-local-dot" />
                      </div>
                    ))
                  )}
                </div>

                <button
                  className="primary-button"
                  disabled={files.length < 2}
                  onClick={() => {
                    setActivePage('Chat')
                    setMessage(
                      'Compare the key similarities and differences across my selected PDFs.'
                    )
                  }}
                >
                  Prepare comparison <span>→</span>
                </button>

                {files.length < 2 && (
                  <small className="compare-hint">
                    Add at least two PDFs to prepare a comparison.
                  </small>
                )}
              </div>
            </div>
          )}

          {activePage === 'Chat History' && (
            <div className="page-view">
              <div className="eyebrow">YOUR CONVERSATIONS</div>

              <h1 className="page-title">
                Chat <span className="gradient-text">history.</span>
              </h1>

              <p className="page-description">
                Return to a conversation from this browser session.
              </p>

              {chats.length === 0 ? (
                <div className="empty-state panel">
                  <div className="empty-state-icon">◷</div>
                  <h2>No conversations yet</h2>
                  <p>Start a conversation to see it here.</p>
                  <button
                    className="primary-button"
                    onClick={createChat}
                  >
                    ＋ New conversation
                  </button>
                </div>
              ) : (
                <div className="history-page-list">
                  {chats.map((chat) => (
                    <button
                      className="history-page-item panel"
                      key={chat.id}
                      onClick={() => {
                        setActiveChat(chat.id)
                        setActivePage('Chat')
                      }}
                    >
                      <span className="feature-icon feature-purple">◌</span>
                      <span>
                        <strong>{chat.title}</strong>
                        <small>
                          {chat.messages.length} message
                          {chat.messages.length !== 1 ? 's' : ''}
                        </small>
                      </span>
                      <span className="feature-arrow">↗</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <footer className="page-footer">
            <span>
              <span className="footer-dot" /> FINDPDF WORKSPACE
            </span>
            <span>Built for better document understanding</span>
          </footer>
        </section>
      </main>

      {previewSource && (
        <div className="pdf-viewer-overlay" onClick={() => setPreviewSource(null)}>
          <div className="pdf-viewer-modal" onClick={(event) => event.stopPropagation()}>
            <div className="pdf-viewer-header">
              <div className="pdf-viewer-heading">
                <span className="source-pdf-icon">PDF</span>
                <div>
                  <strong>{previewSource.document}</strong>
                  <small>Page {previewSource.page}</small>
                </div>
              </div>
              <button
                type="button"
                className="pdf-viewer-close"
                onClick={() => setPreviewSource(null)}
                aria-label="Close PDF viewer"
              >
                ×
              </button>
            </div>
            <iframe
              className="pdf-viewer-frame"
              title={`PDF page ${previewSource.page}`}
              src={`${previewSource.localUrl}#page=${Math.max(1, Number(previewSource.page) || 1)}&toolbar=1&navpanes=0`}
            />
            <div className="pdf-viewer-footer">
              <span>Viewing cited page {previewSource.page}</span>
              <a
                href={`${previewSource.localUrl}#page=${Math.max(1, Number(previewSource.page) || 1)}`}
                target="_blank"
                rel="noreferrer"
              >
                Open in new tab ↗
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App