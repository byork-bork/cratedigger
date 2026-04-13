// ===================== APP STATE =====================
let currentUser = null; // { id, username, discogs_username }
let allReleases = [];
let sortDirection = 'asc';
let lastSortValue = 'added';

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

// ===================== RECOMMENDATION MODAL =====================

// Holds the last recommendation result so startSessionFromRecommendation can use it
let lastRecommendation = null;   // { discogs_id, title, artist, cover_url, explanation, year? }
let lastRecommendMood    = null;
let lastRecommendWeather = null;

function openRecommendModal() {
    // Reset to step 1 each time
    document.getElementById('recStep1').style.display = 'block';
    document.getElementById('recStep2').style.display = 'none';
    document.getElementById('recStep3').style.display = 'none';
    document.getElementById('recommendMoodSelect').value    = 'neutral';
    document.getElementById('recommendWeatherSelect').value = '';
    document.getElementById('recommendModal').style.display = 'flex';
}

function closeRecommendModal() {
    document.getElementById('recommendModal').style.display = 'none';
}

async function getRecommendation() {
    const mood    = document.getElementById('recommendMoodSelect').value;
    const weather = document.getElementById('recommendWeatherSelect').value || null;

    // Save for session logging later
    lastRecommendMood    = mood;
    lastRecommendWeather = weather;

    // Slide to loading state
    document.getElementById('recStep1').style.display = 'none';
    document.getElementById('recStep2').style.display = 'block';
    document.getElementById('recStep3').style.display = 'none';

    try {
        const collectionSnapshot = allReleases.map(item => ({
            discogs_id: item.basic_information.id,
            title:      item.basic_information.title,
            artist:     item.basic_information.artists?.[0]?.name || '',
            cover_url:  item.basic_information.cover_image,
            genres:     item.basic_information.genres  || [],
            styles:     item.basic_information.styles  || [],
        }));

        const res  = await fetch('http://localhost:8000/api/recommend/', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                mood,
                weather:    weather || null,
                user_id:    currentUser?.id || null,
                collection: collectionSnapshot,
            }),
        });
        const data = await res.json();

        if (data.recommendation) {
            const r = data.recommendation;
            lastRecommendation = r;

            // Try to pull the year from the release details cache
            let year = '';
            try {
                const detailRes = await fetch(`http://localhost:8000/api/release/${r.discogs_id}/`);
                const details   = await detailRes.json();
                year = details.year || '';
                // Attach year to the stored recommendation for session use
                lastRecommendation.year = year;
            } catch (_) {}

            // Populate result step
            document.getElementById('recResultCover').src       = r.cover_url;
            document.getElementById('recResultTitle').innerText = r.title;
            document.getElementById('recResultArtist').innerText = r.artist;
            document.getElementById('recResultYear').innerText  = year;
            document.getElementById('recResultExplanation').innerText =
                r.explanation || 'No explanation available.';

            // Slide to result
            document.getElementById('recStep2').style.display = 'none';
            document.getElementById('recStep3').style.display = 'block';

        } else {
            // Back to step 1 with a subtle error note
            document.getElementById('recStep2').style.display = 'none';
            document.getElementById('recStep1').style.display = 'block';
            alert(data.message || 'No recommendation found. Try a different mood or weather.');
        }
    } catch (e) {
        document.getElementById('recStep2').style.display = 'none';
        document.getElementById('recStep1').style.display = 'block';
        alert('Could not reach the server. Is Django running?');
    }
}

function startSessionFromRecommendation() {
    if (!lastRecommendation) return;

    // Find the full basic_information object from allReleases so the active
    // session modal has everything it needs (artists array, cover_image, etc.)
    const match = allReleases.find(
        item => item.basic_information.id === lastRecommendation.discogs_id
    );

    if (!match) {
        alert('Album not found in your collection.');
        return;
    }

    // Pre-populate session data using the recommendation's mood + weather,
    // bypassing the preSession modal entirely
    currentSessionData.album      = match.basic_information;
    currentSessionData.preEmotion = lastRecommendMood    || 'neutral';
    currentSessionData.weather    = lastRecommendWeather || '';

    resetTimers();
    document.getElementById('recommendModal').style.display = 'none';
    document.getElementById('activeAlbumTitle').innerText   = lastRecommendation.title;
    document.getElementById('activeSessionModal').style.display = 'flex';
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

// ---- Turntable constants ----
const TT = {
    RECORD_CX: 140, RECORD_CY: 130, RECORD_R: 108,
    PIVOT_X: 265,   PIVOT_Y: 32,
    NEEDLE_LEN: 150,
    REST_ANGLE:  90 * Math.PI / 180,
    PLAY_ANGLE:  115 * Math.PI / 180,
    LIFT_ANGLE:  90 * Math.PI / 180,
};

// ---- Turntable runtime state ----
let tt = {
    currentAngle: TT.REST_ANGLE,
    isPlaying: false,
    isPaused: false,
    currentSide: 'A',
    recordRotation: 0,
    recordAnimFrame: null,
    timerInterval: null,
    isDragging: false,
};

// Legacy aliases kept so existing callers (closeAllModals, submitFinalSession) still compile
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

// ===================== MODAL 2 — Active Session (Turntable) =====================

function startActiveSession() {
    const selected = document.querySelector('input[name="preEmotionRadio"]:checked');
    currentSessionData.preEmotion = selected ? selected.value : 'neutral';
    const selectedWeather = document.querySelector('input[name="weatherRadio"]:checked');
    currentSessionData.weather = selectedWeather ? selectedWeather.value : '';

    document.getElementById('preSessionModal').style.display = 'none';

    // Populate meta fields
    const album = currentSessionData.album;
    document.getElementById('activeAlbumTitle').innerText  = album.title;
    document.getElementById('activeAlbumArtist').innerText = album.artists ? album.artists.map(a => a.name).join(', ') : '';
    document.getElementById('activeAlbumYear').innerText   = album.year || '';

    document.getElementById('activeSessionModal').style.display = 'flex';
    ttInit();
}

// ---- Turntable helpers ----

function ttGetNeedleTip(angle) {
    return {
        x: TT.PIVOT_X + Math.cos(angle) * TT.NEEDLE_LEN,
        y: TT.PIVOT_Y + Math.sin(angle) * TT.NEEDLE_LEN,
    };
}

function ttIsNearRecord(angle) {
    const tip = ttGetNeedleTip(angle);
    const dx = tip.x - TT.RECORD_CX, dy = tip.y - TT.RECORD_CY;
    return Math.sqrt(dx * dx + dy * dy) <= TT.RECORD_R + 6;
}

function ttSetAngle(angle) {
    tt.currentAngle = angle;
    const tip = ttGetNeedleTip(angle);
    const armLine   = document.getElementById('ttArmLine');
    const headshell = document.getElementById('ttHeadshell');
    const needle    = document.getElementById('ttNeedle');

    armLine.setAttribute('x1', TT.PIVOT_X);
    armLine.setAttribute('y1', TT.PIVOT_Y);
    armLine.setAttribute('x2', tip.x);
    armLine.setAttribute('y2', tip.y);

    const deg = angle * 180 / Math.PI;
    headshell.setAttribute('transform', `rotate(${deg + 53} ${tip.x} ${tip.y})`);
    headshell.setAttribute('x', tip.x - 10);
    headshell.setAttribute('y', tip.y - 5);
    needle.setAttribute('transform', `rotate(${deg + 53} ${tip.x} ${tip.y})`);
    needle.setAttribute('x1', tip.x);
    needle.setAttribute('y1', tip.y);
    needle.setAttribute('x2', tip.x + Math.cos(angle + Math.PI / 2) * 8);
    needle.setAttribute('y2', tip.y + Math.sin(angle + Math.PI / 2) * 8);
}

function ttAnimateArm(fromAngle, toAngle, duration, onDone) {
    const start = performance.now();
    function step(now) {
        const t = Math.min((now - start) / duration, 1);
        const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
        ttSetAngle(fromAngle + (toAngle - fromAngle) * ease);
        if (t < 1) requestAnimationFrame(step);
        else if (onDone) onDone();
    }
    requestAnimationFrame(step);
}

function ttSpinRecord() {
    if (!tt.isPlaying || tt.isPaused) return;
    tt.recordRotation += 1.2;
    const rec    = document.getElementById('ttRecord');
    const grooves = document.getElementById('ttGrooves');
    rec.setAttribute('transform',    `rotate(${tt.recordRotation} 140 130)`);
    grooves.setAttribute('transform', `rotate(${tt.recordRotation} 140 130)`);
    tt.recordAnimFrame = requestAnimationFrame(ttSpinRecord);
}

function ttStartSpin() { if (!tt.recordAnimFrame) ttSpinRecord(); }
function ttStopSpin()  {
    if (tt.recordAnimFrame) { cancelAnimationFrame(tt.recordAnimFrame); tt.recordAnimFrame = null; }
}

function ttStartTimer() {
    if (tt.timerInterval) return;
    tt.timerInterval = setInterval(() => {
        if (tt.currentSide === 'A') { currentSessionData.timeA++; }
        else                        { currentSessionData.timeB++; }
        ttUpdateTimerDisplay();
    }, 1000);
}

function ttStopTimer() {
    clearInterval(tt.timerInterval);
    tt.timerInterval = null;
}

function ttUpdateTimerDisplay() {
    const elA = document.getElementById('timeA');
    const elB = document.getElementById('timeB');
    elA.innerText  = formatTime(currentSessionData.timeA);
    elB.innerText  = formatTime(currentSessionData.timeB);
    elA.className  = 'as-timer-val' + (tt.isPlaying && !tt.isPaused && tt.currentSide === 'A' ? ' as-timer-active' : '');
    elB.className  = 'as-timer-val' + (tt.isPlaying && !tt.isPaused && tt.currentSide === 'B' ? ' as-timer-active' : '');
}

function ttSetPlayUI(playing) {
    const icon  = document.getElementById('ppIcon');
    const label = document.getElementById('ppLabel');
    if (playing) {
        label.textContent = 'Pause';
        icon.innerHTML = '<rect x="2" y="2" width="4" height="10" rx="1"/><rect x="8" y="2" width="4" height="10" rx="1"/>';
    } else {
        label.textContent = tt.isPaused ? 'Resume' : 'Start';
        icon.innerHTML = '<path d="M3 2l9 5-9 5V2z"/>';
    }
}

function ttAnimateFlip(onDone) {
    const group = document.getElementById('ttRecordGroup');
    const cx = 140, cy = 130, r = TT.RECORD_R;
    const start = performance.now(), dur = 600;

    function step(now) {
        const t = Math.min((now - start) / dur, 1);
        // ease in-out
        const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
        const angle = ease * 180;

        // Perspective squish: scaleX simulates rotation around Y axis
        // First half: squeeze to 0 (face disappears), second half: expand back (back face)
        const scaleX = Math.abs(Math.cos(angle * Math.PI / 180));
        // Slight vertical bulge at midpoint for the 3D "pop"
        const scaleY = 1 + 0.08 * Math.sin(ease * Math.PI);

        group.setAttribute('transform',
            `translate(${cx} ${cy}) scale(${scaleX} ${scaleY}) translate(${-cx} ${-cy})`
        );

        // Swap appearance at the midpoint
        if (angle >= 90) {
            document.getElementById('ttRecord').setAttribute('fill', '#111');
        }

        if (t < 1) {
            requestAnimationFrame(step);
        } else {
            group.setAttribute('transform', '');
            document.getElementById('ttRecord').setAttribute('fill', 'url(#recGrad)');
            if (onDone) onDone();
        }
    }
    requestAnimationFrame(step);
}

function ttBuildGrooves() {
    const g = document.getElementById('ttGrooves');
    if (!g || g.childElementCount > 0) return;
    for (let r = 42; r <= 102; r += 5) {
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', 140); c.setAttribute('cy', 130); c.setAttribute('r', r);
        c.setAttribute('fill', 'none');
        c.setAttribute('stroke', 'rgba(255,255,255,0.04)');
        c.setAttribute('stroke-width', '1');
        g.appendChild(c);
    }
}

// ---- Public handlers called from HTML ----

function handlePlayPause() {
    if (!tt.isPlaying) {
        tt.isPlaying = true; tt.isPaused = false;
        ttAnimateArm(tt.currentAngle, TT.PLAY_ANGLE, 600, () => {
            ttStartTimer(); ttStartSpin();
        });
        ttSetPlayUI(true);
        ttUpdateTimerDisplay();
    } else if (!tt.isPaused) {
        tt.isPaused = true;
        ttStopTimer(); ttStopSpin();
        ttAnimateArm(tt.currentAngle, TT.LIFT_ANGLE, 400, null);
        ttSetPlayUI(false);
        ttUpdateTimerDisplay();
    } else {
        tt.isPaused = false;
        ttAnimateArm(tt.currentAngle, TT.PLAY_ANGLE, 400, () => {
            ttStartTimer(); ttStartSpin();
        });
        ttSetPlayUI(true);
        ttUpdateTimerDisplay();
    }
}

function handleFlip() {
    const wasPlaying = tt.isPlaying && !tt.isPaused;
    ttStopTimer(); ttStopSpin();

    ttAnimateArm(tt.currentAngle, TT.LIFT_ANGLE, 300, () => {
        tt.currentSide = tt.currentSide === 'A' ? 'B' : 'A';
        document.getElementById('activeSideLabel').innerText = tt.currentSide;

        // Reset record rotation visually
        const rec    = document.getElementById('ttRecord');
        const grooves = document.getElementById('ttGrooves');
        rec.setAttribute('transform', '');
        grooves.setAttribute('transform', '');
        tt.recordRotation = 0;

        ttAnimateFlip(() => {
            if (wasPlaying) {
                tt.isPlaying = true; tt.isPaused = false;
                ttAnimateArm(TT.LIFT_ANGLE, TT.PLAY_ANGLE, 500, () => {
                    ttStartTimer(); ttStartSpin();
                });
                ttSetPlayUI(true);
            } else {
                tt.isPlaying = false; tt.isPaused = false;
                ttAnimateArm(TT.LIFT_ANGLE, TT.REST_ANGLE, 500, null);
                ttSetPlayUI(false);
            }
            ttUpdateTimerDisplay();
        });
    });
}

// ---- Drag-to-play tonearm ----

function ttGetSvgPoint(e) {
    const svg  = document.getElementById('turntableSvg');
    const rect = svg.getBoundingClientRect();
    const client = e.touches ? e.touches[0] : e;
    return {
        x: (client.clientX - rect.left) * (320 / rect.width),
        y: (client.clientY - rect.top)  * (260 / rect.height),
    };
}

function ttDragStart(e) {
    tt.isDragging = true;
    if (tt.isPlaying && !tt.isPaused) { ttStopTimer(); ttStopSpin(); }
    document.getElementById('ttTonearm').style.cursor = 'grabbing';
    e.stopPropagation();
}

function ttDragMove(e) {
    if (!tt.isDragging) return;
    const pt  = ttGetSvgPoint(e);
    let angle = Math.atan2(pt.y - TT.PIVOT_Y, pt.x - TT.PIVOT_X);
    angle = Math.max(75 * Math.PI / 180, Math.min(125 * Math.PI / 180, angle));
    ttSetAngle(angle);
}

function ttDragEnd() {
    if (!tt.isDragging) return;
    tt.isDragging = false;
    document.getElementById('ttTonearm').style.cursor = 'grab';

    if (ttIsNearRecord(tt.currentAngle)) {
        tt.isPlaying = true; tt.isPaused = false;
        ttAnimateArm(tt.currentAngle, TT.PLAY_ANGLE, 300, () => {
            ttStartTimer(); ttStartSpin();
        });
        ttSetPlayUI(true);
        ttUpdateTimerDisplay();
    } else {
        tt.isPlaying = false; tt.isPaused = false;
        ttStopTimer(); ttStopSpin();
        ttAnimateArm(tt.currentAngle, TT.REST_ANGLE, 400, null);
        ttSetPlayUI(false);
        ttUpdateTimerDisplay();
    }
}

// ---- Init: called each time the modal opens ----

function ttInit() {
    ttBuildGrooves();
    tt.currentAngle   = TT.REST_ANGLE;
    tt.isPlaying      = false;
    tt.isPaused       = false;
    tt.currentSide    = 'A';
    tt.recordRotation = 0;

    ttSetAngle(TT.REST_ANGLE);
    ttSetPlayUI(false);
    document.getElementById('activeSideLabel').innerText = 'A';
    ttUpdateTimerDisplay();

    const rec    = document.getElementById('ttRecord');
    const grooves = document.getElementById('ttGrooves');
    rec.setAttribute('transform', '');
    rec.setAttribute('fill', 'url(#recGrad)');
    grooves.setAttribute('transform', '');

    // Replace rec.onclick = ... with:
    const group = document.getElementById('ttRecordGroup');
    group.onclick = () => {
        handleFlip();
    };

    // Tonearm drag
    const arm = document.getElementById('ttTonearm');
    arm.addEventListener('mousedown',  ttDragStart);
    arm.addEventListener('touchstart', ttDragStart, { passive: true });
}

// Attach window-level drag listeners once
window.addEventListener('mousemove', ttDragMove);
window.addEventListener('touchmove', ttDragMove, { passive: true });
window.addEventListener('mouseup',   ttDragEnd);
window.addEventListener('touchend',  ttDragEnd);

// ===================== MODAL 3 =====================
function endActiveSession() {
    ttStopTimer();
    ttStopSpin();
    tt.isPlaying = false;
    tt.isPaused  = false;
    ttAnimateArm(tt.currentAngle, TT.REST_ANGLE, 500, null);

    document.getElementById('activeSessionModal').style.display = 'none';

    const totalSeconds = currentSessionData.timeA + currentSessionData.timeB;
    document.getElementById('totalTimeDisplay').innerText = formatTime(totalSeconds);

    document.getElementById('postSessionModal').style.display = 'flex';
}

// ===================== SAVE SESSION =====================
async function submitFinalSession() {
    const selected = document.querySelector('input[name="postEmotionRadio"]:checked');
    currentSessionData.postEmotion = selected ? selected.value : 'neutral';
    
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

// ===================== HISTORY VIEW =====================

let historyData     = { sessions: [], stats: {} };
let historySortCol  = 'date';
let historySortDir  = 'desc';
let historyPeriod   = 'all';

const MOOD_EMOJI = {
    neutral: '😐', happy: '😊', calm: '😌',
    sad: '😔', stressed: '😰', tired: '😴',
};

async function openHistoryView() {
    document.getElementById('appContainer').classList.add('view-history');
    document.getElementById('navHome').classList.remove('active');
    document.getElementById('navHistory').classList.add('active');
    await loadHistory();
}

function closeHistoryView() {
    document.getElementById('appContainer').classList.remove('view-history');
    document.getElementById('navHome').classList.add('active');
    document.getElementById('navHistory').classList.remove('active');
}

async function loadHistory() {
    if (!currentUser) return;

    const strip = document.getElementById('hvStatsStrip');
    strip.classList.add('hv-loading');

    try {
        const res  = await fetch(`http://localhost:8000/api/history/?user_id=${currentUser.id}&period=${historyPeriod}`);
        const data = await res.json();
        historyData = data;
        renderStats(data.stats);
        renderMostPlayed(data.stats.most_played_albums || []);
        renderMoodDist(data.stats.mood_distribution   || []);
        renderSessionTable();
    } catch (e) {
        console.error('History load failed', e);
    } finally {
        strip.classList.remove('hv-loading');
    }
}

function handlePeriodClick(btn) {
    document.querySelectorAll('.hv-period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    historyPeriod = btn.dataset.period;
    loadHistory();
}

// --- Stats strip ---
function renderStats(stats) {
    document.getElementById('hvStatTime').textContent     = formatHistoryTime(stats.total_seconds || 0);
    document.getElementById('hvStatSessions').textContent = stats.session_count || 0;
    document.getElementById('hvStatArtist').textContent   = stats.most_played_artist
        ? `${stats.most_played_artist.artist} (${stats.most_played_artist.count})`
        : '—';
    document.getElementById('hvStatGenres').textContent   = (stats.top_genres || []).length
        ? stats.top_genres.map(g => g.genre).join(', ')
        : '—';
}

function formatHistoryTime(totalSeconds) {
    if (!totalSeconds) return '0 min';
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m} min`;
}

// --- Most played ---
function renderMostPlayed(albums) {
    const el = document.getElementById('hvMostPlayed');
    if (!albums.length) { el.innerHTML = '<p class="hv-empty-small">No data yet.</p>'; return; }
    el.innerHTML = albums.map((a, i) => `
        <div class="hv-mp-row">
            <span class="hv-mp-rank">${i + 1}</span>
            <img class="hv-mp-cover" src="${a.cover_url || 'https://placehold.co/40'}" alt="" onerror="this.src='https://placehold.co/40'">
            <div class="hv-mp-meta">
                <span class="hv-mp-title">${a.title}</span>
                <span class="hv-mp-artist">${a.artist}</span>
            </div>
            <span class="hv-mp-count">${a.count}×</span>
        </div>
    `).join('');
}

// --- Mood distribution bar chart ---
function renderMoodDist(moods) {
    const el  = document.getElementById('hvMoodDist');
    if (!moods.length) { el.innerHTML = '<p class="hv-empty-small">No data yet.</p>'; return; }
    const max = moods[0].count;
    el.innerHTML = moods.map(m => `
        <div class="hv-mood-row">
            <span class="hv-mood-label">${MOOD_EMOJI[m.mood] || ''} ${m.mood}</span>
            <div class="hv-mood-bar-wrap">
                <div class="hv-mood-bar mood-${m.mood}" style="width:${Math.round((m.count / max) * 100)}%"></div>
            </div>
            <span class="hv-mood-count">${m.count}</span>
        </div>
    `).join('');
}

// --- Session table ---
function renderSessionTable() {
    const search = (document.getElementById('hvSearchInput').value || '').toLowerCase();
    let rows = [...(historyData.sessions || [])];

    if (search) {
        rows = rows.filter(s =>
            s.album_title.toLowerCase().includes(search) ||
            s.album_artist.toLowerCase().includes(search)
        );
    }

    rows.sort((a, b) => {
        let va, vb;
        switch (historySortCol) {
            case 'date':     va = a.timestamp;      vb = b.timestamp;      break;
            case 'album':    va = a.album_title;    vb = b.album_title;    break;
            case 'artist':   va = a.album_artist;   vb = b.album_artist;   break;
            case 'pre':      va = a.pre_emotion;    vb = b.pre_emotion;    break;
            case 'post':     va = a.post_emotion;   vb = b.post_emotion;   break;
            case 'duration': va = a.total_duration; vb = b.total_duration; break;
            default:         va = a.timestamp;      vb = b.timestamp;
        }
        if (va < vb) return historySortDir === 'asc' ? -1 :  1;
        if (va > vb) return historySortDir === 'asc' ?  1 : -1;
        return 0;
    });

    const tbody  = document.getElementById('hvTableBody');
    const empty  = document.getElementById('hvEmptyMsg');

    if (!rows.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = rows.map(s => {
        const dt     = new Date(s.timestamp);
        const dateStr = dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        const timeStr = dt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        const dur    = formatHistoryTime(s.total_duration);
        const preEmoji  = MOOD_EMOJI[s.pre_emotion]  || '';
        const postEmoji = MOOD_EMOJI[s.post_emotion] || '';
        return `
        <tr class="hv-tr">
            <td class="hv-td hv-td-date">
                <span class="hv-date">${dateStr}</span>
                <span class="hv-time">${timeStr}</span>
            </td>
            <td class="hv-td hv-td-album">
                <div class="hv-album-cell">
                    <img class="hv-row-cover" src="${s.album_cover || 'https://placehold.co/36'}" alt="" onerror="this.src='https://placehold.co/36'">
                    <span class="hv-row-title">${s.album_title}</span>
                </div>
            </td>
            <td class="hv-td">${s.album_artist}</td>
            <td class="hv-td"><span class="mood-badge mood-${s.pre_emotion}">${preEmoji} ${s.pre_emotion}</span></td>
            <td class="hv-td"><span class="mood-badge mood-${s.post_emotion}">${postEmoji} ${s.post_emotion}</span></td>
            <td class="hv-td hv-td-dur">${dur}</td>
        </tr>`;
    }).join('');
}

function handleHistorySort(th) {
    const col = th.dataset.col;
    if (col === historySortCol) {
        historySortDir = historySortDir === 'asc' ? 'desc' : 'asc';
    } else {
        historySortCol = col;
        historySortDir = col === 'date' || col === 'duration' ? 'desc' : 'asc';
    }
    document.querySelectorAll('.hv-th .hv-sort-arrow').forEach(a => a.textContent = '');
    const arrow = th.querySelector('.hv-sort-arrow');
    if (arrow) arrow.textContent = historySortDir === 'asc' ? '↑' : '↓';
    renderSessionTable();
}

// ===================== HELPERS =====================
function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function resetTimers() {
    ttStopTimer();
    ttStopSpin();
    tt.isPlaying      = false;
    tt.isPaused       = false;
    tt.currentSide    = 'A';
    tt.recordRotation = 0;
    currentSessionData.timeA = 0;
    currentSessionData.timeB = 0;
    // Reset legacy aliases
    clearInterval(activeInterval);
    activeInterval = null;
    runningSide    = null;
}

function closeAllModals() {
    document.getElementById('recommendModal').style.display    = 'none';
    document.getElementById('preSessionModal').style.display   = 'none';
    document.getElementById('activeSessionModal').style.display = 'none';
    document.getElementById('postSessionModal').style.display  = 'none';
    resetTimers();
}

document.getElementById('preSessionModal').addEventListener('click', function(e) {
    if (e.target === this) closeAllModals();
});