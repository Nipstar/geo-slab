// =====================================================================
// LINKEDIN VOICE NOTES — Content Script
// Injects mic button into message compose areas, records audio,
// attaches to conversation.
// =====================================================================
(function () {
  'use strict';

  const MAX_DURATION = 60;
  const BAR_COUNT = 20;

  let mediaRecorder = null;
  let audioChunks = [];
  let audioBlob = null;
  let audioUrl = null;
  let audioElement = null;
  let analyser = null;
  let animFrameId = null;
  let timerInterval = null;
  let startTime = 0;
  let isRecording = false;

  // ——— Inject mic buttons next to message compose areas ———
  // Instead of finding LinkedIn's toolbar (which changes constantly),
  // we find the contenteditable message input and place a mic button nearby.

  function injectMicButton() {
    // Find all contenteditable areas that look like message compose fields
    const editables = document.querySelectorAll(
      '[contenteditable="true"][role="textbox"], ' +
      '.msg-form__contenteditable [contenteditable="true"], ' +
      '[contenteditable="true"][aria-label*="message" i], ' +
      '[contenteditable="true"][aria-label*="Message" i], ' +
      '[contenteditable="true"][data-placeholder*="message" i], ' +
      '[contenteditable="true"][aria-placeholder*="message" i], ' +
      'div.msg-form__msg-content-container [contenteditable="true"]'
    );

    // Broader fallback: any contenteditable inside a msg-related container
    let targets = [...editables];
    if (targets.length === 0) {
      document.querySelectorAll('[contenteditable="true"]').forEach(el => {
        const parent = el.closest(
          '.msg-form, .msg-overlay-conversation-bubble, .msg-convo-wrapper, ' +
          '[class*="message-composer"], [class*="msg-compose"], [role="dialog"]'
        );
        if (parent) targets.push(el);
      });
    }

    // Even broader: find by placeholder text "Write a message"
    if (targets.length === 0) {
      document.querySelectorAll('[contenteditable="true"]').forEach(el => {
        const placeholder = el.getAttribute('aria-placeholder') ||
                            el.getAttribute('data-placeholder') ||
                            el.getAttribute('placeholder') ||
                            el.querySelector('p')?.textContent || '';
        if (placeholder.toLowerCase().includes('message') ||
            placeholder.toLowerCase().includes('write')) {
          targets.push(el);
        }
      });
    }

    if (targets.length === 0) {
      // Last resort: log all contenteditables for debugging
      const all = document.querySelectorAll('[contenteditable="true"]');
      if (all.length > 0) {
        console.log('[Antek Voice] Found contenteditable elements but none matched messaging:', 
          [...all].map(e => ({ class: e.className, parent: e.parentElement?.className, aria: e.getAttribute('aria-label') }))
        );
      }
      return;
    }

    targets.forEach(editable => {
      // Check if we already injected next to this editable
      const formContainer = editable.closest(
        '.msg-form, .msg-overlay-conversation-bubble, .msg-convo-wrapper, [role="dialog"], .msg-s-event-listitem'
      ) || editable.parentElement?.parentElement;

      if (!formContainer) return;
      if (formContainer.querySelector('.lvn-mic-btn')) return;

      // Create floating mic button
      const btn = document.createElement('button');
      btn.className = 'lvn-mic-btn lvn-mic-floating';
      btn.title = 'Record voice note';
      btn.type = 'button';
      btn.innerHTML = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
      </svg>`;
      btn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        toggleRecorder(formContainer);
      });

      // Try to append to the form's toolbar area, or fall back to the form container
      const toolbar = formContainer.querySelector(
        '[class*="left-action"], [class*="footer"], [class*="toolbar"]'
      );
      if (toolbar && !toolbar.querySelector('.lvn-mic-btn')) {
        toolbar.appendChild(btn);
        console.log('[Antek Voice] Mic injected into toolbar:', toolbar.className);
      } else {
        // Position it as a floating button inside the form container
        formContainer.style.position = 'relative';
        formContainer.appendChild(btn);
        console.log('[Antek Voice] Mic injected as floating button in:', formContainer.className || formContainer.tagName);
      }
    });
  }

  // ——— Recorder UI ———

  function toggleRecorder(anchorEl) {
    const existing = document.querySelector('.lvn-recorder');
    if (existing) { cleanup(); existing.remove(); return; }
    showRecorder(anchorEl);
  }

  function showRecorder(anchorEl) {
    const recorder = document.createElement('div');
    recorder.className = 'lvn-recorder';
    recorder.innerHTML = `
      <div class="lvn-recorder-header">
        <span class="lvn-recorder-title">Voice Note</span>
        <button class="lvn-recorder-close" title="Close">&times;</button>
      </div>
      <div class="lvn-timer">0:00</div>
      <div class="lvn-waveform">
        ${Array.from({ length: BAR_COUNT }, () => '<div class="lvn-waveform-bar" style="height:4px"></div>').join('')}
      </div>
      <div class="lvn-controls">
        <button class="lvn-btn lvn-btn-record" title="Record">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="#fff"/></svg>
        </button>
      </div>
      <div class="lvn-status">Tap to record (max 60s)</div>
    `;

    const wrapper = anchorEl.closest('.msg-form, .msg-overlay-conversation-bubble, .msg-convo-wrapper, [role="dialog"]') || anchorEl.parentElement;
    wrapper.style.position = 'relative';
    wrapper.appendChild(recorder);

    recorder.querySelector('.lvn-recorder-close').addEventListener('click', () => {
      cleanup(); recorder.remove();
    });
    recorder.querySelector('.lvn-btn-record').addEventListener('click', () => {
      startRecording(recorder, wrapper);
    });
  }

  // ——— Recording ———

  async function startRecording(recorderEl, formEl) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);

      const mimeType = MediaRecorder.isTypeSupported('audio/mp4')
        ? 'audio/mp4'
        : MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm';

      mediaRecorder = new MediaRecorder(stream, { mimeType });
      audioChunks = [];
      isRecording = true;
      startTime = Date.now();

      mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        audioCtx.close();
        const ext = mimeType.includes('mp4') ? 'm4a' : 'webm';
        const fileMime = mimeType.includes('mp4') ? 'audio/mp4' : 'audio/webm';
        audioBlob = new Blob(audioChunks, { type: fileMime });
        audioUrl = URL.createObjectURL(audioBlob);
        audioElement = new Audio(audioUrl);
        isRecording = false;
        showPreview(recorderEl, formEl, ext);
      };

      mediaRecorder.start(250);

      // Update timer + waveform
      const bars = recorderEl.querySelectorAll('.lvn-waveform-bar');
      const timerEl = recorderEl.querySelector('.lvn-timer');
      const statusEl = recorderEl.querySelector('.lvn-status');
      statusEl.textContent = 'Recording...';

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      function animate() {
        if (!isRecording) return;
        analyser.getByteFrequencyData(dataArray);
        bars.forEach((bar, i) => {
          const val = dataArray[i % dataArray.length] || 0;
          bar.style.height = Math.max(4, (val / 255) * 36) + 'px';
        });
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(elapsed / 60);
        const s = (elapsed % 60).toString().padStart(2, '0');
        timerEl.textContent = `${m}:${s}`;
        if (elapsed >= MAX_DURATION) { mediaRecorder.stop(); return; }
        animFrameId = requestAnimationFrame(animate);
      }
      animate();

      // Swap to stop button
      const controls = recorderEl.querySelector('.lvn-controls');
      controls.innerHTML = `
        <button class="lvn-btn lvn-btn-stop" title="Stop">
          <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="#fff"/></svg>
        </button>
      `;
      controls.querySelector('.lvn-btn-stop').addEventListener('click', () => {
        mediaRecorder.stop();
      });

    } catch (err) {
      console.error('Voice note error:', err);
      const statusEl = recorderEl.querySelector('.lvn-status');
      statusEl.textContent = 'Mic access denied';
    }
  }

  // ——— Preview ———

  function showPreview(recorderEl, formEl, ext) {
    const controls = recorderEl.querySelector('.lvn-controls');
    const statusEl = recorderEl.querySelector('.lvn-status');
    statusEl.textContent = 'Preview your voice note';

    // Reset waveform bars
    recorderEl.querySelectorAll('.lvn-waveform-bar').forEach(b => { b.style.height = '4px'; });

    controls.innerHTML = `
      <button class="lvn-btn lvn-btn-discard" title="Discard">
        <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" stroke="#666" stroke-width="2" fill="none"/></svg>
      </button>
      <button class="lvn-btn lvn-btn-play" title="Play">
        <svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="#fff"/></svg>
      </button>
      <button class="lvn-btn lvn-btn-send" title="Send">
        <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z" fill="#fff"/></svg>
      </button>
    `;

    controls.querySelector('.lvn-btn-discard').addEventListener('click', () => {
      cleanup(); recorderEl.remove();
    });

    controls.querySelector('.lvn-btn-play').addEventListener('click', () => {
      if (audioElement) {
        audioElement.currentTime = 0;
        audioElement.play();
      }
    });

    controls.querySelector('.lvn-btn-send').addEventListener('click', () => {
      sendVoiceNote(formEl, ext);
      cleanup(); recorderEl.remove();
    });
  }

  // ——— Send / Attach ———

  function sendVoiceNote(formEl, ext) {
    if (!audioBlob) return;
    const fileName = `voice_note_${Date.now()}.${ext}`;
    const file = new File([audioBlob], fileName, { type: audioBlob.type });

    // Try to find LinkedIn's hidden file input — search broadly
    const fileInput = formEl.querySelector('input[type="file"]')
      || document.querySelector('.msg-form input[type="file"]')
      || document.querySelector('.msg-overlay-conversation-bubble input[type="file"]')
      || document.querySelector('[role="dialog"] input[type="file"]')
      || document.querySelector('input[type="file"][accept*="audio"], input[type="file"][accept*="video"], input[type="file"]');

    if (fileInput) {
      try {
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('[Antek Voice] Attached via file input');
        return;
      } catch (e) {
        console.warn('[Antek Voice] DataTransfer failed, trying drag-drop', e);
      }
    }

    // Fallback: trigger drag-and-drop on the message form
    const dropZone = formEl.querySelector('[contenteditable="true"]')
      || formEl.querySelector('.msg-form__contenteditable')
      || formEl.querySelector('[contenteditable]')
      || formEl;

    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      const dropEvent = new DragEvent('drop', { bubbles: true, dataTransfer: dt });
      dropZone.dispatchEvent(dropEvent);
      console.log('[Antek Voice] Attached via drag-drop');
      return;
    } catch (e) {
      console.warn('[Antek Voice] Drag-drop failed, downloading file', e);
    }

    // Last resort: download the file for manual attachment
    const a = document.createElement('a');
    a.href = URL.createObjectURL(audioBlob);
    a.download = fileName;
    a.click();
    console.log('[Antek Voice] Downloaded for manual attachment');
  }

  // ——— Cleanup ———

  function cleanup() {
    isRecording = false;
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try { mediaRecorder.stop(); } catch (e) {}
    }
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (timerInterval) clearInterval(timerInterval);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    mediaRecorder = null;
    audioChunks = [];
    audioBlob = null;
    audioUrl = null;
    audioElement = null;
    analyser = null;
  }

  // ——— Observer: watch for new message forms (debounced) ———

  let injectTimer = null;
  const observer = new MutationObserver(() => {
    if (injectTimer) clearTimeout(injectTimer);
    injectTimer = setTimeout(injectMicButton, 300);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Initial injection
  setTimeout(injectMicButton, 1000);

})();
