// ── State ────────────────────────────────────────────────
let activeCollection = null;
let isProcessing = false;

// ── DOM Elements ─────────────────────────────────────────
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');
const chatContainer = document.getElementById('chatContainer');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const docList = document.getElementById('docList');
const docEmpty = document.getElementById('docEmpty');
const activeDocHeader = document.getElementById('activeDoc');
const headerBadge = document.getElementById('headerBadge');
const sidebar = document.getElementById('sidebar');
const sidebarOpen = document.getElementById('sidebarOpen');
const sidebarClose = document.getElementById('sidebarClose');

// ── Initialize ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    setupEventListeners();
    autoResizeTextarea();
});

function setupEventListeners() {
    // Chat form
    chatForm.addEventListener('submit', handleSend);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend(e);
        }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', autoResizeTextarea);

    // File upload
    uploadZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', handleDrop);

    // Quick action buttons
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('quick-btn')) {
            const question = e.target.dataset.question;
            if (question) {
                chatInput.value = question;
                handleSend(e);
            }
        }
    });

    // Sidebar toggle (mobile)
    sidebarOpen.addEventListener('click', () => sidebar.classList.add('open'));
    sidebarClose.addEventListener('click', () => sidebar.classList.remove('open'));
}

function autoResizeTextarea() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
}

// ── Documents ────────────────────────────────────────────
async function loadDocuments() {
    try {
        const res = await fetch('/documents');
        const data = await res.json();
        renderDocuments(data.documents);
    } catch (err) {
        console.error('Failed to load documents:', err);
    }
}

function renderDocuments(documents) {
    if (!documents || documents.length === 0) {
        docEmpty.hidden = false;
        return;
    }

    docEmpty.hidden = true;

    // Remove existing doc items (keep empty placeholder)
    docList.querySelectorAll('.doc-item').forEach(el => el.remove());

    documents.forEach((doc, idx) => {
        const el = document.createElement('div');
        el.className = 'doc-item' + (idx === 0 && !activeCollection ? ' active' : '');
        el.innerHTML = `
            <div class="doc-item-name" title="${doc.filename}">📄 ${doc.filename}</div>
            <div class="doc-item-meta">
                <span>${doc.page_count} page${doc.page_count !== 1 ? 's' : ''}</span>
                <span>${doc.chunk_count} chunks</span>
            </div>
        `;
        el.addEventListener('click', () => selectDocument(doc.collection_name, doc.filename, el));
        docList.appendChild(el);

        // Auto-select first document
        if (idx === 0 && !activeCollection) {
            activeCollection = doc.collection_name;
            activeDocHeader.textContent = doc.filename;
            headerBadge.hidden = false;
        }
    });
}

function selectDocument(collectionName, filename, element) {
    activeCollection = collectionName;
    activeDocHeader.textContent = filename;
    headerBadge.hidden = false;

    // Update active state
    docList.querySelectorAll('.doc-item').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    // Close sidebar on mobile
    sidebar.classList.remove('open');
}

// ── File Upload ──────────────────────────────────────────
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) uploadFile(file);
}

function handleDrop(e) {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
}

async function uploadFile(file) {
    const allowed = ['.pdf', '.docx', '.txt'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
        addMessage('ai', `❌ Unsupported file type "${ext}". Please upload PDF, DOCX, or TXT files.`);
        return;
    }

    // Show progress
    const uploadContent = uploadZone.querySelector('.upload-content');
    uploadContent.hidden = true;
    uploadProgress.hidden = false;
    progressFill.style.width = '30%';
    progressText.textContent = `Uploading ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        progressFill.style.width = '60%';
        progressText.textContent = 'Processing & embedding...';

        const res = await fetch('/upload', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await res.json();
        progressFill.style.width = '100%';
        progressText.textContent = 'Done!';

        // Refresh document list
        await loadDocuments();

        // Select the new document
        if (data.document && data.document.collection_name) {
            activeCollection = data.document.collection_name;
            activeDocHeader.textContent = data.document.filename;
            headerBadge.hidden = false;
        }

        addMessage('ai', `✅ **"${file.name}"** has been processed and indexed successfully! You can now ask questions about it.`);

        // Reset upload UI
        setTimeout(() => {
            uploadContent.hidden = false;
            uploadProgress.hidden = true;
            progressFill.style.width = '0%';
        }, 1500);

    } catch (err) {
        addMessage('ai', `❌ Failed to process "${file.name}": ${err.message}`);
        uploadContent.hidden = false;
        uploadProgress.hidden = true;
        progressFill.style.width = '0%';
    }

    // Reset file input
    fileInput.value = '';
}

// ── Chat ─────────────────────────────────────────────────
async function handleSend(e) {
    e.preventDefault();
    const question = chatInput.value.trim();
    if (!question || isProcessing) return;

    // Add user message
    addMessage('user', question);
    chatInput.value = '';
    autoResizeTextarea();

    // Show typing indicator
    isProcessing = true;
    sendBtn.disabled = true;
    const typingEl = addTypingIndicator();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                collection: activeCollection,
            }),
        });

        // Remove typing indicator
        typingEl.remove();

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Request failed');
        }

        const data = await res.json();
        addMessage('ai', data.answer);

        if (data.collection) {
            activeCollection = data.collection;
        }

    } catch (err) {
        typingEl.remove();
        addMessage('ai', `❌ Error: ${err.message}`);
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// ── Message Rendering ────────────────────────────────────
function addMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;

    const avatar = role === 'ai' ? '◈' : '👤';
    const renderedContent = role === 'ai' ? renderMarkdown(content) : escapeHtml(content);

    msgDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">${renderedContent}</div>
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

function addTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ai-message typing-message';
    msgDiv.innerHTML = `
        <div class="message-avatar">◈</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
        });
        return marked.parse(text);
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });
}
