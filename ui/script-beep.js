// ui/script-beep.js
// Minimal client-side JavaScript for index-beep.html (Beep Sync TTS Server).
// Handles basic UI interactions, theme toggle, notifications, and simple TTS generation.

document.addEventListener('DOMContentLoaded', function () {
    // --- Configuration ---
    const IS_LOCAL_FILE = window.location.protocol === 'file:';
    const API_BASE_URL = IS_LOCAL_FILE ? 'http://localhost:8004' : '';

    // --- State ---
    let hideChunkWarning = false;
    let hideGenerationWarning = false;
    let currentAbortController = null;

    // --- DOM Element Selectors ---
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const notificationArea = document.getElementById('notification-area');
    const textArea = document.getElementById('text');
    const charCount = document.getElementById('char-count');
    const generateBtn = document.getElementById('generate-btn');
    const modelSelect = document.getElementById('model-select');
    const modelStatusIndicator = document.getElementById('model-status-indicator');
    const modelStatusText = document.getElementById('model-status-text');
    const applyModelBtn = document.getElementById('apply-model-btn');
    const audioPlayerContainer = document.getElementById('audio-player-container');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingMessage = document.getElementById('loading-message');
    const loadingCancelBtn = document.getElementById('loading-cancel-btn');
    const chunkWarningModal = document.getElementById('chunk-warning-modal');
    const chunkWarningOkBtn = document.getElementById('chunk-warning-ok');
    const chunkWarningCancelBtn = document.getElementById('chunk-warning-cancel');
    const hideChunkWarningCheckbox = document.getElementById('hide-chunk-warning-checkbox');
    const generationWarningModal = document.getElementById('generation-warning-modal');
    const generationWarningAcknowledgeBtn = document.getElementById('generation-warning-acknowledge');
    const hideGenerationWarningCheckbox = document.getElementById('hide-generation-warning-checkbox');

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

    // --- Character Counter ---
    if (textArea && charCount) {
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

    if (chunkWarningOkBtn) {
        chunkWarningOkBtn.addEventListener('click', () => {
            if (hideChunkWarningCheckbox && hideChunkWarningCheckbox.checked) {
                hideChunkWarning = true;
            }
            hideModal(chunkWarningModal);
        });
    }

    if (chunkWarningCancelBtn) {
        chunkWarningCancelBtn.addEventListener('click', () => {
            hideModal(chunkWarningModal);
        });
    }

    if (generationWarningAcknowledgeBtn) {
        generationWarningAcknowledgeBtn.addEventListener('click', () => {
            if (hideGenerationWarningCheckbox && hideGenerationWarningCheckbox.checked) {
                hideGenerationWarning = true;
            }
            hideModal(generationWarningModal);
        });
    }

    if (loadingCancelBtn) {
        loadingCancelBtn.addEventListener('click', () => {
            if (currentAbortController) {
                currentAbortController.abort();
                showNotification('Generation cancelled', 'warning');
            }
            hideLoading();
        });
    }

    // --- Fetch Initial Data ---
    async function fetchInitialData() {
        try {
            const response = await fetch(API_BASE_URL + '/api/ui/initial-data');
            if (!response.ok) throw new Error('Failed to fetch initial data');
            
            const data = await response.json();

            // Update model status
            if (data.model && modelStatusText && modelStatusIndicator) {
                modelStatusText.textContent = data.model.name || 'Model loaded';
                modelStatusIndicator.className = 'status-dot success';
            }

            // Populate model selector
            if (data.available_models && modelSelect) {
                modelSelect.innerHTML = '';
                data.available_models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id || model;
                    option.textContent = model.name || model;
                    modelSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to fetch initial data:', error);
            if (modelStatusText) modelStatusText.textContent = 'Failed to load model info';
            if (modelStatusIndicator) modelStatusIndicator.className = 'status-dot error';
        }
    }

    // --- Audio Player ---
    function createAudioPlayer(blob) {
        if (!audioPlayerContainer) return;
        
        const url = URL.createObjectURL(blob);
        audioPlayerContainer.innerHTML = `
            <div class="card">
                <div class="card__body">
                    <h3 class="card__title">Generated Audio</h3>
                    <audio controls style="width: 100%; margin-top: 1rem;">
                        <source src="${url}" type="${blob.type}">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            </div>
        `;
        
        const audioElement = audioPlayerContainer.querySelector('audio');
        if (audioElement) {
            audioElement.play().catch(() => {});
        }
    }

    // --- TTS Generation ---
    function getTTSFormData() {
        return {
            text: (textArea && textArea.value) ? textArea.value : ''
        };
    }

    async function submitTTSRequest() {
        if (!textArea || !textArea.value.trim()) {
            showNotification('Please enter text to synthesize', 'warning');
            return;
        }

        showLoading();

        try {
            currentAbortController = new AbortController();
            
            const response = await fetch(API_BASE_URL + '/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getTTSFormData()),
                signal: currentAbortController.signal
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || response.statusText);
            }

            const blob = await response.blob();
            createAudioPlayer(blob);
            showNotification('Audio generated successfully', 'success');

        } catch (error) {
            if (error.name === 'AbortError') {
                showNotification('Generation cancelled', 'warning');
            } else {
                showNotification('Generation failed: ' + (error.message || 'Unknown error'), 'error');
                console.error('TTS generation error:', error);
            }
        } finally {
            hideLoading();
            currentAbortController = null;
        }
    }

    // --- Event Listeners ---
    if (generateBtn) {
        generateBtn.addEventListener('click', submitTTSRequest);
    }

    if (applyModelBtn && modelSelect) {
        applyModelBtn.addEventListener('click', async () => {
            showNotification('Applying model change (server restart may be required)', 'info', 3000);
            try {
                await fetch(API_BASE_URL + '/api/ui/set-model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: modelSelect.value })
                });
                await fetchInitialData();
                showNotification('Model applied successfully', 'success');
            } catch (error) {
                showNotification('Failed to apply model change', 'error');
                console.error('Model change error:', error);
            }
        });
    }

    // --- Initialize ---
    fetchInitialData();
});
