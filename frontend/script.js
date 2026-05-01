/**
 * VDROP — Frontend Controller
 * Handles: URL validation, API calls, progress polling, history rendering
 */

'use strict';

/* ═══ DOM refs ═══ */
const urlInput    = document.getElementById('urlInput');
const pasteBtn    = document.getElementById('pasteBtn');
const downloadBtn = document.getElementById('downloadBtn');
const statusPanel = document.getElementById('statusPanel');
const statusDot   = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');
const statusPct   = document.getElementById('statusPct');
const progressBar = document.getElementById('progressBar');
const statusDetail= document.getElementById('statusDetail');
const historyList = document.getElementById('historyList');
const historyEmpty= document.getElementById('historyEmpty');
const refreshBtn  = document.getElementById('refreshBtn');
const pills       = document.querySelectorAll('.pill');

/* ═══ State ═══ */
let selectedQuality = '1080p';
let pollInterval    = null;   // setInterval handle for progress polling
let activeVideoId   = null;   // currently downloading video id

/* ═══ Quality pill selection ═══ */
pills.forEach(pill => {
  pill.addEventListener('click', () => {
    pills.forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    selectedQuality = pill.dataset.q;
  });
});

/* ═══ Paste from clipboard ═══ */
pasteBtn.addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    urlInput.value = text.trim();
    urlInput.focus();
  } catch {
    // Clipboard access denied — just focus the field
    urlInput.focus();
  }
});

/* ═══ URL validation (lightweight) ═══ */
function isValidUrl(str) {
  try {
    const u = new URL(str);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

/* ═══ Show / update the status panel ═══ */
function showStatus({ label, pct, detail, state = 'loading' }) {
  statusPanel.hidden = false;

  statusLabel.textContent = label.toUpperCase();
  statusPct.textContent   = pct !== undefined ? `${pct}%` : '';
  statusDetail.textContent= detail || '';

  progressBar.style.width = `${pct ?? 0}%`;

  // State classes on dot
  statusDot.className = 'status-dot';
  if (state === 'done')  statusDot.classList.add('done');
  if (state === 'error') statusDot.classList.add('error');
}

/* ═══ Poll a single video record for progress ═══ */
function startPolling(videoId) {
  clearInterval(pollInterval);
  activeVideoId = videoId;

  pollInterval = setInterval(async () => {
    try {
      const res  = await fetch(`/api/videos/${videoId}`);
      const data = await res.json();

      if (data.status === 'downloading') {
        showStatus({
          label:  'Downloading',
          pct:    data.progress,
          detail: data.file_size ? `File size: ${data.file_size}` : 'Fetching video info…',
          state:  'loading',
        });
      }

      if (data.status === 'done') {
        clearInterval(pollInterval);
        showStatus({ label: 'Download complete ✓', pct: 100, detail: data.title, state: 'done' });
        downloadBtn.disabled = false;
        loadHistory();
      }

      if (data.status === 'error') {
        clearInterval(pollInterval);
        showStatus({ label: 'Download failed', pct: 0, detail: data.error_msg, state: 'error' });
        downloadBtn.disabled = false;
        loadHistory();
      }

    } catch (err) {
      clearInterval(pollInterval);
      showStatus({ label: 'Connection error', detail: err.message, state: 'error' });
      downloadBtn.disabled = false;
    }
  }, 1200); // poll every 1.2 s
}

/* ═══ Start download ═══ */
downloadBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();

  // Client-side validation
  if (!url) {
    showStatus({ label: 'URL required', detail: 'Please paste a video URL first.', state: 'error', pct: 0 });
    urlInput.focus();
    return;
  }
  if (!isValidUrl(url)) {
    showStatus({
      label:  'Invalid URL',
      detail: 'URL must start with http:// or https://',
      state:  'error', pct: 0,
    });
    return;
  }

  // Disable button & show "starting" state
  downloadBtn.disabled = true;
  showStatus({ label: 'Starting download…', pct: 0, detail: url, state: 'loading' });

  try {
    const res  = await fetch('/api/download', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ url, quality: selectedQuality }),
    });
    const data = await res.json();

    if (!res.ok) {
      // Server returned a validation/error message
      showStatus({ label: 'Error', detail: data.error || 'Server error', state: 'error', pct: 0 });
      downloadBtn.disabled = false;
      return;
    }

    // Start polling for progress
    startPolling(data.id);
    loadHistory(); // refresh list immediately so new entry appears

  } catch (err) {
    showStatus({ label: 'Network error', detail: err.message, state: 'error', pct: 0 });
    downloadBtn.disabled = false;
  }
});

/* ═══ Format relative time ═══ */
function relTime(isoStr) {
  const diff = (Date.now() - new Date(isoStr + 'Z')) / 1000;
  if (diff < 60)   return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

/* ═══ Render a single history row ═══ */
function renderHistoryItem(v) {
  const item = document.createElement('div');
  item.className = 'history-item';
  item.dataset.id = v.id;

  const statusClass = v.status; // downloading | done | error
  const progPct     = v.status === 'done' ? 100 : (v.progress ?? 0);
  const progLabel   = v.status === 'done' ? 'Complete'
                    : v.status === 'error' ? 'Failed'
                    : `${progPct}%`;

  item.innerHTML = `
    <div class="hi-status ${statusClass}" title="${v.status}"></div>

    <div class="hi-info">
      <div class="hi-title">${escHtml(v.title || 'Fetching info…')}</div>
      <div class="hi-url">${escHtml(v.url)}</div>
    </div>

    <div class="hi-progress">
      <div class="hi-prog-bar">
        <div class="hi-prog-fill ${statusClass}" style="width:${progPct}%"></div>
      </div>
      <div class="hi-prog-label">${progLabel}</div>
    </div>

    <div class="hi-meta">
      <span class="hi-quality">${escHtml(v.quality)}</span>
      <span class="hi-time">${relTime(v.created_at)}</span>
    </div>
  `;
  return item;
}

/* ═══ Escape HTML to prevent XSS ═══ */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ═══ Load / refresh download history ═══ */
async function loadHistory() {
  try {
    const res    = await fetch('/api/videos');
    const videos = await res.json();

    // Clear existing items (keep empty placeholder in DOM)
    historyList.querySelectorAll('.history-item').forEach(el => el.remove());

    if (!videos.length) {
      historyEmpty.hidden = false;
      return;
    }

    historyEmpty.hidden = true;
    videos.forEach(v => historyList.appendChild(renderHistoryItem(v)));

    // Keep live-updating any rows that are still downloading
    videos
      .filter(v => v.status === 'downloading' && v.id !== activeVideoId)
      .forEach(v => {
        // passive refresh — just update DOM, not full poll
      });

  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

/* ═══ Refresh button ═══ */
refreshBtn.addEventListener('click', () => {
  refreshBtn.textContent = '↺ REFRESHING…';
  loadHistory().finally(() => { refreshBtn.textContent = '↺ REFRESH'; });
});

/* ═══ Auto-refresh history every 5s when page is visible ═══ */
let autoRefresh = setInterval(loadHistory, 5000);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    clearInterval(autoRefresh);
  } else {
    loadHistory();
    autoRefresh = setInterval(loadHistory, 5000);
  }
});

/* ═══ Init ═══ */
loadHistory();
