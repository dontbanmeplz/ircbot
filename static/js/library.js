/**
 * Library Page JavaScript
 * Handles library browsing, filtering, and book management
 */

let allBooks = [];
let filters = { formats: [], sources: [] };

// DOM elements
let librarySearch, formatFilter, sourceFilter, sortBy;
let libraryContainer, libraryBooks, loadingSpinner, emptyLibrary;
let totalBooks, totalSize;

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements
    librarySearch = document.getElementById('librarySearch');
    formatFilter = document.getElementById('formatFilter');
    sourceFilter = document.getElementById('sourceFilter');
    sortBy = document.getElementById('sortBy');
    
    libraryContainer = document.getElementById('libraryContainer');
    libraryBooks = document.getElementById('libraryBooks');
    loadingSpinner = document.getElementById('loadingSpinner');
    emptyLibrary = document.getElementById('emptyLibrary');
    
    totalBooks = document.getElementById('totalBooks');
    totalSize = document.getElementById('totalSize');
    
    // Set up event listeners
    librarySearch.addEventListener('input', debounce(loadLibrary, 300));
    formatFilter.addEventListener('change', loadLibrary);
    sourceFilter.addEventListener('change', loadLibrary);
    sortBy.addEventListener('change', loadLibrary);
    
    // Load library
    loadFilters();
    loadLibrary();
});

// Load available filter options
async function loadFilters() {
    try {
        const response = await fetch('/api/library/filters');
        const data = await response.json();
        
        if (data.success) {
            filters = data;
            
            // Populate format filter
            formatFilter.innerHTML = '<option value="">All Formats</option>';
            data.formats.forEach(format => {
                const option = document.createElement('option');
                option.value = format;
                option.textContent = format.toUpperCase();
                formatFilter.appendChild(option);
            });
            
            // Populate source filter
            sourceFilter.innerHTML = '<option value="">All Sources</option>';
            data.sources.forEach(source => {
                const option = document.createElement('option');
                option.value = source;
                option.textContent = source;
                sourceFilter.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading filters:', error);
    }
}

// Load library books
async function loadLibrary() {
    try {
        // Show loading
        loadingSpinner.classList.remove('hidden');
        libraryBooks.classList.add('hidden');
        emptyLibrary.classList.add('hidden');
        
        // Build query parameters
        const params = new URLSearchParams({
            q: librarySearch.value,
            format: formatFilter.value,
            source: sourceFilter.value,
            sort: sortBy.value
        });
        
        const response = await fetch(`/api/library/books?${params}`);
        const data = await response.json();
        
        if (data.success) {
            allBooks = data.books;
            renderLibrary(allBooks);
            updateStats(allBooks);
        } else {
            throw new Error(data.error || 'Failed to load library');
        }
        
        loadingSpinner.classList.add('hidden');
        
    } catch (error) {
        console.error('Error loading library:', error);
        loadingSpinner.classList.add('hidden');
        alert('Error loading library: ' + error.message);
    }
}

// Render library books
function renderLibrary(books) {
    libraryBooks.innerHTML = '';
    
    if (books.length === 0) {
        libraryBooks.classList.add('hidden');
        emptyLibrary.classList.remove('hidden');
        return;
    }
    
    libraryBooks.classList.remove('hidden');
    emptyLibrary.classList.add('hidden');
    
    books.forEach(book => {
        const bookCard = document.createElement('div');
        bookCard.className = 'book-card';
        
        const title = book.title || book.filename;
        const author = book.author ? `by ${book.author}` : '';
        const size = formatBytes(book.file_size);
        const date = new Date(book.download_date).toLocaleDateString();
        
        bookCard.innerHTML = `
            <div class="book-info">
                <h3 class="book-title">${escapeHtml(title)}</h3>
                ${author ? `<p class="book-author">${escapeHtml(author)}</p>` : ''}
                <div class="book-meta">
                    <span class="meta-item">${size}</span>
                    <span class="meta-item">${book.file_format.toUpperCase()}</span>
                    <span class="meta-item">Source: ${book.bot_source}</span>
                    <span class="meta-item">Added: ${date}</span>
                </div>
            </div>
            <div class="book-actions">
                <a href="/download/${book.id}" class="btn btn-primary btn-sm" download>Download</a>
                <button class="btn btn-danger btn-sm" onclick="deleteBook(${book.id}, '${escapeHtml(title)}')">Delete</button>
            </div>
        `;
        
        libraryBooks.appendChild(bookCard);
    });
}

// Update library statistics
function updateStats(books) {
    const count = books.length;
    const size = books.reduce((sum, book) => sum + (book.file_size || 0), 0);
    
    totalBooks.textContent = `${count} book${count !== 1 ? 's' : ''}`;
    totalSize.textContent = formatBytes(size);
}

// Delete a book
async function deleteBook(bookId, bookTitle) {
    if (!confirm(`Are you sure you want to delete "${bookTitle}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/library/delete/${bookId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Reload library
            loadLibrary();
        } else {
            throw new Error(data.error || 'Failed to delete book');
        }
        
    } catch (error) {
        console.error('Error deleting book:', error);
        alert('Error deleting book: ' + error.message);
    }
}

// Utility: Format bytes to human-readable size
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Utility: Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Make deleteBook available globally
window.deleteBook = deleteBook;
