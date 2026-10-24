/* ==========================================================================
   OtakuVault Global Script & Interactive UI Controller
   ========================================================================== */

// --- 1. Toast Notification System ---
function showToast(message, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = '⚡';
  if (type === 'success') icon = '✓';
  if (type === 'error') icon = '✕';
  if (type === 'info') icon = '★';

  toast.innerHTML = `<span style="font-size: 1.1rem;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);

  // Trigger enter animation
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  // Auto remove after 3.2s
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 3200);
}

// --- 2. Mobile Sidebar Navigation Drawer ---
function toggleMobileSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (!sidebar) return;

  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
  } else {
    sidebar.classList.add('open');
    if (overlay) overlay.classList.add('active');
  }
}

function closeMobileSidebar() {
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('active');
}

// --- 3. Quick Episode / Chapter Increment (+1) ---
async function quickIncrement(btnElement, entryId, medium = 'anime') {
  btnElement.disabled = true;
  const originalText = btnElement.innerHTML;
  btnElement.innerHTML = `<span>...</span>`;

  try {
    const response = await fetch(`/api/increment_progress/${entryId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();
    if (data.success) {
      const card = btnElement.closest('.media-card');
      if (card) {
        // Update progress counter
        const counterEl = card.querySelector('.progress-current');
        if (counterEl) counterEl.textContent = data.progress;

        // Update progress bar percentage
        const progressFill = card.querySelector('.progress-fill');
        if (progressFill && data.total > 0) {
          const pct = Math.min(100, Math.round((data.progress / data.total) * 100));
          progressFill.style.width = `${pct}%`;
        }

        // Update status badge if completed
        if (data.status === 'Completed') {
          const statusBadge = card.querySelector('.badge-status');
          if (statusBadge) {
            statusBadge.textContent = 'Completed';
            statusBadge.className = 'badge-status status-completed';
          }
        }

        // Update data attribute for instant sorting
        card.dataset.progress = data.progress;
      }

      const unit = medium === 'manga' ? 'Chapter' : 'Episode';
      showToast(`+1 ${unit} (${data.progress}${data.total > 0 ? '/' + data.total : ''})`, 'success');
    } else {
      showToast(data.error || 'Failed to update progress', 'error');
    }
  } catch (err) {
    console.error('Increment error:', err);
    showToast('Network error while updating progress', 'error');
  } finally {
    btnElement.disabled = false;
    btnElement.innerHTML = originalText;
  }
}

function handleIncrement(btnElement, medium = 'anime') {
  const card = btnElement.closest('.media-card');
  const entryId = card ? card.dataset.id : null;
  if (entryId) {
    quickIncrement(btnElement, entryId, medium);
  }
}

function openCardDetails(element, medium = 'anime') {
  const card = element.closest('.media-card');
  const title = card ? card.dataset.title : '';
  if (title) {
    openAnimeDetails(title, medium);
  }
}

function openCardEdit(element) {
  const card = element.closest('.media-card');
  if (!card) return;
  const entry = {
    id: card.dataset.id,
    title: card.dataset.title || '',
    progress: card.dataset.progress || 0,
    total: card.dataset.total || 0,
    score: card.dataset.score || 0,
    status: card.dataset.status || 'Watching'
  };
  openEditModal(entry);
}

// --- 4. Toggle Favorite (★) ---
async function toggleFavorite(buttonElement) {
  const entryId = buttonElement.dataset.id;
  try {
    const response = await fetch(`/toggle_favorite/${entryId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    if (data.success) {
      const isFav = data.is_favorite === 1;
      buttonElement.classList.toggle('active', isFav);
      showToast(isFav ? 'Added to Favorites ⭐' : 'Removed from Favorites', 'info');
    } else {
      showToast('Could not update favorite status', 'error');
    }
  } catch (err) {
    console.error(err);
    showToast('Failed to toggle favorite', 'error');
  }
}

// --- 5. Real-Time Library Search & Filter ---
function initLibrarySearch() {
  const searchInput = document.getElementById('librarySearchInput');
  if (!searchInput) return;

  searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase().trim();
    const cards = document.querySelectorAll('.media-grid .media-card');
    let visibleCount = 0;

    cards.forEach(card => {
      const title = (card.dataset.title || '').toLowerCase();
      if (!query || title.includes(query)) {
        card.style.display = 'flex';
        visibleCount++;
      } else {
        card.style.display = 'none';
      }
    });

    // Handle "no search results" message
    let noMatch = document.getElementById('noSearchMatchMsg');
    if (visibleCount === 0 && cards.length > 0) {
      if (!noMatch) {
        noMatch = document.createElement('div');
        noMatch.id = 'noSearchMatchMsg';
        noMatch.className = 'empty-state';
        noMatch.innerHTML = `
          <div class="empty-icon">🔍</div>
          <h3>No matching titles found</h3>
          <p>No results matching "${searchInput.value}". Clear the search to view all.</p>
        `;
        document.querySelector('.media-grid').appendChild(noMatch);
      }
      noMatch.style.display = 'flex';
    } else if (noMatch) {
      noMatch.style.display = 'none';
    }
  });
}

// --- 6. Library Sorting (Title, Score, Progress, Recent) ---
function initLibrarySorting() {
  const sortSelect = document.getElementById('librarySortSelect');
  if (!sortSelect) return;

  const grid = document.querySelector('.media-grid');
  if (!grid) return;

  const originalCards = Array.from(grid.querySelectorAll('.media-card'));

  sortSelect.addEventListener('change', () => {
    const val = sortSelect.value;
    const cards = Array.from(grid.querySelectorAll('.media-card'));

    if (val === 'recent') {
      originalCards.forEach(c => grid.appendChild(c));
      return;
    }

    cards.sort((a, b) => {
      if (val === 'title') {
        const titleA = (a.dataset.title || '').toLowerCase();
        const titleB = (b.dataset.title || '').toLowerCase();
        return titleA.localeCompare(titleB);
      } else if (val === 'score') {
        const scoreA = parseFloat(a.dataset.score || 0);
        const scoreB = parseFloat(b.dataset.score || 0);
        return scoreB - scoreA;
      } else if (val === 'progress') {
        const progA = parseInt(a.dataset.progress || 0, 10);
        const progB = parseInt(b.dataset.progress || 0, 10);
        return progB - progA;
      }
      return 0;
    });

    cards.forEach(c => grid.appendChild(c));
  });
}

// --- 7. Quick Edit Modal Controller ---
function openEditModal(entry) {
  const modal = document.getElementById('editEntryModal');
  if (!modal) return;

  document.getElementById('editForm').action = `/update_entry/${entry.id}`;
  document.getElementById('editEntryTitle').textContent = entry.title;
  document.getElementById('editProgressInput').value = entry.progress;
  document.getElementById('editTotalInput').value = entry.total || 0;
  document.getElementById('editScoreInput').value = entry.score || 0;
  
  const statusSelect = document.getElementById('editStatusSelect');
  if (statusSelect) {
    statusSelect.value = entry.status;
  }

  modal.classList.add('active');
}

function closeEditModal() {
  const modal = document.getElementById('editEntryModal');
  if (modal) modal.classList.remove('active');
}

// --- 8. Add Series Modal & Autocomplete Search ---
function openAddModal() {
  const modal = document.getElementById('addModal');
  if (!modal) return;
  modal.classList.add('active');
  const titleInput = document.getElementById('seriesTitleInput');
  if (titleInput) titleInput.focus();
}

function closeAddModal() {
  const modal = document.getElementById('addModal');
  if (modal) modal.classList.remove('active');
  const box = document.getElementById('suggestionsBox');
  if (box) box.style.display = 'none';
}

function initAddModalAutocomplete(medium = 'anime') {
  const titleInput = document.getElementById('seriesTitleInput');
  const suggestionsBox = document.getElementById('suggestionsBox');
  const totalInput = document.getElementById('seriesTotalInput');
  const imageInput = document.getElementById('seriesImageInput');
  const imagePreview = document.getElementById('seriesImagePreview');

  if (!titleInput || !suggestionsBox) return;

  let debounceTimer;

  titleInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = titleInput.value.trim();

    if (query.length < 2) {
      suggestionsBox.innerHTML = '';
      suggestionsBox.style.display = 'none';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search_anime?medium=${medium}&q=${encodeURIComponent(query)}`);
        const items = await res.json();

        suggestionsBox.innerHTML = '';
        if (!items || items.length === 0) {
          suggestionsBox.style.display = 'none';
          return;
        }

        items.forEach(item => {
          const row = document.createElement('div');
          row.className = 'autocomplete-item';
          const totalLabel = medium === 'manga' ? 'chapters' : 'eps';
          const count = item.total > 0 ? `${item.total} ${totalLabel}` : `? ${totalLabel}`;

          row.innerHTML = `
            <img src="${item.cover || 'https://placehold.co/40x55/1b1f2e/ffffff?text=?'}" class="autocomplete-thumb" alt="">
            <div class="autocomplete-details">
              <div class="autocomplete-title">${item.title}</div>
              <div class="autocomplete-meta">${count}</div>
            </div>
          `;

          row.addEventListener('click', () => {
            titleInput.value = item.title;
            if (totalInput) totalInput.value = item.total || 0;
            if (imageInput) imageInput.value = item.cover || '';
            if (imagePreview && item.cover) {
              imagePreview.src = item.cover;
              imagePreview.style.display = 'block';
            }
            suggestionsBox.style.display = 'none';
          });

          suggestionsBox.appendChild(row);
        });

        suggestionsBox.style.display = 'block';
      } catch (err) {
        console.error('Autocomplete fetch error:', err);
      }
    }, 280);
  });

  // Close suggestions on outside click
  document.addEventListener('click', (e) => {
    if (!titleInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
      suggestionsBox.style.display = 'none';
    }
  });

  // Update preview when typing custom image URL
  if (imageInput && imagePreview) {
    imageInput.addEventListener('input', () => {
      const url = imageInput.value.trim();
      if (url) {
        imagePreview.src = url;
        imagePreview.style.display = 'block';
      } else {
        imagePreview.style.display = 'none';
      }
    });
  }
}

// --- 8b. Character Modal Autocomplete Search (AniList API) ---
function initCharacterModalAutocomplete() {
  const nameInput = document.getElementById('charNameInput');
  const suggestionsBox = document.getElementById('charSuggestionsBox');
  const originInput = document.getElementById('charOriginInput');
  const imageInput = document.getElementById('charImageInput');
  const imagePreview = document.getElementById('charImagePreview');

  if (!nameInput || !suggestionsBox) return;

  let debounceTimer;

  nameInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = nameInput.value.trim();

    if (query.length < 2) {
      suggestionsBox.innerHTML = '';
      suggestionsBox.style.display = 'none';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search_character?q=${encodeURIComponent(query)}`);
        const items = await res.json();

        suggestionsBox.innerHTML = '';
        if (!items || items.length === 0) {
          suggestionsBox.style.display = 'none';
          return;
        }

        items.forEach(item => {
          const row = document.createElement('div');
          row.className = 'autocomplete-item';

          row.innerHTML = `
            <img src="${item.image || 'https://placehold.co/40x55/1b1f2e/ffffff?text=?'}" class="autocomplete-thumb" alt="">
            <div class="autocomplete-details">
              <div class="autocomplete-title">${item.name}</div>
              <div class="autocomplete-meta">${item.origin ? item.origin : 'Anime / Manga Character'}</div>
            </div>
          `;

          row.addEventListener('click', () => {
            nameInput.value = item.name;
            if (originInput && item.origin) {
              originInput.value = item.origin;
            }
            if (imageInput && item.image) {
              imageInput.value = item.image;
            }
            if (imagePreview && item.image) {
              imagePreview.src = item.image;
              imagePreview.style.display = 'block';
            }
            suggestionsBox.style.display = 'none';
          });

          suggestionsBox.appendChild(row);
        });

        suggestionsBox.style.display = 'block';
      } catch (err) {
        console.error('Character autocomplete fetch error:', err);
      }
    }, 280);
  });

  // Close suggestions on outside click
  document.addEventListener('click', (e) => {
    if (!nameInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
      suggestionsBox.style.display = 'none';
    }
  });
}

// Global window click to close modals when clicking backdrop
window.addEventListener('click', (e) => {
  const addModal = document.getElementById('addModal');
  const editModal = document.getElementById('editEntryModal');
  const charModal = document.getElementById('addCharModal');
  const detailsModal = document.getElementById('animeDetailsModal');

  if (e.target === addModal) closeAddModal();
  if (e.target === editModal) closeEditModal();
  if (e.target === charModal) closeCharModal();
  if (e.target === detailsModal) closeAnimeDetails();
});

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initLibrarySearch();
  initLibrarySorting();
});


// --- 9. Anime Details & Where to Watch Modal (AniList API) ---
function closeAnimeDetails() {
  const modal = document.getElementById('animeDetailsModal');
  if (modal) {
    modal.classList.remove('active');
  }
}

async function openAnimeDetails(title, medium = 'anime') {
  let modal = document.getElementById('animeDetailsModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'animeDetailsModal';
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="modal-dialog modal-dialog-large">
        <div class="details-hero" id="detailsHero">
          <div class="details-hero-overlay"></div>
          <button type="button" class="details-close-btn" onclick="closeAnimeDetails()">✕</button>
        </div>
        <div class="details-body" id="detailsBody">
          <!-- Injected dynamically -->
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeAnimeDetails();
    });
  }

  const hero = document.getElementById('detailsHero');
  const body = document.getElementById('detailsBody');

  hero.style.backgroundImage = 'none';
  body.innerHTML = `
    <div style="text-align: center; padding: 60px 20px;">
      <div style="font-size: 2.2rem; margin-bottom: 12px; animation: spin 1s infinite linear;">⚡</div>
      <h3 style="font-family: var(--font-display); color: #fff; margin-bottom: 6px;">Fetching Anime Details & Streaming Sources...</h3>
      <p style="color: var(--text-muted); font-size: 0.9rem;">Connecting to AniList for "${title}"</p>
    </div>
  `;

  modal.classList.add('active');

  try {
    const res = await fetch(`/api/anime_details?title=${encodeURIComponent(title)}&medium=${medium}`);
    const result = await res.json();

    if (!result.success || !result.data) {
      body.innerHTML = `
        <div style="text-align: center; padding: 50px 20px;">
          <div style="font-size: 2.5rem; margin-bottom: 12px; color: #ef4444;">✕</div>
          <h3 style="color: #fff; margin-bottom: 8px;">No details found on AniList</h3>
          <p style="color: var(--text-muted); font-size: 0.92rem; margin-bottom: 20px;">
            Could not find an exact match for "${title}".
          </p>
          <a href="https://anilist.co/search/anime?search=${encodeURIComponent(title)}" target="_blank" rel="noopener noreferrer" class="btn btn-anilist">
            <span>Search AniList Directly</span> ↗
          </a>
        </div>
      `;
      return;
    }

    const d = result.data;

    // Set hero banner if available
    if (d.banner) {
      hero.style.backgroundImage = `url('${d.banner}')`;
    } else if (d.cover) {
      hero.style.backgroundImage = `url('${d.cover}')`;
    }

    // Build streaming badges
    let streamingHtml = '';
    if (d.streamingLinks && d.streamingLinks.length > 0) {
      streamingHtml = d.streamingLinks.map(s => `
        <a href="${s.url}" target="_blank" rel="noopener noreferrer" class="stream-card-link" title="Watch on ${s.site}">
          <span class="stream-dot" style="background-color: ${s.color || '#ff3366'};"></span>
          <span>${s.site}</span>
          <span class="stream-arrow">↗</span>
        </a>
      `).join('');
    } else {
      streamingHtml = `
        <div style="font-size: 0.88rem; color: var(--text-muted); background: rgba(255,255,255,0.03); padding: 12px 16px; border-radius: 8px; width: 100%;">
          No direct streaming partners listed on AniList for this title. You can check the official AniList page or distributors below.
        </div>
      `;
    }

    // Other links (e.g. Official Site)
    let otherLinksHtml = '';
    if (d.otherLinks && d.otherLinks.length > 0) {
      otherLinksHtml = d.otherLinks.map(o => `
        <a href="${o.url}" target="_blank" rel="noopener noreferrer" class="filter-pill" style="font-size: 0.8rem;">
          <span>${o.site}</span> ↗
        </a>
      `).join('');
    }

    // Genres pills
    const genresHtml = (d.genres || []).map(g => `<span class="details-chip">${g}</span>`).join('');

    body.innerHTML = `
      <div class="details-header-row">
        <img src="${d.cover || 'https://placehold.co/130x180/1a1f2e/ffffff?text=' + encodeURIComponent(d.title)}" class="details-poster" alt="${d.title}">
        
        <div class="details-title-box">
          <h2 class="details-main-title">${d.title}</h2>
          ${d.romaji && d.romaji !== d.title ? `<div class="details-romaji">${d.romaji}</div>` : ''}
          
          <div class="details-chips-row">
            ${d.score ? `<span class="details-chip" style="color: #ffb703; font-weight: 700;">★ ${d.score}/10</span>` : ''}
            ${d.format ? `<span class="details-chip">${d.format}</span>` : ''}
            ${d.episodes ? `<span class="details-chip">${d.episodes} eps</span>` : (d.chapters ? `<span class="details-chip">${d.chapters} chs</span>` : '')}
            ${d.status ? `<span class="details-chip" style="color: var(--status-watching);">${d.status}</span>` : ''}
            ${d.studios && d.studios.length > 0 ? `<span class="details-chip">🏛️ ${d.studios[0]}</span>` : ''}
          </div>
        </div>
      </div>

      <!-- Where to Watch Streaming Section -->
      <div class="watch-section">
        <div class="watch-section-title">
          <span>📺</span> Where to Watch / Streaming Platforms
        </div>
        <div class="streaming-grid">
          ${streamingHtml}
        </div>
      </div>

      <!-- Action Buttons: AniList & Trailer -->
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
        <a href="${d.siteUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-anilist">
          <span>View on AniList</span> ↗
        </a>
        ${d.trailerUrl ? `
          <a href="${d.trailerUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">
            <span>▶ Watch Trailer</span>
          </a>
        ` : ''}
        ${otherLinksHtml}
      </div>

      <!-- Genres -->
      ${genresHtml ? `
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${genresHtml}
        </div>
      ` : ''}

      <!-- Synopsis -->
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <h4 style="font-family: var(--font-display); font-size: 1rem; color: #fff;">Synopsis</h4>
        <div style="font-size: 0.9rem; color: var(--text-muted); line-height: 1.6; white-space: pre-line; background: rgba(255,255,255,0.02); padding: 14px 18px; border-radius: var(--radius-md); border: 1px solid var(--border);">
          ${d.description}
        </div>
      </div>
    `;

  } catch (err) {
    console.error("Anime details error:", err);
    body.innerHTML = `
      <div style="text-align: center; padding: 50px 20px;">
        <div style="font-size: 2.5rem; margin-bottom: 12px; color: #ef4444;">✕</div>
        <h3 style="color: #fff; margin-bottom: 8px;">Network Error</h3>
        <p style="color: var(--text-muted); font-size: 0.92rem; margin-bottom: 20px;">
          Failed to fetch anime details from AniList API.
        </p>
        <button class="btn" onclick="openAnimeDetails('${title}', '${medium}')">Try Again</button>
      </div>
    `;
  }
}
