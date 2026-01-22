// ui/script-beep.js
// Client-side JavaScript for index-beep.html (Beep Sync Audio Censorship Tool).
// Handles file upload, bad words input, and audio censorship via /api/censor endpoint.

document.addEventListener('DOMContentLoaded', function () {
    // --- Configuration ---
    const IS_LOCAL_FILE = window.location.protocol === 'file:';
    const API_BASE_URL = IS_LOCAL_FILE ? 'http://localhost:8005' : '';

    // --- State ---
    let selectedFile = null;
    let currentAbortController = null;

    // --- DOM Element Selectors ---
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const notificationArea = document.getElementById('notification-area');
    const badWordsTextarea = document.getElementById('bad-words-textarea');
    const wordsCount = document.getElementById('words-count');
    const audioDropZone = document.getElementById('audio-drop-zone');
    const audioFileInput = document.getElementById('audio-file-input');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const removeFileBtn = document.getElementById('remove-file-btn');
    const generateBtn = document.getElementById('generate-btn');
    const audioPlayerContainer = document.getElementById('audio-player-container');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingMessage = document.getElementById('loading-message');
    const loadingCancelBtn = document.getElementById('loading-cancel-btn');
    const resultModal = document.getElementById('result-modal');
    const resultMessage = document.getElementById('result-message');
    const resultDetails = document.getElementById('result-details');
    const resultOkBtn = document.getElementById('result-ok-btn');
    const errorModal = document.getElementById('error-modal');
    const errorMessage = document.getElementById('error-message');
    const errorOkBtn = document.getElementById('error-ok-btn');

    // --- Utility Functions ---
    function showNotification(message, type = 'info', duration = 4000) {
        if (!notificationArea) return null;

        const icons = {
            success: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>',
            error: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>',
            warning: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" /></svg>',
            info: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd" /></svg>'
        };

        const notificationDiv = document.createElement('div');
        notificationDiv.className = `notification ${type}`;
        notificationDiv.setAttribute('role', 'alert');

        // Build notification structure
        notificationDiv.innerHTML = `
            ${icons[type] || icons['info']}
            <div class="notification__content"><span>${message}</span></div>
        `;

        // Create close button
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'notification__close';
        closeButton.innerHTML = `
            <span class="sr-only">Close</span>
            <svg class="notification__close-icon" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
        `;
        closeButton.onclick = () => {
            notificationDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            notificationDiv.style.opacity = '0';
            notificationDiv.style.transform = 'translateY(-20px)';
            setTimeout(() => notificationDiv.remove(), 300);
        };

        notificationDiv.appendChild(closeButton);
        notificationArea.appendChild(notificationDiv);

        if (duration > 0) {
            setTimeout(() => closeButton.click(), duration);
        }

        return notificationDiv;
    }

    // --- Theme Management ---
    function applyTheme(theme) {
        const isDark = theme === 'dark';
        document.documentElement.classList.toggle('dark', isDark);
        localStorage.setItem('uiTheme', theme);
    }

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            const newTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    }

    // Initialize theme from localStorage
    const savedTheme = localStorage.getItem('uiTheme') || 'dark';
    applyTheme(savedTheme);

    // --- Word Counter for Bad Words ---
    if (badWordsTextarea && wordsCount) {
        function updateWordCount() {
            const text = badWordsTextarea.value.trim();
            const words = text ? text.split(',').filter(w => w.trim()).length : 0;
            wordsCount.textContent = words;
        }
        badWordsTextarea.addEventListener('input', updateWordCount);
        updateWordCount();
    }

    // --- File Upload Handling ---
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    function handleFileSelect(file) {
        if (!file) return;

        const maxSize = 100 * 1024 * 1024; // 100MB
        if (file.size > maxSize) {
            showNotification('File too large. Maximum size is 100MB.', 'error');
            return;
        }

        const allowedTypes = ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/x-m4a', 'audio/flac', 'audio/ogg'];
        const allowedExtensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExt)) {
            showNotification('Invalid file type. Please upload a valid audio file.', 'error');
            return;
        }

        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        audioDropZone.classList.add('hidden');
        fileInfo.classList.remove('hidden');
        generateBtn.disabled = false;
        showNotification('File selected: ' + file.name, 'success', 3000);
    }

    function clearFileSelection() {
        selectedFile = null;
        fileName.textContent = 'No file selected';
        fileSize.textContent = '';
        audioDropZone.classList.remove('hidden');
        fileInfo.classList.add('hidden');
        generateBtn.disabled = true;
        if (audioFileInput) audioFileInput.value = '';
    }

    // Drag & Drop handlers
    if (audioDropZone && audioFileInput) {
        audioDropZone.addEventListener('click', () => audioFileInput.click());
        
        audioDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            audioDropZone.classList.add('dragover');
        });
        
        audioDropZone.addEventListener('dragleave', () => {
            audioDropZone.classList.remove('dragover');
        });
        
        audioDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            audioDropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
        
        audioFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', clearFileSelection);
    }

    // --- Character Counter (kept for compatibility if needed) ---
    if (document.getElementById('text') && document.getElementById('char-count')) {
        const textArea = document.getElementById('text');
        const charCount = document.getElementById('char-count');
        textArea.addEventListener('input', () => {
            charCount.textContent = textArea.value.length;
        });
    }

    // --- Loading Overlay ---
    function showLoading(message = 'Generating audio...') {
        if (!loadingOverlay) return;
        if (loadingMessage) loadingMessage.textContent = message;
        loadingOverlay.style.display = '';
        loadingOverlay.classList.remove('hidden', 'opacity-0');
        loadingOverlay.setAttribute('data-state', 'open');
    }

    function hideLoading() {
        if (!loadingOverlay) return;
        loadingOverlay.classList.add('opacity-0');
        loadingOverlay.setAttribute('data-state', 'closed');
        setTimeout(() => {
            loadingOverlay.style.display = 'none';
            loadingOverlay.classList.add('hidden');
        }, 300);
    }

    // --- Modal Handling ---
    function showModal(modal) {
        if (!modal) return;
        modal.style.display = '';
        modal.classList.remove('hidden', 'opacity-0');
        modal.setAttribute('data-state', 'open');
    }

    function hideModal(modal) {
        if (!modal) return;
        modal.classList.add('opacity-0');
        modal.setAttribute('data-state', 'closed');
        setTimeout(() => {
            modal.style.display = 'none';
            modal.classList.add('hidden');
        }, 300);
    }

    if (resultOkBtn) {
        resultOkBtn.addEventListener('click', () => hideModal(resultModal));
    }

    if (errorOkBtn) {
        errorOkBtn.addEventListener('click', () => hideModal(errorModal));
    }

    if (loadingCancelBtn) {
        loadingCancelBtn.addEventListener('click', () => {
            if (currentAbortController) {
                currentAbortController.abort();
                showNotification('Request cancelled', 'warning');
            }
            hideLoading();
        });
    }

    // --- Audio Player Creation ---
    function createAudioPlayer(audioUrl, stats = {}) {
        if (!audioPlayerContainer) return;

        audioPlayerContainer.innerHTML = '';

        const card = document.createElement('div');
        card.className = 'card';

        const cardBody = document.createElement('div');
        cardBody.className = 'card__body';

        const title = document.createElement('h3');
        title.className = 'card__title';
        title.textContent = 'Censored Audio Result';

        const audio = document.createElement('audio');
        audio.controls = true;
        audio.className = 'audio-player';
        audio.src = audioUrl;

        const downloadBtn = document.createElement('a');
        downloadBtn.href = audioUrl;
        downloadBtn.download = 'censored_audio.wav';
        downloadBtn.className = 'btn secondary';
        downloadBtn.innerHTML = `
            <svg class="btn__icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Download Censored Audio
        `;

        cardBody.appendChild(title);
        cardBody.appendChild(audio);
        
        if (stats.detected_count !== undefined) {
            const statsDiv = document.createElement('div');
            statsDiv.className = 'form-hint mt-4';
            statsDiv.innerHTML = `
                <p><strong>Censorship Stats:</strong></p>
                <ul class="tips-list">
                    <li>Bad words detected: <strong>${stats.detected_count}</strong></li>
                    <li>Groups censored: <strong>${stats.groups_censored || 0}</strong></li>
                    ${stats.detected_words && stats.detected_words.length > 0 ? 
                        `<li>Words found: ${stats.detected_words.join(', ')}</li>` : ''}
                </ul>
            `;
            cardBody.appendChild(statsDiv);
        }
        
        cardBody.appendChild(downloadBtn);
        card.appendChild(cardBody);
        audioPlayerContainer.appendChild(card);

        audio.play().catch(() => {});
    }

    // --- Censor Audio Request ---
    async function submitCensorRequest() {
        if (!selectedFile) {
            showNotification('Please select an audio file first', 'error');
            return;
        }

        const badWords = badWordsTextarea ? badWordsTextarea.value.trim() : '';
        
        showLoading('Processing audio...');
        currentAbortController = new AbortController();

        const formData = new FormData();
        formData.append('audio_file', selectedFile);
        formData.append('bad_words', badWords || 'fuck,shit,damn,bitch,asshole');

        try {
            const response = await fetch(API_BASE_URL + '/api/censor', {
                method: 'POST',
                body: formData,
                signal: currentAbortController.signal
            });

            hideLoading();

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            // Get stats from headers
            const detectedCount = parseInt(response.headers.get('X-Detected-Count') || '0');
            const groupsCensored = parseInt(response.headers.get('X-Groups-Censored') || '0');
            const detectedWords = (response.headers.get('X-Detected-Words') || '').split(',').filter(w => w);

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);

            createAudioPlayer(audioUrl, {
                detected_count: detectedCount,
                groups_censored: groupsCensored,
                detected_words: detectedWords
            });

            if (detectedCount === 0) {
                showNotification('No profanity detected. Audio returned unchanged.', 'info');
            } else {
                showNotification(`Success! Censored ${detectedCount} bad word(s) in ${groupsCensored} region(s).`, 'success');
            }

            // Show result modal
            if (resultModal && resultMessage && resultDetails) {
                resultMessage.textContent = detectedCount === 0 ? 
                    'No profanity detected in the audio.' :
                    `Successfully censored ${detectedCount} bad word(s)!`;
                
                resultDetails.innerHTML = `
                    <li>Bad words detected: <strong>${detectedCount}</strong></li>
                    <li>Audio regions censored: <strong>${groupsCensored}</strong></li>
                    ${detectedWords.length > 0 ? `<li>Words found: ${detectedWords.join(', ')}</li>` : ''}
                `;
                showModal(resultModal);
            }

        } catch (error) {
            hideLoading();
            if (error.name === 'AbortError') {
                showNotification('Request cancelled', 'warning');
                return;
            }
            
            console.error('Censorship error:', error);
            showNotification('Error: ' + error.message, 'error');
            
            if (errorModal && errorMessage) {
                errorMessage.textContent = error.message;
                showModal(errorModal);
            }
        }
    }

    // --- Generate Button Handler ---
    if (generateBtn) {
        generateBtn.addEventListener('click', submitCensorRequest);
    }

    console.log('Beep Sync UI initialized');
});
