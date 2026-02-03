// AI News Scraper - Frontend JavaScript

// State
let currentSource = 'all';
let currentOffset = 0;
const ARTICLES_PER_PAGE = 30;

// DOM Elements
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const scrapeBtn = document.getElementById('scrapeBtn');
const articlesGrid = document.getElementById('articlesGrid');
const sourceFilters = document.getElementById('sourceFilters');
const articleCount = document.getElementById('articleCount');
const lastUpdated = document.getElementById('lastUpdated');
const aiResponse = document.getElementById('aiResponse');
const aiResponseText = document.getElementById('aiResponseText');
const aiLoading = document.getElementById('aiLoading');
const emptyState = document.getElementById('emptyState');
const loadMore = document.getElementById('loadMore');
const toastContainer = document.getElementById('toastContainer');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSources();
    loadArticles();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    // Search
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });

    // Scrape
    scrapeBtn.addEventListener('click', handleScrape);

    // Load more
    loadMore.querySelector('button').addEventListener('click', () => {
        currentOffset += ARTICLES_PER_PAGE;
        loadArticles(true);
    });
}

// Load sources for filter pills
async function loadSources() {
    try {
        const response = await fetch('/api/sources');
        const data = await response.json();

        // Add source filter buttons
        data.sources.forEach(source => {
            const btn = document.createElement('button');
            btn.dataset.source = source.name;
            btn.className = 'source-filter px-4 py-2 rounded-full text-sm font-medium transition-all duration-200';
            btn.textContent = formatSourceName(source.name) + ` (${source.count})`;
            btn.addEventListener('click', () => filterBySource(source.name));
            sourceFilters.appendChild(btn);
        });

        // Update last updated
        if (data.last_updated) {
            lastUpdated.textContent = `Last updated: ${formatDate(data.last_updated)}`;
        }
    } catch (error) {
        console.error('Error loading sources:', error);
    }
}

// Load articles
async function loadArticles(append = false) {
    try {
        const url = new URL('/api/articles', window.location.origin);
        url.searchParams.set('limit', ARTICLES_PER_PAGE);
        url.searchParams.set('offset', currentOffset);
        if (currentSource !== 'all') {
            url.searchParams.set('source', currentSource);
        }

        const response = await fetch(url);
        const data = await response.json();

        if (!append) {
            articlesGrid.innerHTML = '';
        }

        if (data.articles.length === 0 && !append) {
            emptyState.classList.remove('hidden');
            articlesGrid.classList.add('hidden');
            loadMore.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            articlesGrid.classList.remove('hidden');

            data.articles.forEach(article => {
                articlesGrid.appendChild(createArticleCard(article));
            });

            // Show/hide load more button
            if (data.articles.length === ARTICLES_PER_PAGE) {
                loadMore.classList.remove('hidden');
            } else {
                loadMore.classList.add('hidden');
            }
        }

        // Update count
        const totalCount = data.count + currentOffset;
        articleCount.textContent = `Showing ${totalCount} articles`;

    } catch (error) {
        console.error('Error loading articles:', error);
        showToast('Failed to load articles', 'error');
    }
}

// Create article card HTML
function createArticleCard(article) {
    const card = document.createElement('article');
    card.className = 'article-card';

    const date = article.published_date ? formatDate(article.published_date) : 'Date unknown';
    const summary = article.tldr || article.summary || 'No summary available.';
    const impactedStocks = article.impacted_stocks || [];

    // Build stocks HTML
    let stocksHtml = '';
    if (impactedStocks.length > 0) {
        const stockBadges = impactedStocks.map(s =>
            `<span class="stock-badge" title="${escapeHtml(s.reason || '')}">${s.ticker}</span>`
        ).join('');
        stocksHtml = `
            <div class="mt-3 flex flex-wrap items-center gap-1">
                <span class="text-xs text-gray-500 mr-1">📊</span>
                ${stockBadges}
            </div>
        `;
    }

    card.innerHTML = `
        <div class="flex items-center justify-between mb-3">
            <span class="source-badge ${article.source}">${formatSourceName(article.source)}</span>
            <span class="article-date">${date}</span>
        </div>
        <h3 class="font-semibold text-gray-800 mb-2 line-clamp-2">
            <a href="${article.url}" target="_blank" rel="noopener noreferrer" class="article-title hover:text-primary-600 transition-colors">
                ${escapeHtml(article.title)}
            </a>
        </h3>
        <p class="article-summary">${escapeHtml(summary)}</p>
        ${stocksHtml}
        <div class="mt-4 flex items-center justify-between">
            <a href="${article.url}" target="_blank" rel="noopener noreferrer"
               class="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1 transition-colors">
                Read more
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                </svg>
            </a>
        </div>
    `;

    return card;
}

// Filter by source
function filterBySource(source) {
    currentSource = source;
    currentOffset = 0;

    // Update active state
    document.querySelectorAll('.source-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.source === source || (source === 'all' && btn.dataset.source === 'all')) {
            btn.classList.add('active');
        }
    });

    loadArticles();
}

// Handle AI search
async function handleSearch() {
    const query = searchInput.value.trim();
    if (!query) {
        showToast('Please enter a search query', 'info');
        return;
    }

    // Show loading
    aiLoading.classList.remove('hidden');
    aiResponse.classList.add('hidden');

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query, max_articles: 100 }),
        });

        const data = await response.json();

        aiLoading.classList.add('hidden');

        if (data.success) {
            aiResponseText.textContent = data.response;
            aiResponse.classList.remove('hidden');
        } else {
            showToast(data.response || 'Search failed', 'error');
        }
    } catch (error) {
        aiLoading.classList.add('hidden');
        console.error('Search error:', error);
        showToast('Failed to perform search', 'error');
    }
}

// Handle manual scrape
async function handleScrape() {
    scrapeBtn.disabled = true;
    scrapeBtn.textContent = 'Scraping...';
    scrapeBtn.classList.add('pulse');

    try {
        const response = await fetch('/api/scrape', { method: 'POST' });
        const data = await response.json();

        showToast('Scrape started! New articles will appear shortly.', 'success');

        // Reload articles after a delay
        setTimeout(() => {
            currentOffset = 0;
            loadArticles();
            loadSources();
        }, 5000);

    } catch (error) {
        console.error('Scrape error:', error);
        showToast('Failed to start scrape', 'error');
    } finally {
        scrapeBtn.disabled = false;
        scrapeBtn.textContent = 'Refresh News';
        scrapeBtn.classList.remove('pulse');
    }
}

// Utility functions
function formatSourceName(source) {
    const names = {
        // Foundational Model Labs
        'openai': 'OpenAI',
        'anthropic_news': 'Anthropic',
        'anthropic_research': 'Anthropic Research',
        'deepmind': 'DeepMind',
        'google_ai': 'Google AI',
        'meta_ai': 'Meta AI',
        'mistral': 'Mistral',
        'cohere': 'Cohere',
        'xai': 'xAI',
        'ai21': 'AI21 Labs',
        'stability': 'Stability AI',
        'inflection': 'Inflection AI',
        // Forbes AI 50 B2B SaaS
        'huggingface': 'Hugging Face',
        'databricks': 'Databricks',
        'scale_ai': 'Scale AI',
        'writer': 'Writer',
        'jasper': 'Jasper',
        'runway': 'Runway',
        'elevenlabs': 'ElevenLabs',
        'perplexity': 'Perplexity',
        'glean': 'Glean',
        'cursor': 'Cursor',
        'together_ai': 'Together AI',
        'replicate': 'Replicate',
        'pinecone': 'Pinecone',
        'wandb': 'Weights & Biases',
        'harvey_ai': 'Harvey AI',
        'adept': 'Adept',
        'langchain': 'LangChain',
        'llamaindex': 'LlamaIndex',
        // News
        'verge_ai': 'The Verge',
        'techcrunch_ai': 'TechCrunch',
        'venturebeat_ai': 'VentureBeat',
        'mit_tech_ai': 'MIT Tech Review',
        'wired_ai': 'Wired',
        'ars_ai': 'Ars Technica',
    };
    return names[source] || source;
}

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffHours < 1) return 'Just now';
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    } catch {
        return dateString;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    // Remove after animation
    setTimeout(() => {
        toast.remove();
    }, 3000);
}
