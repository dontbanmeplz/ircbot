/**
 * Search Page JavaScript
 * Handles search form, results display, and book selection
 */

let currentSearchQuery = '';
let searchResults = {};
let selectedBooks = new Map(); // command -> {title, bot}

// DOM elements
let searchForm, searchQuery, searchBtn;
let statusSection, statusMessage, progressBar, progressFill;
let queueInfo, queueText;
let resultsSection, resultsTitle, resultsContainer, downloadSelectedBtn;

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements
    searchForm = document.getElementById('searchForm');
    searchQuery = document.getElementById('searchQuery');
    searchBtn = document.getElementById('searchBtn');
    
    statusSection = document.getElementById('statusSection');
    statusMessage = document.getElementById('statusMessage');
    progressBar = document.getElementById('progressBar');
    progressFill = document.getElementById('progressFill');
    
    queueInfo = document.getElementById('queueInfo');
    queueText = document.getElementById('queueText');
    
    resultsSection = document.getElementById('resultsSection');
    resultsTitle = document.getElementById('resultsTitle');
    resultsContainer = document.getElementById('resultsContainer');
    downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
    
    // Set up event listeners
    searchForm.addEventListener('submit', handleSearchSubmit);
    downloadSelectedBtn.addEventListener('click', handleDownloadSelected);
});

// Handle search form submission
function handleSearchSubmit(e) {
    e.preventDefault();
    
    const query = searchQuery.value.trim();
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    currentSearchQuery = query;
    selectedBooks.clear();
    
    // Clear previous results
    resultsSection.classList.add('hidden');
    resultsContainer.innerHTML = '';
    
    // Show status
    showStatus('Sending search request...', 0);
    
    // Send search request via WebSocket
    sendSearchRequest(query);
}

// Handle download selected button click
function handleDownloadSelected() {
    if (selectedBooks.size === 0) {
        alert('Please select at least one book');
        return;
    }
    
    const commands = [];
    const titles = [];
    
    selectedBooks.forEach((info, command) => {
        commands.push(command);
        titles.push(info.title);
    });
    
    // Send download request
    sendDownloadRequest(commands, titles, currentSearchQuery);
    
    // Clear selection
    selectedBooks.clear();
    updateDownloadButton();
    
    // Show status
    showStatus('Download request queued...', 0);
}

// WebSocket event handlers (called from socket.js)
window.handleStatusUpdate = function(data) {
    showStatus(data.message, data.progress, data.type);
};

window.handleQueueUpdate = function(data) {
    if (data.size > 0 && !data.processing) {
        queueInfo.classList.remove('hidden');
        queueText.textContent = `In queue: ${data.size} request(s)`;
    } else if (data.processing) {
        queueInfo.classList.remove('hidden');
        queueText.textContent = 'Processing...';
    } else {
        queueInfo.classList.add('hidden');
    }
};

window.handleSearchResults = function(data) {
    searchResults = data.grouped_results;
    const total = data.total;
    
    resultsTitle.textContent = `Search Results (${total} matches)`;
    resultsSection.classList.remove('hidden');
    
    renderResults(searchResults);
    
    showStatus(`Found ${total} results`, 100, 'success');
    setTimeout(() => hideStatus(), 3000);
};

window.handleDownloadComplete = function(data) {
    showStatus(`Downloaded: ${data.title}`, data.progress, 'success');
    
    if (data.progress === 100) {
        setTimeout(() => {
            showStatus('All downloads complete!', 100, 'success');
            setTimeout(() => hideStatus(), 3000);
        }, 1000);
    }
};

// Show status message and progress bar
function showStatus(message, progress, type = 'info') {
    statusSection.classList.remove('hidden');
    statusMessage.textContent = message;
    statusMessage.className = `status-message status-${type}`;
    progressFill.style.width = `${progress}%`;
}

// Hide status section
function hideStatus() {
    statusSection.classList.add('hidden');
}

// Render search results grouped by bot
function renderResults(groupedResults) {
    resultsContainer.innerHTML = '';
    
    if (Object.keys(groupedResults).length === 0) {
        resultsContainer.innerHTML = '<p class="no-results">No results found.</p>';
        return;
    }
    
    // Sort bots alphabetically
    const sortedBots = Object.keys(groupedResults).sort();
    
    sortedBots.forEach(botName => {
        const books = groupedResults[botName];
        
        // Create bot group
        const botGroup = document.createElement('div');
        botGroup.className = 'bot-group';
        
        // Bot header
        const botHeader = document.createElement('div');
        botHeader.className = 'bot-header';
        botHeader.innerHTML = `
            <h4 class="bot-name">${botName} <span class="book-count">(${books.length} books)</span></h4>
            <button class="toggle-btn" data-bot="${botName}">▼</button>
        `;
        botGroup.appendChild(botHeader);
        
        // Books list
        const booksList = document.createElement('div');
        booksList.className = 'books-list';
        booksList.id = `bot-${botName}`;
        
        books.forEach(book => {
            const bookItem = document.createElement('div');
            bookItem.className = 'book-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'book-checkbox';
            checkbox.id = `book-${book.command.replace(/[^a-zA-Z0-9]/g, '_')}`;
            checkbox.addEventListener('change', (e) => {
                handleBookSelection(e.target.checked, book.command, book.title, botName);
            });
            
            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.innerHTML = `
                <span class="book-title">${escapeHtml(book.title)}</span>
                <span class="book-meta">${book.size} • ${book.format.toUpperCase()}</span>
            `;
            
            bookItem.appendChild(checkbox);
            bookItem.appendChild(label);
            booksList.appendChild(bookItem);
        });
        
        botGroup.appendChild(booksList);
        resultsContainer.appendChild(botGroup);
        
        // Toggle button click
        botHeader.querySelector('.toggle-btn').addEventListener('click', (e) => {
            const btn = e.target;
            booksList.classList.toggle('collapsed');
            btn.textContent = booksList.classList.contains('collapsed') ? '▶' : '▼';
        });
    });
}

// Handle book selection
function handleBookSelection(checked, command, title, botName) {
    if (checked) {
        selectedBooks.set(command, { title, bot: botName });
    } else {
        selectedBooks.delete(command);
    }
    
    updateDownloadButton();
}

// Update download button state
function updateDownloadButton() {
    const count = selectedBooks.size;
    downloadSelectedBtn.textContent = `Download Selected (${count})`;
    downloadSelectedBtn.disabled = count === 0;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
