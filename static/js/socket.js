/**
 * WebSocket Connection Handler
 * Manages Socket.IO connection and event listeners
 */

// Global socket instance
let socket = null;
let isConnected = false;

// Initialize socket connection
function initSocket() {
    socket = io();
    
    // Connection events
    socket.on('connect', () => {
        console.log('Connected to server');
        isConnected = true;
        updateConnectionStatus('connected', 'Connected');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        isConnected = false;
        updateConnectionStatus('disconnected', 'Disconnected');
    });
    
    // Status updates
    socket.on('status', (data) => {
        console.log('Status update:', data);
        if (window.handleStatusUpdate) {
            window.handleStatusUpdate(data);
        }
    });
    
    // Queue updates
    socket.on('queue_update', (data) => {
        console.log('Queue update:', data);
        if (window.handleQueueUpdate) {
            window.handleQueueUpdate(data);
        }
    });
    
    // Search results
    socket.on('search_results', (data) => {
        console.log('Search results received:', data);
        if (window.handleSearchResults) {
            window.handleSearchResults(data);
        }
    });
    
    // Download complete
    socket.on('download_complete', (data) => {
        console.log('Download complete:', data);
        if (window.handleDownloadComplete) {
            window.handleDownloadComplete(data);
        }
    });
    
    // Bot connection status
    socket.on('bot_connected', (data) => {
        console.log('Bot connected:', data);
        updateConnectionStatus('bot-connected', `Bot: ${data.nickname}`);
    });
    
    socket.on('bot_disconnected', () => {
        console.log('Bot disconnected');
        updateConnectionStatus('connected', 'Connected');
    });
    
    // Error handling
    socket.on('error', (data) => {
        console.error('Socket error:', data);
        showError(data.message || 'An error occurred');
    });
}

// Update connection status indicator
function updateConnectionStatus(status, text) {
    const statusIndicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    if (statusIndicator && statusText) {
        statusIndicator.className = `status-indicator status-${status}`;
        statusText.textContent = text;
    }
}

// Send search request
function sendSearchRequest(query) {
    if (!isConnected) {
        showError('Not connected to server');
        return;
    }
    
    socket.emit('search', { query: query });
}

// Send download request
function sendDownloadRequest(commands, titles, query) {
    if (!isConnected) {
        showError('Not connected to server');
        return;
    }
    
    socket.emit('download', {
        commands: commands,
        titles: titles,
        query: query
    });
}

// Get queue status
function getQueueStatus() {
    if (!isConnected) {
        return;
    }
    
    socket.emit('get_queue_status');
}

// Show error message
function showError(message) {
    alert('Error: ' + message);
}

// Initialize socket on page load
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
});
