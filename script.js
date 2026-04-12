// ===================== APP STATE =====================
let currentUser = null; // { id, username, discogs_username }
let allReleases = [];
let sortDirection = 'asc';
let lastSortValue = 'added';
let recommendedFilterIds = null; // null = no filter active

// ===================== LOGIN =====================
async function handleLogin() {
    const input = document.getElementById('loginUsernameInput');
    const errorEl = document.getElementById('loginError');
    const btn = document.getElementById('loginBtn');
    const btnText = document.getElementById('loginBtnText');
    const spinner = document.getElementById('loginBtnSpinner');

    const username = input.value.trim();

    // Clear error state
    input.classList.remove('error');
    errorEl.style.display = 'none';

    if (!username) {
        showLoginError('Please enter your Discogs username.');
        return;
    }

    // Loading state
    btn.disabled = true;
    btnText.textContent = 'Loading...';
    spinner.style.display = 'inline';

    try {
        const res = await fetch('http://localhost:8000/api/login/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ discogs_username: username })
        });

        const data = await res.json();

        if (!res.ok) {
            showLoginError(data.error || 'Could not connect. Is the server running?');
            return;
        }

        // Success — store user and unlock app
        currentUser = data.user;
        unlockApp(currentUser.discogs_username);

        // Directly store the releases from the login response and display them
        allReleases = data.releases;
        applyFilters();

    } catch (err) {
        showLoginError('Could not connect to server. Make sure Django is running.');
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Dig In';
        spinner.style.display = 'none';
    }
}

function showLoginError(msg) {
    const input = document.getElementById('loginUsernameInput');
    const errorEl = document.getElementById('loginError');
    input.classList.add('error');
    errorEl.textContent = msg;
    errorEl.style.display = 'block';
}

function unlockApp(username) {
    // Hide login overlay
    const overlay = document.getElementById('loginModal');
    overlay.classList.add('hidden');

    // Remove blur from app
    const app = document.getElementById('appContainer');
    app.classList.remove('app-locked');
    app.classList.add('app-unlocked');

    // Show username in header
    document.getElementById('headerUsernameDisplay').textContent = username;
    document.getElementById('headerUser').style.display = 'flex';

    // Remove overlay from DOM after transition
    setTimeout(() => overlay.remove(), 500);
}

// Replace the existing handleLogout() with this:
function handleLogout() {
    document.getElementById('logoutConfirmModal').style.display = 'flex';
}

function closeLogoutModal() {
    document.getElementById('logoutConfirmModal').style.display = 'none';
}

// Rename the old logout logic to confirmLogout():
function confirmLogout() {
    currentUser = null;
    allReleases = [];
    document.getElementById('resultsArea').innerHTML = '';
    location.reload();
}

// ===================== FETCH COLLECTION =====================
async function fetchCollection(username) {
    const resultsArea = document.getElementById('resultsArea');
    resultsArea.innerHTML = '<p>Digging through the crates...</p>';

    try {
        const response = await fetch(`http://localhost:8000/api/collection/${username}`);
        const data = await response.json();

        if (data.releases) {
            allReleases = data.releases;
            applyFilters();
        } else {
            resultsArea.innerHTML = '<p>No records found.</p>';
        }
    } catch (error) {
        resultsArea.innerHTML = '<p>Could not connect to the server.</p>';
    }
}

// ===================== DISPLAY =====================
function displayResults(releases) {
    const resultsArea = document.getElementById('resultsArea');
    resultsArea.innerHTML = '';

    releases.forEach(item => {
        const release = item.basic_information;
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.discogsId = release.id;

        card.onclick = () => openModal(release);

        card.innerHTML = `
            <img 
                src="https://placehold.co/150"
                data-src="${release.cover_image}"
                alt="${release.title}"
                class="lazy-image"
                onerror="this.src='https://placehold.co/150'"
            >
            <div id="mood-tag-${release.id}" class="card-mood-tag"></div>
        `;

        resultsArea.appendChild(card);
    });

    initImageLazyLoad();
    loadMoodTags();
}

// ===================== MOOD TAGS =====================
async function loadMoodTags() {
    for (const item of allReleases) {
        const id = item.basic_information.id;
        try {
            const res = await fetch(`http://localhost:8000/api/mood-tags/?discogs_id=${id}`);
            const data = await res.json();
            if (data.mood_tags && data.mood_tags.length > 0) {
                renderMoodTags(id, data.mood_tags);
            }
        } catch (_) {}
    }
}

function renderMoodTags(discogsId, moodTags) {
    const el = document.getElementById(`mood-tag-${discogsId}`);
    if (!el) return;
    el.innerHTML = moodTags.map(tag =>
        `<span class="mood-badge mood-${tag.emotion}">${tag.emotion}</span>`
    ).join('');
}

// ===================== FILTERS =====================
function applyFilters() {
    let filtered = [...allReleases];

    const searchInput = document.getElementById('searchInput');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : "";
    if (searchTerm) {
        filtered = filtered.filter(item => {
            const info = item.basic_information;
            const title = info.title.toLowerCase();
            const artist = info.artists.map(a => a.name).join(' ').toLowerCase();
            return title.includes(searchTerm) || artist.includes(searchTerm);
        });
    }

    const activeMoodFilter = document.querySelector('.mood-filter-btn.selected');
    if (activeMoodFilter) {
        const filterMood = activeMoodFilter.dataset.mood;
        filtered = filtered.filter(item => {
            const tagEl = document.getElementById(`mood-tag-${item.basic_information.id}`);
            if (!tagEl) return false;
            return Array.from(tagEl.querySelectorAll('.mood-badge'))
                .some(badge => badge.textContent === filterMood);
        });
    }
    // Recommendation filter
    if (recommendedFilterIds !== null) {
        filtered = filtered.filter(item =>
            recommendedFilterIds.includes(item.basic_information.id)
        );
    }

    filtered.sort((a, b) => {
        const infoA = a.basic_information;
        const infoB = b.basic_information;
        let comparison = 0;

        if (lastSortValue === 'artist') {
            comparison = infoA.artists[0].name.localeCompare(infoB.artists[0].name);
        } else if (lastSortValue === 'title') {
            comparison = infoA.title.localeCompare(infoB.title);
        } else if (lastSortValue === 'year') {
            comparison = (infoA.year || 0) - (infoB.year || 0);
        } else if (lastSortValue === 'added') {
            const dateA = new Date(a.date_added);
            const dateB = new Date(b.date_added);
            comparison = dateB - dateA;
        }

        return sortDirection === 'asc' ? comparison : -comparison;
    });
    
    displayResults(filtered);
}

function handleSortClick(btn) {
    const newSort = btn.dataset.sort;

    if (newSort === lastSortValue) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortDirection = 'asc';
        lastSortValue = newSort;
    }

    document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.remove('active');
        b.querySelector('.sort-arrow').textContent = '';
    });
    btn.classList.add('active');
    btn.querySelector('.sort-arrow').textContent = sortDirection === 'asc' ? '↑' : '↓';

    applyFilters();
}

// ===================== MOOD FILTER =====================
function handleMoodFilterClick(btn) {
    const already = btn.classList.contains('selected');
    document.querySelectorAll('.mood-filter-btn').forEach(b => b.classList.remove('selected'));
    if (!already) btn.classList.add('selected');
    applyFilters();
}

// ===================== RECOMMENDATION =====================
async function getRecommendation() {
    const mood     = document.getElementById('recommendMoodSelect').value;
    const weather = document.getElementById('recommendWeatherSelect').value || null;
    const resultArea = document.getElementById('recommendationResult');

    resultArea.innerHTML = '<p>Finding the perfect record...</p>';

    try {
        // Send the current collection so the recommender can score
        // albums directly without needing them pre-saved in the DB
        const collectionSnapshot = allReleases.map(item => ({
            discogs_id: item.basic_information.id,
            title:      item.basic_information.title,
            artist:     item.basic_information.artists?.[0]?.name || '',
            cover_url:  item.basic_information.cover_image,
            genres:     item.basic_information.genres  || [],
            styles:     item.basic_information.styles  || [],
        }));

        const body = {
            mood,
            weather:    weather || null,
            user_id:    currentUser?.id || null,
            collection: collectionSnapshot,
        };

        const res  = await fetch('http://localhost:8000/api/recommend/', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(body),
        });
        const data = await res.json();

        if (data.recommendation) {
            const r = data.recommendation;
            recommendedFilterIds = [r.discogs_id];
            applyFilters();

            resultArea.innerHTML = `
                <div class="recommendation-card">
                    <img src="${r.cover_url}" alt="${r.title}"
                         onerror="this.src='https://placehold.co/150'">
                    <div class="recommendation-info">
                        <p class="rec-title">${r.title}</p>
                        <p class="rec-artist">${r.artist}</p>
                    </div>
                </div>
                ${r.explanation ? `<p class="rec-explanation">${r.explanation}</p>` : ''}
                <button class="rec-clear-btn" onclick="clearRecommendationFilter()">
                    ✕ Clear filter
                </button>
            `;
        } else {
            resultArea.innerHTML = `<p class="rec-empty">${data.message || 'No recommendation available.'}</p>`;
        }
    } catch (e) {
        resultArea.innerHTML = '<p>Could not fetch recommendation.</p>';
    }
}

function clearRecommendationFilter() {
    recommendedFilterIds = null;
    applyFilters();
    document.getElementById('recommendationResult').innerHTML = '';
}

// ===================== LAZY IMAGE LOAD =====================
function initImageLazyLoad() {
    const images = document.querySelectorAll("img[data-src]");

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.onload = () => img.classList.add("loaded");
                img.src = img.dataset.src;
                img.removeAttribute("data-src");
                obs.unobserve(img);
            }
        });
    }, {
        root: document.getElementById('resultsArea'),
        threshold: 0.1
    });

    images.forEach(img => observer.observe(img));
}

// ===================== ENTER KEY on login =====================
document.getElementById('loginUsernameInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleLogin();
});

// ===================== SESSION STATE =====================
let currentSessionData = {
    album: null,
    preEmotion: "",
    weather: "",
    timeA: 0,
    timeB: 0,
    postEmotion: ""
};

let activeInterval = null;
let runningSide = null;

// ===================== MODAL 1 =====================
// Replace openModal() — populate the new thumb fields too
async function openModal(release) {
    currentSessionData.album = release;

    // Step 1 fields
    document.getElementById('modalAlbumTitle').innerText = release.title;
    document.getElementById('modalAlbumTitleThumb').innerText = release.title;
    document.getElementById('modalAlbumCover').src = release.cover_image;
    document.getElementById('modalAlbumCoverThumb').src = release.cover_image;
    document.getElementById('modalAlbumArtist').innerText = release.artists.map(a => a.name).join(', ');
    document.getElementById('modalGenres').innerHTML = '<p class="pre-artist">Loading...</p>';
    document.getElementById('modalYear').innerText = '';
    document.getElementById('modalTracklist').innerHTML = '';

    // Always show Step 1, hide Step 2
    document.getElementById('preStep1').style.display = 'block';
    document.getElementById('preStep2').style.display = 'none';
    document.querySelectorAll('input[name="preEmotionRadio"]').forEach(r => {
        r.checked = r.value === 'neutral';
    });
    document.querySelectorAll('input[name="weatherRadio"]').forEach(r => {
        r.checked = r.value === '';
    });

    resetTimers();
    document.getElementById('preSessionModal').style.display = 'flex';

    try {
        const res = await fetch(`http://localhost:8000/api/release/${release.id}/`);
        const details = await res.json();

        // Year badge
        document.getElementById('modalYear').innerText = details.year || '';
        // Update the thumb subtitle once year is loaded
        document.getElementById('modalAlbumSubThumb').innerText =
            [release.artists.map(a => a.name).join(', '), details.year].filter(Boolean).join(' · ');

        // Genre pills
        const allGenres = [...(details.genres || []), ...(details.styles || [])];
        const genresEl = document.getElementById('modalGenres');
        genresEl.innerHTML = allGenres.length
            ? allGenres.map(g => `<span class="genre-pill">${g}</span>`).join('')
            : '<p class="pre-artist">N/A</p>';

        // Tracklist rows
        const tracklistEl = document.getElementById('modalTracklist');
        tracklistEl.innerHTML = (details.tracklist || []).map(track => `
            <div class="track-row">
                <span class="track-position">${track.position}</span>
                <span class="track-title">${track.title}</span>
                <span class="track-duration">${track.duration}</span>
            </div>
        `).join('');

    } catch (e) {
        document.getElementById('modalGenres').innerHTML = '<p class="pre-artist">Could not load details.</p>';
    }
}

// New: go to mood step
function goToMoodStep() {
    document.getElementById('preStep1').style.display = 'none';
    document.getElementById('preStep2').style.display = 'block';
}

// New: go back to details step
function backToDetails() {
    document.getElementById('preStep2').style.display = 'none';
    document.getElementById('preStep1').style.display = 'block';
}

// ===================== MODAL 2 =====================
// Replace startActiveSession() — read from radio buttons instead of <select>
function startActiveSession() {
    const selected = document.querySelector('input[name="preEmotionRadio"]:checked');
    currentSessionData.preEmotion = selected ? selected.value : 'neutral';

    const selectedWeather = document.querySelector('input[name="weatherRadio"]:checked');
    currentSessionData.weather = selectedWeather ? selectedWeather.value : '';

    document.getElementById('preSessionModal').style.display = 'none';
    document.getElementById('activeAlbumTitle').innerText = currentSessionData.album.title;
    document.getElementById('activeSessionModal').style.display = 'flex';
}

function toggleTimer(side) {
    const btn = document.getElementById(`btn${side}`);
    const record = document.getElementById('recordGraphic');

    if (runningSide === side) {
        clearInterval(activeInterval);
        runningSide = null;
        btn.innerText = "Resume";
        record.classList.remove('spinning');
        return;
    }

    if (runningSide && runningSide !== side) {
        clearInterval(activeInterval);
        document.getElementById(`btn${runningSide}`).innerText = "Start";
    }

    runningSide = side;
    btn.innerText = "Pause";
    record.classList.add('spinning');

    activeInterval = setInterval(() => {
        if (side === 'A') {
            currentSessionData.timeA++;
            document.getElementById('timeA').innerText = formatTime(currentSessionData.timeA);
        } else {
            currentSessionData.timeB++;
            document.getElementById('timeB').innerText = formatTime(currentSessionData.timeB);
        }
    }, 1000);
}

// ===================== MODAL 3 =====================
function endActiveSession() {
    clearInterval(activeInterval);
    runningSide = null;
    document.getElementById('recordGraphic').classList.remove('spinning');

    document.getElementById('activeSessionModal').style.display = 'none';
    
    const totalSeconds = currentSessionData.timeA + currentSessionData.timeB;
    document.getElementById('totalTimeDisplay').innerText = formatTime(totalSeconds);
    
    document.getElementById('postSessionModal').style.display = 'flex';
}

// ===================== SAVE SESSION =====================
async function submitFinalSession() {
    currentSessionData.postEmotion = document.getElementById('postEmotion').value;
    
    const payload = {
        album_id: currentSessionData.album.id,
        title: currentSessionData.album.title,
        artist: currentSessionData.album.artists[0].name,
        cover_url: currentSessionData.album.cover_image,
        pre_emotion: currentSessionData.preEmotion,
        post_emotion: currentSessionData.postEmotion,
        side_a_duration: currentSessionData.timeA,
        side_b_duration: currentSessionData.timeB,
        month: new Date().getMonth() + 1,
        weather: currentSessionData.weather,
        user_id: currentUser ? currentUser.id : null,
    };

    try {
        const response = await fetch('http://localhost:8000/api/log-session/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const id = currentSessionData.album.id;
            const tagRes = await fetch(`http://localhost:8000/api/mood-tags/?discogs_id=${id}`);
            const tagData = await tagRes.json();
            if (tagData.mood_tags && tagData.mood_tags.length > 0) {
                renderMoodTags(id, tagData.mood_tags);
            }
            closeAllModals();
        }
    } catch(err) {
        console.error(err);
    }
}

// ===================== HELPERS =====================
function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function resetTimers() {
    clearInterval(activeInterval);
    runningSide = null;
    currentSessionData.timeA = 0;
    currentSessionData.timeB = 0;
    document.getElementById('timeA').innerText = "00:00";
    document.getElementById('timeB').innerText = "00:00";
    document.getElementById('btnA').innerText = "Start";
    document.getElementById('btnB').innerText = "Start";
    document.getElementById('recordGraphic').classList.remove('spinning');
}

function closeAllModals() {
    document.getElementById('preSessionModal').style.display = 'none';
    document.getElementById('activeSessionModal').style.display = 'none';
    document.getElementById('postSessionModal').style.display = 'none';
    resetTimers();
}

document.getElementById('preSessionModal').addEventListener('click', function(e) {
    if (e.target === this) closeAllModals();
});