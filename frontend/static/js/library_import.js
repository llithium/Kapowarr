// Library Import: scan, then sort the results into an inbox by outcome. Files
// are handled per series group; the panel on the right shows the current
// match, where the files will go, and a Comic Vine search for fixing it.

const LIEls = {
	templates: {
		group: document.querySelector('#li-group-template'),
		result: document.querySelector('#li-result-template')
	},
	views: {
		start: document.querySelector('#start-window'),
		no_result: document.querySelector('#no-result-window'),
		inbox: document.querySelector('#inbox-window'),
		loading: document.querySelector('#loading-window'),
		no_cv: document.querySelector('#no-cv-window')
	},
	inbox: document.querySelector('#inbox'),
	status: document.querySelector('#inbox-status'),
	buckets: document.querySelectorAll('.li-buckets button[data-bucket]'),
	list: {
		title: document.querySelector('#bucket-title'),
		hint: document.querySelector('#bucket-hint'),
		groups: document.querySelector('#group-list'),
		empty: document.querySelector('#bucket-empty')
	},
	panel: {
		empty: document.querySelector('#panel-empty'),
		content: document.querySelector('#panel-content'),
		title: document.querySelector('#panel-title'),
		meta: document.querySelector('#panel-meta'),
		close: document.querySelector('#close-panel'),
		current: document.querySelector('#current-match'),
		accept: document.querySelector('#accept-guess'),
		exclude: document.querySelector('#toggle-exclude'),
		search_form: document.querySelector('#search-form'),
		search_input: document.querySelector('#search-input'),
		search_status: document.querySelector('#search-status'),
		results: document.querySelector('#search-results'),
		pending: document.querySelector('#pending-match'),
		pending_detail: document.querySelector('#pending-detail'),
		use_group: document.querySelector('#use-for-group'),
		use_file: document.querySelector('#use-for-file'),
		files: document.querySelector('#group-files'),
		files_summary: document.querySelector('#group-files-summary'),
		file_list: document.querySelector('#group-file-list')
	},
	summary: {
		box: document.querySelector('#import-summary'),
		title: document.querySelector('#import-summary-title'),
		list: document.querySelector('#import-summary-list'),
		conflicts: document.querySelector('#import-conflicts'),
		conflict_list: document.querySelector('#import-conflict-list'),
		close: document.querySelector('#close-summary')
	},
	footer: {
		ready: document.querySelector('#ready-summary'),
		rename: document.querySelector('#rename-input'),
		import: document.querySelector('#import-button')
	},
	buttons: {
		cancel: document.querySelectorAll('.cancel-button'),
		run: document.querySelector('#run-import-button'),
		rescan: document.querySelector('#rescan-button')
	}
};

const LIProgress = {
	mode: 'scan',
	started_at: null,
	timer: null,
	observer: null
};

function formatElapsedTime(milliseconds) {
	const total_seconds = Math.max(0, Math.floor(milliseconds / 1000));
	const hours = Math.floor(total_seconds / 3600);
	const minutes = Math.floor((total_seconds % 3600) / 60);
	const seconds = total_seconds % 60;

	return [hours, minutes, seconds]
		.map(value => value.toString().padStart(2, '0'))
		.join(':');
};

function libraryImportProgressContent(mode) {
	if (mode === 'import-rename') {
		return {
			title: 'Importing and renaming comics',
			summary: 'Kapowarr is adding the selected volumes, attaching files to issues, moving files into their managed folders, and applying your naming rules.',
			activity: 'Import in progress',
			steps: [
				'Adding or reusing matched volumes',
				'Attaching files to the matching issues',
				'Moving files into managed volume folders',
				'Renaming files with your media-management settings'
			]
		};
	}

	if (mode === 'import') {
		return {
			title: 'Importing selected comics',
			summary: 'Kapowarr is adding the selected volumes and attaching the files to their matching issues without renaming your files.',
			activity: 'Import in progress',
			steps: [
				'Adding or reusing matched volumes',
				'Attaching files to the matching issues',
				'Moving files only when an existing or shared folder requires it',
				'Updating Kapowarr\'s file records'
			]
		};
	}

	return {
		title: 'Preparing library import',
		summary: 'Kapowarr is scanning your library and building the review list. The scan checks local files first and only uses ComicVine where it is needed.',
		activity: 'Scan in progress',
		steps: [
			'Finding unimported comic files',
			'Reading filenames and embedded ComicInfo.xml metadata',
			'Checking volumes already in your Kapowarr library',
			'Resolving ComicVine IDs or searching ComicVine for unmatched groups',
			'Building the import preview'
		]
	};
};

function installLibraryImportProgressStyles() {
	if (document.querySelector('#library-import-progress-styles'))
		return;

	const style = document.createElement('style');
	style.id = 'library-import-progress-styles';
	style.textContent = `
		#loading-window {
			min-height: calc(100vh - 8rem);
			padding: 2rem 1rem;
		}

		.li-progress-card {
			width: min(44rem, 100%);
			display: flex;
			flex-direction: column;
			gap: 1.25rem;
			border: 1px solid var(--border-color);
			border-radius: 10px;
			padding: clamp(1.25rem, 4vw, 2rem);
			background-color: var(--foreground-color);
			box-shadow: 0 8px 24px rgba(0, 0, 0, .12);
		}

		.li-progress-heading {
			display: flex;
			align-items: flex-start;
			gap: 1rem;
		}

		.li-progress-spinner {
			width: 2.25rem;
			height: 2.25rem;
			flex: 0 0 auto;
			border: 3px solid var(--border-color);
			border-top-color: var(--accent-color);
			border-radius: 50%;
			animation: li-progress-spin .9s linear infinite;
		}

		.li-progress-title {
			margin: 0;
			text-align: left !important;
		}

		.li-progress-summary {
			margin: .4rem 0 0;
			line-height: 1.45;
			color: var(--text-color);
			opacity: .85;
		}

		.li-progress-bar {
			height: .55rem;
			position: relative;
			overflow: hidden;
			border: 1px solid var(--border-color);
			border-radius: 999px;
			background-color: var(--background-color);
		}

		.li-progress-bar::after {
			content: '';
			position: absolute;
			inset-block: 0;
			left: -35%;
			width: 35%;
			border-radius: inherit;
			background-color: var(--accent-color);
			animation: li-progress-slide 1.45s ease-in-out infinite;
		}

		.li-progress-status-row {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 1rem;
			font-size: .95rem;
		}

		.li-progress-activity {
			font-weight: 600;
		}

		.li-progress-elapsed {
			font-variant-numeric: tabular-nums;
			opacity: .8;
		}

		.li-progress-details {
			border-top: 1px solid var(--border-color);
			padding-top: 1rem;
		}

		.li-progress-details h3 {
			margin: 0 0 .75rem;
			font-size: 1rem;
			font-weight: 600;
		}

		.li-progress-steps {
			list-style: none;
			margin: 0;
			padding: 0;
			display: grid;
			gap: .65rem;
		}

		.li-progress-steps li {
			display: flex;
			align-items: center;
			gap: .7rem;
			line-height: 1.35;
		}

		.li-progress-step-dot {
			width: .65rem;
			height: .65rem;
			flex: 0 0 auto;
			border: 2px solid var(--accent-color);
			border-radius: 50%;
			animation: li-progress-pulse 1.8s ease-in-out infinite;
		}

		.li-progress-steps li:nth-child(2) .li-progress-step-dot { animation-delay: .25s; }
		.li-progress-steps li:nth-child(3) .li-progress-step-dot { animation-delay: .5s; }
		.li-progress-steps li:nth-child(4) .li-progress-step-dot { animation-delay: .75s; }
		.li-progress-steps li:nth-child(5) .li-progress-step-dot { animation-delay: 1s; }

		.li-progress-note {
			margin: 0;
			border-top: 1px solid var(--border-color);
			padding-top: 1rem;
			font-size: .9rem;
			line-height: 1.4;
			opacity: .78;
		}

		@keyframes li-progress-spin {
			to { transform: rotate(360deg); }
		}

		@keyframes li-progress-slide {
			0% { left: -35%; }
			55% { left: 100%; }
			100% { left: 100%; }
		}

		@keyframes li-progress-pulse {
			0%, 100% { opacity: .35; transform: scale(.85); }
			50% { opacity: 1; transform: scale(1); }
		}

		@media (prefers-reduced-motion: reduce) {
			.li-progress-spinner,
			.li-progress-bar::after,
			.li-progress-step-dot {
				animation: none;
			}
		}

		@media (max-width: 36rem) {
			.li-progress-status-row {
				align-items: flex-start;
				flex-direction: column;
				gap: .35rem;
			}
		}
	`;
	document.head.appendChild(style);
};

function renderLibraryImportProgress() {
	installLibraryImportProgressStyles();
	const content = libraryImportProgressContent(LIProgress.mode);
	const steps = content.steps
		.map(step => `
			<li>
				<span class="li-progress-step-dot" aria-hidden="true"></span>
				<span>${step}</span>
			</li>
		`)
		.join('');

	LIEls.views.loading.innerHTML = `
		<section class="li-progress-card" role="status" aria-live="polite">
			<div class="li-progress-heading">
				<div class="li-progress-spinner" aria-hidden="true"></div>
				<div>
					<h2 class="li-progress-title">${content.title}</h2>
					<p class="li-progress-summary">${content.summary}</p>
				</div>
			</div>
			<div class="li-progress-bar" aria-label="Operation in progress"></div>
			<div class="li-progress-status-row">
				<span class="li-progress-activity">${content.activity}</span>
				<span class="li-progress-elapsed">Elapsed <span id="li-progress-time">00:00:00</span></span>
			</div>
			<div class="li-progress-details">
				<h3>What Kapowarr is doing</h3>
				<ul class="li-progress-steps">${steps}</ul>
			</div>
			<p class="li-progress-note" id="li-progress-note">Large libraries can take a while. Unchanged ComicInfo metadata may be reused from the Library Import cache.</p>
		</section>
	`;
};

function updateLibraryImportElapsedTime() {
	if (LIProgress.started_at === null)
		return;

	const elapsed = Date.now() - LIProgress.started_at;
	const timer = document.querySelector('#li-progress-time');
	if (timer)
		timer.innerText = formatElapsedTime(elapsed);

	const note = document.querySelector('#li-progress-note');
	if (note && LIProgress.mode === 'scan' && elapsed >= 10000)
		note.innerText = 'Still working. iCloud-only archives can take longer if macOS needs to make their contents available. Successfully cached ComicInfo metadata will not be reopened on later unchanged scans.';
};

function stopLibraryImportProgressTimer() {
	if (LIProgress.timer !== null) {
		clearInterval(LIProgress.timer);
		LIProgress.timer = null;
	}
};

function startLibraryImportProgressTimer() {
	stopLibraryImportProgressTimer();
	if (LIProgress.started_at === null)
		LIProgress.started_at = Date.now();
	updateLibraryImportElapsedTime();
	LIProgress.timer = setInterval(updateLibraryImportElapsedTime, 1000);
};

function setLibraryImportLoadingMode(mode) {
	LIProgress.mode = mode;
	LIProgress.started_at = Date.now();
	renderLibraryImportProgress();
	startLibraryImportProgressTimer();
};

function setupLibraryImportProgressObserver() {
	LIProgress.observer = new MutationObserver(() => {
		if (LIEls.views.loading.classList.contains('hidden')) {
			stopLibraryImportProgressTimer();
			LIProgress.started_at = null;
		} else if (LIProgress.timer === null) {
			if (LIProgress.started_at === null)
				LIProgress.started_at = Date.now();
			startLibraryImportProgressTimer();
		}
	});

	LIProgress.observer.observe(LIEls.views.loading, {
		attributes: true,
		attributeFilter: ['class']
	});
};

//
// Inbox state
//
const BUCKETS = {
	nomatch: {
		title: 'No match',
		hint: 'Kapowarr couldn\'t find these on Comic Vine. Search for each series on the right. These files stay where they are until you match them.'
	},
	guess: {
		title: 'Check the guess',
		hint: 'Matched by title only, without a Comic Vine ID. Accept the guess or pick another match. Unchecked guesses aren\'t imported.'
	},
	new: {
		title: 'New series',
		hint: 'Matched by the Comic Vine ID in their ComicInfo.xml. Each becomes a new series in your library.'
	},
	existing: {
		title: 'Joins a series you have',
		hint: 'These files belong to series already in your library and will be added to them.'
	},
	manual: {
		title: 'Matched by you',
		hint: 'Matches you picked or confirmed in this session.'
	},
	skipped: {
		title: 'Already in library',
		hint: 'These files are already linked to a series, or would replace a file that is already there. They won\'t be imported.'
	},
	excluded: {
		title: 'Left out by you',
		hint: 'You left these out of this import. Select one to include it again.'
	}
};
const BUCKET_ORDER = ['nomatch', 'guess', 'new', 'existing', 'manual', 'skipped', 'excluded'];
const READY_BUCKETS = new Set(['new', 'existing', 'manual']);

const LIState = {
	api_key: null,
	groups: new Map(),
	bucket: null,
	selected: null,
	selected_file: null,
	pending: null,
	search_request: 0,
	scan_summary: ''
};

function groupBucket(group) {
	if (group.conflict) return 'skipped';
	if (group.excluded) return 'excluded';
	if (!group.cv || !group.cv.id) return 'nomatch';
	if (group.manual) return 'manual';
	if (group.cv.match_source === 'comicvine') return 'guess';
	if (group.cv.already_added) return 'existing';
	return 'new';
};

function issueLabel(group) {
	const numbers = group.files
		.map(f => f.comicinfo && f.comicinfo.issue_number)
		.filter(n => n !== undefined && n !== null && n !== '');
	if (!numbers.length) return '';
	if (numbers.length === 1) return `#${numbers[0]}`;
	const numeric = numbers.map(Number);
	if (numeric.every(n => !isNaN(n))) {
		const min = Math.min(...numeric);
		const max = Math.max(...numeric);
		return min === max ? `#${min}` : `#${min}–${max}`;
	}
	return `#${numbers[0]}–${numbers[numbers.length - 1]}`;
};

function sourceLabel(group) {
	const ci = group.files.map(f => f.comicinfo).filter(Boolean);
	if (ci.some(c => c.comicvine_volume_id || c.comicvine_issue_id))
		return 'ComicInfo with a Comic Vine ID';
	if (group.files.some(f => f.metadata_source === 'comicinfo'))
		return 'ComicInfo, no Comic Vine ID';
	return 'filename only';
};

function plural(count, word, plural_word=null) {
	return `${count} ${count === 1 ? word : (plural_word || word + 's')}`;
};

function groupName(group) {
	if (group.cv && group.cv.series_title) return group.cv.series_title;
	const ci = group.files.find(f => f.comicinfo && f.comicinfo.series);
	if (ci) return ci.comicinfo.series;
	return cleanFileTitle(group.files[0].file_title);
};

function cleanFileTitle(title) {
	return title
		.replace(/\s*\(\d{4}\)/g, '')
		.replace(/\s*(issue|#)\s*[\d.]+.*$/i, '')
		.replace(/\s+v(ol(ume)?)?\s*\d+\s*$/i, '')
		.replace(/\s+\d{1,4}\s*$/, '')
		.replace(/[_]+/g, ' ')
		.trim() || title;
};

function groupYear(group) {
	const ci = group.files.find(f => f.comicinfo && f.comicinfo.year);
	return ci ? Number(ci.comicinfo.year) : null;
};

function groupPublisher(group) {
	const ci = group.files.find(f => f.comicinfo && f.comicinfo.publisher);
	return ci ? ci.comicinfo.publisher : null;
};

function matchYear(cv) {
	if (cv.year) return cv.year;
	const m = /\((\d{4})\)\s*$/.exec(cv.title || '');
	return m ? Number(m[1]) : null;
};

function coverUrl(cv) {
	if (!cv) return null;
	if (cv.already_added && LIState.api_key)
		return `${url_base}/api/volumes/${cv.already_added}/cover?api_key=${LIState.api_key}`;
	return cv.cover_link || null;
};

function fillCover(el, url, label) {
	el.innerHTML = '';
	el.classList.toggle('li-cover-empty', !url);
	if (url) {
		const img = document.createElement('img');
		img.src = url;
		img.alt = '';
		img.loading = 'lazy';
		img.onerror = () => {
			img.remove();
			el.classList.add('li-cover-empty');
			el.textContent = (label || '?').trim().charAt(0).toUpperCase();
		};
		el.appendChild(img);
	} else {
		el.textContent = (label || '?').trim().charAt(0).toUpperCase();
	}
};

function buildGroups(results) {
	LIState.groups.clear();
	results.forEach((result, rowid) => {
		const key = result.group_number;
		if (!LIState.groups.has(key))
			LIState.groups.set(key, {
				key,
				files: [],
				cv: result.cv,
				conflict: null,
				manual: false,
				excluded: false
			});
		const group = LIState.groups.get(key);
		group.files.push({
			rowid,
			filepath: result.filepath,
			file_title: result.file_title,
			metadata_source: result.metadata_source,
			comicinfo: result.comicinfo
		});
		if (result.conflict) group.conflict = result.conflict;
	});
};

function groupsInBucket(bucket) {
	return [...LIState.groups.values()].filter(g => groupBucket(g) === bucket);
};

function fileCount(groups) {
	return groups.reduce((total, g) => total + g.files.length, 0);
};

//
// Rendering
//
function renderBuckets() {
	LIEls.buckets.forEach(button => {
		const bucket = button.dataset.bucket;
		const groups = groupsInBucket(bucket);
		const count = fileCount(groups);
		button.querySelector('.li-count').textContent = count;
		button.classList.toggle('li-bucket-zero', count === 0);
		const current = bucket === LIState.bucket;
		button.classList.toggle('li-bucket-current', current);
		if (current) button.setAttribute('aria-current', 'true');
		else button.removeAttribute('aria-current');
		button.title = `${plural(groups.length, 'series', 'series')}, ${plural(count, 'file')}`;
	});
};

function describeGroupMatch(group) {
	const bucket = groupBucket(group);
	if (bucket === 'skipped') return group.conflict.message || 'Already in your library.';
	if (!group.cv || !group.cv.id) return 'No match yet';
	const parts = [`→ ${group.cv.title}`];
	if (group.cv.publisher) parts.push(group.cv.publisher);
	return parts.join(' · ');
};

function renderList() {
	const bucket = LIState.bucket;
	const groups = groupsInBucket(bucket);
	LIEls.list.title.textContent = `${BUCKETS[bucket].title} · ${plural(groups.length, 'series', 'series')}, ${plural(fileCount(groups), 'file')}`;
	LIEls.list.hint.textContent = BUCKETS[bucket].hint;
	LIEls.list.groups.innerHTML = '';
	hide([LIEls.list.empty]);

	if (!groups.length) {
		LIEls.list.empty.textContent = 'Nothing here.';
		hide([], [LIEls.list.empty]);
	}

	groups.forEach(group => {
		const entry = LIEls.templates.group.content.firstElementChild.cloneNode(true);
		entry.dataset.group = group.key;
		const button = entry.querySelector('button');
		const name = groupName(group);
		fillCover(entry.querySelector('.li-cover'), coverUrl(group.cv), name);
		entry.querySelector('.li-group-title').textContent = name;
		const meta = [plural(group.files.length, 'file')];
		const issues = issueLabel(group);
		if (issues) meta.push(issues);
		meta.push(sourceLabel(group));
		entry.querySelector('.li-group-meta').textContent = meta.join(' · ');
		entry.querySelector('.li-group-match').textContent = describeGroupMatch(group);
		const chip = entry.querySelector('.li-chip');
		const chips = {
			nomatch: ['No match', 'bad'], guess: ['Guess', 'warn'], new: ['New', 'ok'],
			existing: ['Adds to series', 'ok'], manual: ['Matched by you', 'acc'],
			skipped: ['Skipped', 'idle'], excluded: ['Left out', 'idle']
		};
		chip.textContent = chips[bucket][0];
		chip.classList.add(chips[bucket][1]);
		const selected = LIState.selected === group.key;
		entry.classList.toggle('li-group-selected', selected);
		button.setAttribute('aria-pressed', selected ? 'true' : 'false');
		button.onclick = () => selectGroup(group.key, true);
		LIEls.list.groups.appendChild(entry);
	});
};

function renderFooter() {
	const ready = [...LIState.groups.values()].filter(g => READY_BUCKETS.has(groupBucket(g)));
	const waiting = [...LIState.groups.values()].filter(g => ['nomatch', 'guess'].includes(groupBucket(g)));
	const ready_files = fileCount(ready);
	const waiting_files = fileCount(waiting);
	let text = ready_files
		? `${plural(ready_files, 'file')} in ${plural(ready.length, 'series', 'series')} ready to import.`
		: 'Nothing is ready to import yet.';
	if (waiting_files)
		text += ` ${plural(waiting_files, 'file')} still ${waiting_files === 1 ? 'needs' : 'need'} you and will stay where ${waiting_files === 1 ? 'it is' : 'they are'}.`;
	LIEls.footer.ready.textContent = text;
	LIEls.footer.import.textContent = ready_files ? `Import ${plural(ready_files, 'file')}` : 'Import';
	LIEls.footer.import.disabled = ready_files === 0;
};

function renderStatus() {
	const total = fileCount([...LIState.groups.values()]);
	LIEls.status.textContent = total
		? `${LIState.scan_summary}${plural(total, 'file')} in ${plural(LIState.groups.size, 'series', 'series')} waiting`
		: `${LIState.scan_summary}Nothing left to import`;
};

function renderAll() {
	renderBuckets();
	renderList();
	renderFooter();
	renderStatus();
	renderPanel();
};

function matchDetail(container, cv, destination_text, destination_exists) {
	container.innerHTML = '';
	if (!cv || !cv.id) {
		const p = document.createElement('p');
		p.className = 'li-muted';
		p.textContent = 'No match yet. Search Comic Vine below.';
		container.appendChild(p);
		return;
	}
	const cover = document.createElement('span');
	cover.className = 'li-cover li-cover-large';
	fillCover(cover, coverUrl(cv), cv.series_title || cv.title);
	const text = document.createElement('div');
	text.className = 'li-match-text';
	const title = document.createElement(cv.link ? 'a' : 'span');
	title.className = 'li-match-title';
	title.textContent = cv.title || cv.series_title;
	if (cv.link) {
		title.href = cv.link;
		title.target = '_blank';
		title.rel = 'noopener';
		title.title = 'Open on Comic Vine';
	}
	const meta = document.createElement('span');
	meta.className = 'li-muted';
	const parts = [];
	if (cv.publisher) parts.push(cv.publisher);
	if (cv.issue_count !== undefined && cv.issue_count !== null) parts.push(plural(cv.issue_count, 'issue'));
	if (cv.already_added) parts.push('in your library');
	meta.textContent = parts.join(' · ');
	text.append(title, meta);
	if (cv.match_reason || cv.match_source) {
		const reason = document.createElement('span');
		reason.className = 'li-muted li-small';
		reason.textContent = cv.match_source === 'comicvine'
			? 'Guessed from the series title. No Comic Vine ID in the files.'
			: cv.match_source === 'manual'
				? 'Picked by you.'
				: (cv.match_reason || '');
		if (reason.textContent) text.appendChild(reason);
	}
	if (destination_text !== undefined) {
		const dest = document.createElement('div');
		dest.className = 'li-destination';
		const label = document.createElement('span');
		label.className = 'li-card-label';
		label.textContent = destination_exists ? 'Files go into the existing folder' : 'Files go to a new folder';
		const path = document.createElement('code');
		path.textContent = destination_text || 'Worked out when you import';
		dest.append(label, path);
		text.appendChild(dest);
	}
	container.append(cover, text);
};

function renderPanel() {
	const group = LIState.groups.get(LIState.selected);
	LIEls.inbox.classList.toggle('li-panel-open', Boolean(group));
	if (!group) {
		hide([LIEls.panel.content], [LIEls.panel.empty]);
		return;
	}
	hide([LIEls.panel.empty], [LIEls.panel.content]);
	const bucket = groupBucket(group);
	const name = groupName(group);
	LIEls.panel.title.textContent = name;
	const meta = [plural(group.files.length, 'file')];
	const issues = issueLabel(group);
	if (issues) meta.push(issues);
	const year = groupYear(group);
	if (year) meta.push(String(year));
	meta.push(sourceLabel(group));
	LIEls.panel.meta.textContent = meta.join(' · ');

	matchDetail(
		LIEls.panel.current,
		group.cv,
		group.cv && group.cv.id ? (group.cv.destination || '') : undefined,
		group.cv && (group.cv.destination_exists || group.cv.already_added)
	);

	hide([LIEls.panel.accept]);
	if (bucket === 'guess') hide([], [LIEls.panel.accept]);

	LIEls.panel.exclude.classList.toggle('hidden', bucket === 'skipped');
	LIEls.panel.exclude.textContent = group.excluded ? 'Include in this import' : 'Leave out of this import';

	// Files
	LIEls.panel.files_summary.textContent = `Files in this series (${group.files.length})`;
	LIEls.panel.file_list.innerHTML = '';
	group.files.forEach(file => {
		const li = document.createElement('li');
		const button = document.createElement('button');
		button.type = 'button';
		button.className = 'li-file';
		const name = document.createElement('span');
		name.textContent = file.file_title;
		name.title = file.filepath;
		button.appendChild(name);
		if (file.comicinfo && file.comicinfo.issue_number) {
			const n = document.createElement('span');
			n.className = 'li-muted';
			n.textContent = `#${file.comicinfo.issue_number}`;
			button.appendChild(n);
		}
		const selected = LIState.selected_file === file.rowid;
		button.setAttribute('aria-pressed', selected ? 'true' : 'false');
		button.onclick = () => {
			LIState.selected_file = selected ? null : file.rowid;
			renderPanel();
		};
		li.appendChild(button);
		LIEls.panel.file_list.appendChild(li);
	});
	if (group.files.length === 1) LIEls.panel.files.open = false;

	renderPending();
};

function renderPending() {
	const group = LIState.groups.get(LIState.selected);
	const pending = LIState.pending;
	if (!group || !pending || pending.group !== group.key) {
		hide([LIEls.panel.pending]);
		return;
	}
	hide([], [LIEls.panel.pending]);
	matchDetail(
		LIEls.panel.pending_detail,
		pending.cv,
		pending.destination === null ? 'Working it out…' : pending.destination,
		Boolean(pending.cv.already_added)
	);
	LIEls.panel.use_group.textContent = group.files.length === 1
		? 'Use this match'
		: `Use for all ${group.files.length} files`;
	const file = group.files.find(f => f.rowid === LIState.selected_file);
	if (file && group.files.length > 1) {
		LIEls.panel.use_file.textContent = `Only ${file.file_title}`;
		hide([], [LIEls.panel.use_file]);
	} else {
		hide([LIEls.panel.use_file]);
	}
};

//
// Selection and keyboard
//
function selectBucket(bucket, select_first=true) {
	LIState.bucket = bucket;
	if (select_first) {
		const first = groupsInBucket(bucket)[0];
		LIState.selected = first && window.matchMedia('(min-width: 901px)').matches ? first.key : null;
		LIState.selected_file = null;
		LIState.pending = null;
		if (first && LIState.selected !== null) prefillSearch(first);
	}
	renderAll();
};

function selectGroup(key, focus_panel=false) {
	if (LIState.selected !== key) {
		LIState.selected = key;
		LIState.selected_file = null;
		LIState.pending = null;
		const group = LIState.groups.get(key);
		if (group) prefillSearch(group);
	}
	renderAll();
	if (focus_panel && window.matchMedia('(max-width: 900px)').matches)
		LIEls.panel.title.focus?.();
};

function moveSelection(step) {
	const groups = groupsInBucket(LIState.bucket);
	if (!groups.length) return;
	let index = groups.findIndex(g => g.key === LIState.selected);
	index = index === -1 ? 0 : Math.max(0, Math.min(groups.length - 1, index + step));
	selectGroup(groups[index].key);
	const el = LIEls.list.groups.querySelector(`[data-group="${groups[index].key}"] button`);
	if (el) {
		el.focus();
		el.scrollIntoView({block: 'nearest'});
	}
};

function firstBucketWithGroups() {
	return BUCKET_ORDER.find(b => groupsInBucket(b).length) || 'nomatch';
};

// After you handle a series, move on to the next one that still needs you.
function advanceAfterChange(previous_bucket, previous_index) {
	const remaining = groupsInBucket(previous_bucket);
	if (remaining.length) {
		const next = remaining[Math.min(previous_index, remaining.length - 1)];
		LIState.bucket = previous_bucket;
		LIState.selected = next.key;
		LIState.selected_file = null;
		LIState.pending = null;
		prefillSearch(next);
	} else {
		const needs = ['nomatch', 'guess'].find(b => groupsInBucket(b).length);
		LIState.bucket = needs || previous_bucket;
		const next = needs ? groupsInBucket(needs)[0] : null;
		LIState.selected = next ? next.key : LIState.selected;
		LIState.selected_file = null;
		LIState.pending = null;
		if (next) prefillSearch(next);
	}
	renderAll();
};

//
// Matching
//
function prefillSearch(group) {
	const query = group.cv && group.cv.series_title ? group.cv.series_title : groupName(group);
	LIEls.panel.search_input.value = query;
	LIEls.panel.results.innerHTML = '';
	LIEls.panel.search_status.textContent = '';
};

function rankResults(results, group) {
	const year = groupYear(group);
	const publisher = (groupPublisher(group) || '').toLowerCase().replace(/\s+comics?$/, '');
	const highest_issue = Math.max(0, ...group.files
		.map(f => Number(f.comicinfo && f.comicinfo.issue_number))
		.filter(n => !isNaN(n)));
	return results
		.map((result, index) => {
			const reasons = [];
			let score = 0;
			if (year && result.year && Math.abs(Number(result.year) - year) <= 1) {
				score += 2;
				reasons.push('Year matches');
			}
			const result_publisher = (result.publisher || '').toLowerCase().replace(/\s+comics?$/, '');
			if (publisher && result_publisher && result_publisher === publisher) {
				score += 2;
				reasons.push('Publisher matches');
			}
			if (highest_issue && result.issue_count >= highest_issue) {
				score += 1;
				reasons.push(`Has #${highest_issue}`);
			}
			if (result.already_added) score += 1;
			return {result, score, reasons, index};
		})
		.sort((a, b) => b.score - a.score || a.index - b.index);
};

function searchComicVine() {
	const group = LIState.groups.get(LIState.selected);
	const query = LIEls.panel.search_input.value.trim();
	if (!group || !query) return;
	const request = ++LIState.search_request;
	LIEls.panel.search_status.textContent = 'Searching Comic Vine…';
	LIEls.panel.results.innerHTML = '';
	fetchAPI('/volumes/search', LIState.api_key, {query})
	.then(json => {
		if (request !== LIState.search_request) return;
		const ranked = rankResults(json.result, group);
		LIEls.panel.search_status.textContent = ranked.length
			? `${plural(ranked.length, 'result')}. Closest matches first.`
			: 'No results. Try fewer words, or paste a Comic Vine volume ID like 4050-12345.';
		ranked.forEach(({result, reasons}) => {
			const entry = LIEls.templates.result.content.firstElementChild.cloneNode(true);
			const button = entry.querySelector('button');
			fillCover(entry.querySelector('.li-cover'), result.already_added
				? `${url_base}/api/volumes/${result.already_added}/cover?api_key=${LIState.api_key}`
				: result.cover_link, result.title);
			entry.querySelector('.li-result-title').textContent = `${result.title} (${result.year || '?'})`;
			const meta = [];
			if (result.publisher) meta.push(result.publisher);
			meta.push(plural(result.issue_count, 'issue'));
			if (result.translated) meta.push('translated');
			entry.querySelector('.li-result-meta').textContent = meta.join(' · ');
			const chips = entry.querySelector('.li-result-chips');
			if (result.already_added) reasons.unshift('In your library');
			reasons.forEach(reason => {
				const chip = document.createElement('span');
				chip.className = 'li-chip ' + (reason === 'In your library' ? 'acc' : 'ok');
				chip.textContent = reason;
				chips.appendChild(chip);
			});
			const is_current = group.cv && group.cv.id === result.comicvine_id;
			if (is_current) {
				const chip = document.createElement('span');
				chip.className = 'li-chip idle';
				chip.textContent = 'Current match';
				chips.appendChild(chip);
			}
			button.onclick = () => {
				LIEls.panel.results.querySelectorAll('.li-result').forEach(b => b.setAttribute('aria-pressed', 'false'));
				button.setAttribute('aria-pressed', 'true');
				choosePending(group, result);
			};
			button.setAttribute('aria-pressed', 'false');
			LIEls.panel.results.appendChild(entry);
		});
	})
	.catch(async e => {
		if (request !== LIState.search_request) return;
		const j = await apiError(e);
		LIEls.panel.search_status.textContent = j.error === 'CVRateLimitReached'
			? 'Comic Vine is rate limiting requests. Wait a minute and search again.'
			: 'Search failed. Check your connection and Comic Vine API key, then try again.';
	});
};

function choosePending(group, result) {
	const cv = {
		id: result.comicvine_id,
		title: `${result.title} (${result.year})`,
		series_title: result.title,
		year: result.year,
		publisher: result.publisher,
		volume_number: result.volume_number,
		issue_count: result.issue_count,
		link: result.site_url,
		cover_link: result.cover_link,
		already_added: result.already_added || null,
		match_source: 'manual'
	};
	const pending = {group: group.key, cv, destination: null};
	LIState.pending = pending;
	renderPending();
	LIEls.panel.pending.scrollIntoView({block: 'nearest', behavior: 'smooth'});
	previewDestination(cv).then(destination => {
		if (LIState.pending !== pending) return;
		pending.destination = destination;
		cv.destination = destination;
		cv.destination_exists = Boolean(cv.already_added);
		renderPending();
	});
};

function relativeFolder(folder, root) {
	if (root && folder.startsWith(root))
		return folder.slice(root.length).replace(/^[\\/]+/, '');
	return folder;
};

async function previewDestination(cv) {
	try {
		if (cv.already_added) {
			const json = await fetchAPI(`/volumes/${cv.already_added}`, LIState.api_key);
			return relativeFolder(json.result.folder, json.result.root_folder_path);
		}
		const response = await sendAPI('POST', '/volumes/search', LIState.api_key, {}, {
			comicvine_id: cv.id,
			title: cv.series_title,
			year: cv.year,
			volume_number: cv.volume_number || 1,
			publisher: cv.publisher || null
		});
		const json = await response.json();
		return json.result.folder;
	} catch (e) {
		return '';
	}
};

function applyPending(only_file=false) {
	const group = LIState.groups.get(LIState.selected);
	const pending = LIState.pending;
	if (!group || !pending || pending.group !== group.key) return;
	const previous_bucket = groupBucket(group);
	const previous_index = groupsInBucket(previous_bucket).findIndex(g => g.key === group.key);

	if (only_file && group.files.length > 1) {
		const file = group.files.find(f => f.rowid === LIState.selected_file);
		if (!file) return;
		group.files = group.files.filter(f => f !== file);
		const key = `${group.key}.${file.rowid}`;
		LIState.groups.set(key, {
			key, files: [file], cv: {...pending.cv}, conflict: null, manual: true, excluded: false
		});
		LIState.selected_file = null;
		LIState.pending = null;
		renderAll();
		return;
	}

	group.cv = {...pending.cv};
	group.manual = true;
	group.excluded = false;
	advanceAfterChange(previous_bucket, previous_index);
};

function acceptGuess() {
	const group = LIState.groups.get(LIState.selected);
	if (!group || groupBucket(group) !== 'guess') return;
	const previous_index = groupsInBucket('guess').findIndex(g => g.key === group.key);
	group.manual = true;
	group.cv = {...group.cv, match_source: 'manual'};
	advanceAfterChange('guess', previous_index);
};

function toggleExclude() {
	const group = LIState.groups.get(LIState.selected);
	if (!group || group.conflict) return;
	const previous_bucket = groupBucket(group);
	const previous_index = groupsInBucket(previous_bucket).findIndex(g => g.key === group.key);
	group.excluded = !group.excluded;
	if (group.excluded) advanceAfterChange(previous_bucket, previous_index);
	else {
		LIState.bucket = groupBucket(group);
		renderAll();
	}
};

//
// Scan and import
//
function showView(view) {
	hide(Object.values(LIEls.views), [view]);
};

function loadProposal(api_key) {
	const params = {
		limit: parseInt(document.querySelector('#limit-input').value),
		limit_parent_folder: document.querySelector('#folder-input').value,
		only_english: document.querySelector('#lang-input').value
	};
	const ffi = document.querySelector('#folder-filter-input');
	if (ffi.offsetParent !== null && (ffi.value || null) !== null)
		params.folder_filter = encodeURIComponent(ffi.value);

	setLibraryImportLoadingMode('scan');
	hide([document.querySelector('#folder-filter-error'), LIEls.summary.box]);
	showView(LIEls.views.loading);

	fetchAPI('/libraryimport', api_key, params)
	.then(json => {
		buildGroups(json.result);
		LIState.scan_summary = '';
		LIState.selected = null;
		LIState.pending = null;
		if (!json.result.length) {
			showView(LIEls.views.no_result);
			return;
		}
		showView(LIEls.views.inbox);
		selectBucket(firstBucketWithGroups());
	})
	.catch(async e => {
		const j = await apiError(e);
		if (j.error === 'InvalidComicVineApiKey')
			showView(LIEls.views.no_cv);
		else if (j.error === 'InvalidKeyValue') {
			showView(LIEls.views.start);
			hide([], [document.querySelector('#folder-filter-error')]);
		} else {
			showView(LIEls.views.start);
			alert('Could not scan the library. Please try again.');
		}
	});
};

function importPayload() {
	return [...LIState.groups.values()]
		.filter(g => READY_BUCKETS.has(groupBucket(g)))
		.flatMap(g => g.files.map(f => ({filepath: f.filepath, id: g.cv.id})));
};

function importLibrary(api_key) {
	const data = importPayload();
	if (!data.length) return;
	const rename = LIEls.footer.rename.checked;
	const imported_paths = new Set(data.map(d => d.filepath));

	setLibraryImportLoadingMode(rename ? 'import-rename' : 'import');
	showView(LIEls.views.loading);
	sendAPI('POST', '/libraryimport', api_key, {rename_files: rename}, data)
	.then(response => response.json())
	.then(json => {
		const conflicts = json.result.conflicts || [];
		const imported = json.result.imported || [];
		const conflict_paths = new Set(conflicts.map(c => c.filepath));

		// Imported files leave the inbox. Files that hit a name clash stay,
		// marked, so you can see what didn't move.
		for (const [key, group] of [...LIState.groups.entries()]) {
			group.files = group.files.filter(f => !imported_paths.has(f.filepath) || conflict_paths.has(f.filepath));
			if (!group.files.length) LIState.groups.delete(key);
			else if (group.files.every(f => conflict_paths.has(f.filepath)))
				group.conflict = {
					label: 'Not moved',
					message: 'A file with the same name is already in the series folder.'
				};
		}

		renderSummary(imported, conflicts);
		LIState.selected = null;
		LIState.pending = null;
		showView(LIEls.views.inbox);
		if (LIState.groups.size) selectBucket(firstBucketWithGroups());
		else {
			LIState.bucket = 'nomatch';
			renderAll();
		}
		LIEls.summary.box.focus();
	})
	.catch(() => {
		showView(LIEls.views.inbox);
		alert('Could not import the selected files. Please try again.');
	});
};

function renderSummary(imported, conflicts) {
	const files = imported.reduce((t, v) => t + v.file_count, 0);
	LIEls.summary.title.textContent = imported.length
		? `Imported ${plural(files, 'file')} into ${plural(imported.length, 'series', 'series')}`
		: 'Nothing was imported';
	LIEls.summary.list.innerHTML = '';
	imported.forEach(volume => {
		const li = document.createElement('li');
		const link = document.createElement('a');
		link.href = `${url_base}/volumes/${volume.volume_id}`;
		link.textContent = volume.year ? `${volume.title} (${volume.year})` : volume.title;
		const detail = document.createElement('span');
		detail.className = 'li-muted';
		detail.textContent = ` · ${plural(volume.file_count, 'file')} · ${volume.new_volume ? 'new series' : 'added to series'}`;
		const folder = document.createElement('code');
		folder.textContent = volume.folder;
		li.append(link, detail, folder);
		LIEls.summary.list.appendChild(li);
	});
	LIEls.summary.conflict_list.innerHTML = '';
	conflicts.forEach(conflict => {
		const li = document.createElement('li');
		li.textContent = conflict.filepath.split(/[\\/]/).pop();
		li.title = `${conflict.filepath} → ${conflict.destination}`;
		LIEls.summary.conflict_list.appendChild(li);
	});
	LIEls.summary.conflicts.classList.toggle('hidden', !conflicts.length);
	hide([], [LIEls.summary.box]);
};

function isTyping(target) {
	return target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
};

function handleShortcut(e) {
	if (LIEls.views.inbox.classList.contains('hidden') || e.metaKey || e.ctrlKey || e.altKey) return;
	if (isTyping(e.target)) {
		if (e.key === 'Escape') e.target.blur();
		return;
	}
	const key = e.key.toLowerCase();
	if (key === 'j') { e.preventDefault(); moveSelection(1); }
	else if (key === 'k') { e.preventDefault(); moveSelection(-1); }
	else if (key === '/') {
		if (!LIState.selected) return;
		e.preventDefault();
		LIEls.panel.search_input.focus();
		LIEls.panel.search_input.select();
	}
	else if (key === 'a') { acceptGuess(); }
	else if (key === 'escape' && LIEls.inbox.classList.contains('li-panel-open') && window.matchMedia('(max-width: 900px)').matches) {
		LIState.selected = null;
		renderAll();
	}
};

// code run on load

renderLibraryImportProgress();
setupLibraryImportProgressObserver();

try {
	const saved = getLocalStorage('li_rename').li_rename;
	if (saved !== null && saved !== undefined) LIEls.footer.rename.checked = Boolean(saved);
} catch (e) {}
LIEls.footer.rename.onchange = () => setLocalStorage({li_rename: LIEls.footer.rename.checked});

usingApiKey()
.then(api_key => {
	LIState.api_key = api_key;
	LIEls.buttons.run.onclick = () => loadProposal(api_key);
	LIEls.buttons.rescan.onclick = () => loadProposal(api_key);
	LIEls.footer.import.onclick = () => importLibrary(api_key);
});

LIEls.buckets.forEach(button => button.onclick = () => selectBucket(button.dataset.bucket));
LIEls.panel.search_form.addEventListener('submit', e => {
	e.preventDefault();
	searchComicVine();
});
LIEls.panel.accept.onclick = acceptGuess;
LIEls.panel.exclude.onclick = toggleExclude;
LIEls.panel.use_group.onclick = () => applyPending(false);
LIEls.panel.use_file.onclick = () => applyPending(true);
LIEls.panel.close.onclick = () => {
	LIState.selected = null;
	renderAll();
};
LIEls.summary.close.onclick = () => hide([LIEls.summary.box]);
document.addEventListener('keydown', handleShortcut);
LIEls.buttons.cancel.forEach(b => b.onclick = () => showView(LIEls.views.start));
