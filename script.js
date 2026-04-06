let allReleases = []; // Store the full collection here
let sortDirection = 'asc';
let lastSortValue = 'added';

// ---------------- FETCH ----------------
async function fetchCollection() {
    const username = document.getElementById('usernameInput').value;
    const resultsArea = document.getElementById('resultsArea');
    if (!username) return alert("Please enter a username");

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

// ---------------- DISPLAY ----------------
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
                src="https://via.placeholder.com/150"
                data-src="${release.cover_image}"
                alt="${release.title}"
                class="lazy-image"
                onerror="this.src='https://via.placeholder.com/150'"
            >
            <div id="mood-tag-${release.id}" class="card-mood-tag"></div>
        `;

        resultsArea.appendChild(card);
    });

    // 🔥 Activate lazy loading AFTER rendering
    initImageLazyLoad();
    loadMoodTags();
}

// ---------------- MOOD TAGS ON CARDS ----------------
async function loadMoodTags() {
    // Fetch mood tags for every album currently in allReleases
    // and paint the badge onto the card if one exists
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

// ---------------- FILTERS ----------------
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

    // Mood filter from sidebar
    const activeMoodFilter = document.querySelector('.mood-filter-btn.selected');
    if (activeMoodFilter) {
        const filterMood = activeMoodFilter.dataset.mood;
        filtered = filtered.filter(item => {
            const tagEl = document.getElementById(`mood-tag-${item.basic_information.id}`);
            if (!tagEl) return false;
            // Check if ANY badge on this card matches the filter
            return Array.from(tagEl.querySelectorAll('.mood-badge'))
                .some(badge => badge.textContent === filterMood);
        });
    }

    // Sort using lastSortValue and sortDirection instead of the old select
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
            comparison = a._index - b._index;
        }
        // 'added' keeps original order (comparison stays 0)

        return sortDirection === 'asc' ? comparison : -comparison;
    });

    displayResults(filtered);
}

function handleSortClick(btn) {
    const newSort = btn.dataset.sort;

    if (newSort === lastSortValue) {
        // Same option clicked — toggle direction
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        // New option — reset to ascending
        sortDirection = 'asc';
        lastSortValue = newSort;
    }

    // Update arrow indicators
    document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.remove('active');
        b.querySelector('.sort-arrow').textContent = '';
    });
    btn.classList.add('active');
    btn.querySelector('.sort-arrow').textContent = sortDirection === 'asc' ? '↑' : '↓';

    applyFilters();
}

// ---------------- SIDEBAR: MOOD FILTER ----------------
function handleMoodFilterClick(btn) {
    const already = btn.classList.contains('selected');

    // Deselect all
    document.querySelectorAll('.mood-filter-btn').forEach(b => b.classList.remove('selected'));

    if (!already) {
        btn.classList.add('selected');
    }

    applyFilters();
}

// ---------------- SIDEBAR: RECOMMENDATION ----------------
async function getRecommendation() {
    const moodSelect = document.getElementById('recommendMoodSelect');
    const weatherSelect = document.getElementById('recommendWeatherSelect');
    const resultArea = document.getElementById('recommendationResult');

    const mood = moodSelect.value;
    const weather = weatherSelect.value;

    resultArea.innerHTML = '<p>Finding the perfect record...</p>';

    try {
        const params = new URLSearchParams({ mood });
        if (weather) params.append('weather', weather);

        const res = await fetch(`http://localhost:8000/api/recommend/?${params}`);
        const data = await res.json();

        if (data.recommendation) {
            const r = data.recommendation;
            resultArea.innerHTML = `
                <div class="recommendation-card">
                    <img src="${r.cover_url}" alt="${r.title}"
                         onerror="this.src='https://via.placeholder.com/150'">
                    <div class="recommendation-info">
                        <p class="rec-title">${r.title}</p>
                        <p class="rec-artist">${r.artist}</p>
                        ${r.mood_tag ? `<span class="card-mood-tag mood-${r.mood_tag}">${r.mood_tag}</span>` : ''}
                    </div>
                </div>
            `;
        } else {
            resultArea.innerHTML = `<p class="rec-empty">${data.message || 'No recommendation available.'}</p>`;
        }
    } catch (e) {
        resultArea.innerHTML = '<p>Could not fetch recommendation.</p>';
    }
}

// ---------------- LAZY IMAGE LOADING ----------------
function initImageLazyLoad() {
    const images = document.querySelectorAll("img[data-src]");

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;

                img.onload = () => {
                    img.classList.add("loaded");
                };

                img.src = img.dataset.src; // load real image
                img.removeAttribute("data-src");

                obs.unobserve(img);
            }
        });
    }, {
        root: document.getElementById('resultsArea'), // IMPORTANT for inner scroll
        threshold: 0.1
    });

    images.forEach(img => observer.observe(img));
}

// ---------------- ENTER KEY ----------------
document.getElementById('usernameInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        fetchCollection();
    }
});

// ---------------- SESSION STATE ----------------
let currentSessionData = {
    album: null,
    preEmotion: "",
    timeA: 0,
    timeB: 0,
    postEmotion: ""
};

let activeInterval = null;
let runningSide = null;

// ---------------- MODAL 1 ----------------
async function openModal(release) {
    currentSessionData.album = release;
    
    document.getElementById('modalAlbumTitle').innerText = release.title;
    document.getElementById('modalAlbumCover').src = release.cover_image;
    document.getElementById('preEmotion').selectedIndex = 0;
    document.getElementById('modalGenres').innerText = 'Loading...';
    document.getElementById('modalYear').innerText = '';
    document.getElementById('modalTracklist').innerHTML = '';
    
    resetTimers();
    
    const modal = document.getElementById('preSessionModal');
    if (modal) {
        modal.style.display = 'flex';
    }

    try {
        const res = await fetch(`http://localhost:8000/api/release/${release.id}/`);
        const details = await res.json();

        document.getElementById('modalGenres').innerText =
            [...(details.genres || []), ...(details.styles || [])].join(', ') || 'N/A';

        document.getElementById('modalYear').innerText = details.year || 'N/A';

        const tracklistEl = document.getElementById('modalTracklist');
        tracklistEl.innerHTML = (details.tracklist || []).map(track => `
            <div class="track-row">
                <span class="track-position">${track.position}</span>
                <span class="track-title">${track.title}</span>
                <span class="track-duration">${track.duration}</span>
            </div>
        `).join('');

    } catch (e) {
        document.getElementById('modalGenres').innerText = 'Could not load details.';
    }
}

// ---------------- MODAL 2 ----------------
function startActiveSession() {
    currentSessionData.preEmotion = document.getElementById('preEmotion').value;
    
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

// ---------------- MODAL 3 ----------------
function endActiveSession() {
    clearInterval(activeInterval);
    runningSide = null;
    document.getElementById('recordGraphic').classList.remove('spinning');

    document.getElementById('activeSessionModal').style.display = 'none';
    
    const totalSeconds = currentSessionData.timeA + currentSessionData.timeB;
    document.getElementById('totalTimeDisplay').innerText = formatTime(totalSeconds);
    
    document.getElementById('postSessionModal').style.display = 'flex';
}

// ---------------- SAVE ----------------
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
                renderMoodTags(id, tagData.mood_tags);  // ← was inline, now shared helper
            }
            closeAllModals();
        }
    } catch(err) {
        console.error(err);
    }
}

// ---------------- HELPERS ----------------
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
