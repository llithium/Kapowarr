const LIEls = {
	pre_build: {
		li_result: document.querySelector('.pre-build-els .li-result'),
		search_result: document.querySelector('.pre-build-els .search-result')
	},
	views: {
		start: document.querySelector('#start-window'),
		no_result: document.querySelector('#no-result-window'),
		list: document.querySelector('#list-window'),
		loading: document.querySelector('#loading-window'),
		no_cv: document.querySelector('#no-cv-window')
	},
	proposal_list: document.querySelector('.proposal-list'),
	select_all: document.querySelector('#selectall-input'),
	search: {
		window: document.querySelector('#cv-window'),
		input: document.querySelector('#search-input'),
		results: document.querySelector('.search-results'),
		container: document.querySelector('.search-results-container'),
		bar: document.querySelector('.search-bar')
	},
	buttons: {
		cancel: document.querySelectorAll('.cancel-button'),
		run: document.querySelector('#run-import-button'),
		import: document.querySelector('#import-button'),
		import_rename: document.querySelector('#import-rename-button')
	}
};

const rowid_to_filepath = {};

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

function describeMatch(result) {
	if (!result.cv.id)
		return ['No automatic match', 'Choose a match manually.'];

	if (result.cv.match_source === 'comicinfo-id' || result.cv.direct_id) {
		const confidence = result.cv.confidence === undefined
			? ''
			: ` (${result.cv.confidence}%)`;
		return [
			`ComicInfo ID${confidence}`,
			result.cv.match_reason || 'Matched using a ComicVine ID embedded in ComicInfo.xml.'
		];
	}

	if (result.cv.match_source === 'existing-library') {
		const confidence = result.cv.confidence === undefined
			? ''
			: ` (${result.cv.confidence}%)`;
		return [
			`Existing library${confidence}`,
			result.cv.match_reason || 'Matched to a volume already in Kapowarr.'
		];
	}

	if (result.cv.match_source === 'comicvine')
		return ['ComicVine', 'Matched by ComicVine search.'];

	return ['Automatic', 'Automatically matched.'];
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
	hide(
		[LIEls.views.start, document.querySelector('#folder-filter-error')],
		[LIEls.views.loading]
	);

	LIEls.proposal_list.innerHTML = '';
	LIEls.select_all.checked = true;

	fetchAPI('/libraryimport', api_key, params)
	.then(json => {
		json.result.forEach((result, rowid) => {
			const entry = LIEls.pre_build.li_result.cloneNode(true);
			entry.dataset.rowid = rowid;
			entry.dataset.group_number = result.group_number;
			rowid_to_filepath[rowid] = {
				cv_id: result.cv.id || null,
				filepath: result.filepath
			};

			const title = entry.querySelector('.file-column');
			title.innerText = result.file_title;
			title.title = result.filepath;

			const metadata_source = entry.querySelector('.metadata-source');
			if (result.metadata_source === 'comicinfo') {
				metadata_source.innerText = 'ComicInfo.xml';
				if (result.comicinfo) {
					const details = [];
					if (result.comicinfo.series)
						details.push(`Series: ${result.comicinfo.series}`);
					if (result.comicinfo.issue_number)
						details.push(`Issue: ${result.comicinfo.issue_number}`);
					if (result.comicinfo.year)
						details.push(`Issue year: ${result.comicinfo.year}`);
					if (result.comicinfo.publisher)
						details.push(`Publisher: ${result.comicinfo.publisher}`);
					if (result.comicinfo.format)
						details.push(`Format: ${result.comicinfo.format}`);
					if (result.comicinfo.comicvine_volume_id)
						details.push(`ComicVine volume ID: ${result.comicinfo.comicvine_volume_id}`);
					if (result.comicinfo.comicvine_issue_id)
						details.push(`ComicVine issue ID: ${result.comicinfo.comicvine_issue_id}`);
					metadata_source.title = details.join('\n');
				}
			} else {
				metadata_source.innerText = 'Filename';
				metadata_source.title = 'No usable embedded ComicInfo.xml found.';
			}

			const CV_link = entry.querySelector('a');
			CV_link.href = result.cv.link || '';
			CV_link.innerText = result.cv.title || 'No match';

			entry.querySelector('.issue-count').innerText =
				result.cv.issue_count ?? '';

			const [match_text, match_reason] = describeMatch(result);
			const match_details = entry.querySelector('.match-details');
			match_details.innerText = match_text;
			match_details.title = match_reason;

			entry.querySelector('button').onclick = e => openEditCVMatch(rowid);

			LIEls.proposal_list.appendChild(entry);
		});

		if (json.result.length > 0)
			hide([LIEls.views.loading], [LIEls.views.list]);
		else
			hide([LIEls.views.loading], [LIEls.views.no_result]);
	})
	.catch(e => {
		e.json().then(j => {
			if (j.error === 'InvalidComicVineApiKey')
				hide([LIEls.views.loading], [LIEls.views.no_cv]);
			else if (j.error === 'InvalidKeyValue')
				hide(
					[LIEls.views.loading],
					[LIEls.views.start, document.querySelector('#folder-filter-error')]
				);
			else
				console.log(j);
		});
	});
};

function toggleSelectAll() {
	const checked = LIEls.select_all.checked;
	LIEls.proposal_list.querySelectorAll('input[type="checkbox"]').forEach(
		e => e.checked = checked
	);
};

function openEditCVMatch(rowid) {
	LIEls.search.window.dataset.rowid = rowid;
	LIEls.search.results.innerHTML = '';
	hide([LIEls.search.container]);
	LIEls.search.input.value = '';
	showWindow('cv-window');
	LIEls.search.input.focus();
};

function editCVMatch(
	rowid,
	comicvine_id,
	site_url,
	title,
	year,
	issue_count,
	group_number=null
) {
	let target_td;
	if (group_number === null)
		target_td = document.querySelectorAll(`tr[data-rowid="${rowid}"]`);
	else
		target_td = document.querySelectorAll(`tr[data-group_number="${group_number}"]`);

	target_td.forEach(tr => {
		rowid_to_filepath[tr.dataset.rowid].cv_id = parseInt(comicvine_id);
		const link = tr.querySelector('a');
		link.href = site_url;
		link.innerText = `${title} (${year})`;
		tr.querySelector('.issue-count').innerText = issue_count;
		const match_details = tr.querySelector('.match-details');
		match_details.innerText = 'Manual';
		match_details.title = 'Match selected manually.';
	});
};

function searchCV() {
	const input = LIEls.search.input;
	input.blur();
	usingApiKey()
	.then(api_key => {
		LIEls.search.results.innerHTML = '';
		fetchAPI('/volumes/search', api_key, {query: input.value})
		.then(json => {
			json.result.forEach(result => {
				const entry = LIEls.pre_build.search_result.cloneNode(true);

				const title = entry.querySelector('td:nth-child(1) a');
				title.href = result.site_url;
				title.innerText = `${result.title} (${result.year})`;

				entry.querySelector('td:nth-child(2)').innerText =
					result.issue_count;

				const select_button = entry.querySelector('td:nth-child(3) button');
				select_button.onclick = e => {
					editCVMatch(
						LIEls.search.window.dataset.rowid,
						result.comicvine_id,
						result.site_url,
						result.title,
						result.year,
						result.issue_count
					);
					closeWindow();
				};

				const select_for_all_button = entry.querySelector('td:nth-child(4) button');
				select_for_all_button.onclick = e => {
					const rowid = LIEls.search.window.dataset.rowid;
					const group_number = document.querySelector(`tr[data-rowid="${rowid}"]`)
						.dataset.group_number;
					editCVMatch(
						rowid,
						result.comicvine_id,
						result.site_url,
						result.title,
						result.year,
						result.issue_count,
						group_number
					);
					closeWindow();
				};

				LIEls.search.results.appendChild(entry);
			});
			hide([], [LIEls.search.container]);
		});
	});
};

function importLibrary(api_key, rename=false) {
	const data = [...LIEls.proposal_list.querySelectorAll(
		'tr:has(input[type="checkbox"]:checked)'
	)]
		.filter(i => rowid_to_filepath[i.dataset.rowid].cv_id !== null)
		.map(e => {
			const rowid = e.dataset.rowid;
			return {
				'filepath': rowid_to_filepath[rowid].filepath,
				'id': rowid_to_filepath[rowid].cv_id
			};
		});

	setLibraryImportLoadingMode(rename ? 'import-rename' : 'import');
	hide([LIEls.views.list], [LIEls.views.loading]);
	sendAPI('POST', '/libraryimport', api_key, {rename_files: rename}, data)
	.then(response => hide([LIEls.views.loading], [LIEls.views.start]));
};

// code run on load

renderLibraryImportProgress();
setupLibraryImportProgressObserver();

usingApiKey()
.then(api_key => {
	LIEls.buttons.run.onclick = e => loadProposal(api_key);
	LIEls.buttons.import.onclick = e => importLibrary(api_key, false);
	LIEls.buttons.import_rename.onclick = e => importLibrary(api_key, true);
});

LIEls.search.bar.action = 'javascript:searchCV();';
LIEls.select_all.onchange = e => toggleSelectAll();
LIEls.buttons.cancel.forEach(b =>
	b.onclick = e => hide(
		[LIEls.views.list, LIEls.views.no_result, LIEls.views.no_cv],
		[LIEls.views.start]
	)
);