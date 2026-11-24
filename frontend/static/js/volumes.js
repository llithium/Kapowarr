const library_els = {
	main: document.querySelector('main'),
	pages: {
		loading: document.querySelector('#loading-library'),
		empty: document.querySelector('#empty-library'),
		error: document.querySelector('#library-error'),
		view: document.querySelector('#library-container'),
	},
	views: {
		list: document.querySelector('#list-library'),
		table: document.querySelector('#table-library'),
	},
	view_options: {
		sort: document.querySelector('#sort-button'),
		view: document.querySelector('#view-button'),
		filter: document.querySelector('#filter-button')
	},
	task_buttons: {
		update_all: document.querySelector('#updateall-button')
	},
	search: {
		clear: document.querySelector('#clear-search'),
		container: document.querySelector('#search-container'),
		input: document.querySelector('#search-input')
	},
	stats: {
		volume_count: document.querySelector('#volume-count'),
		volume_monitored_count: document.querySelector('#volume-monitored-count'),
		volume_unmonitored_count: document.querySelector('#volume-unmonitored-count'),
		issue_count: document.querySelector('#issue-count'),
		issue_download_count: document.querySelector('#issue-download-count'),
		file_count: document.querySelector('#file-count'),
		total_file_size: document.querySelector('#total-file-size')
	},
	select_all: document.querySelector('#selectall-input'),
	publishers: document.querySelector('#publisher-list'),
	publisher_picker: {
		button: document.querySelector('#publisher-button'),
		popover: document.querySelector('#publisher-popover'),
		search: document.querySelector('#publisher-search'),
		none: document.querySelector('#publisher-none'),
		chips: document.querySelector('#publisher-chips')
	},
	scope: {
		title: document.querySelector('#scope-title'),
		count: document.querySelector('#library-result-count')
	},
	inspector: {
		root: document.querySelector('#inspector'),
		empty: document.querySelector('#inspector-empty'),
		content: document.querySelector('#inspector-content'),
		cover: document.querySelector('#insp-cover'),
		stack: document.querySelector('#insp-stack'),
		title: document.querySelector('#insp-title'),
		meta: document.querySelector('#insp-meta'),
		open: document.querySelector('#insp-open'),
		cv: document.querySelector('#insp-cv'),
		clear: document.querySelector('#insp-clear'),
		close: document.querySelector('#insp-close'),
		count: document.querySelector('#insp-count'),
		selection: document.querySelector('#insp-selection'),
		form: document.querySelector('#insp-form'),
		edition: document.querySelector('#insp-edition'),
		root_folder: document.querySelector('#insp-root-folder'),
		folder_field: document.querySelector('#insp-folder-field'),
		folder: document.querySelector('#insp-folder'),
		save: document.querySelector('#insp-save'),
		undo: document.querySelector('#insp-undo'),
		files: document.querySelector('#insp-files'),
		naming: document.querySelector('#insp-naming'),
		rename_details: document.querySelector('#insp-rename-details'),
		rename_list: document.querySelector('#insp-rename-list'),
		downloads_state: document.querySelector('#insp-downloads-state'),
		scheme: document.querySelector('#insp-scheme'),
		remove: document.querySelector('#insp-remove'),
		delete_folder: document.querySelector('#insp-delete-folder'),
		remove_button: document.querySelector('#insp-remove-button'),
		status: document.querySelector('#insp-status')
	}
};

const pre_build_els = {
	list_entry: document.querySelector('.pre-build-els .list-entry'),
	table_entry: document.querySelector('.pre-build-els .table-entry')
};

function isOrganizerMode() {
	return Boolean(document.documentElement?.classList?.contains('organizer-mode'));
};

function showLibraryPage(el) {
	hide(Object.values(library_els.pages), [el]);
};

const libraryVolumes = new Map();
const renderedViews = new Set();
// Series picked for the inspector. Selection lives here, not in the DOM, so
// both views and the inspector stay in step.
const selectedVolumes = new Set();
let selectionAnchor = null;
let activePublisher = new URLSearchParams(window.location?.search || '').get('publisher');
let rootFolders = null;
let inspectorRequest = 0;
let inspectorData = null;
let inspectorBusy = false;
let currentApiKey = null;
let inspectorSelectionKey = '';
// Rendered cover and row for each series, so selection changes don't search the DOM.
const entryElements = new Map();

function entriesFor(id) {
	return entryElements.get(id) || {};
}

const UNKNOWN_PUBLISHER = 'Unknown publisher';
const EDITION_NAMES = {
	'': 'Standard', 'tpb': 'Trade paperback', 'one-shot': 'One-shot',
	'hard-cover': 'Hardcover', 'omnibus': 'Omnibus',
	'volume-as-issue': 'Volume as issue', 'cover': 'Cover', 'metadata': 'Metadata'
};

class LibraryEntry {
	constructor(id, api_key, elements) {
		this.id = id;
		this.api_key = api_key;
		this.list_entry = elements ? elements.list_entry : library_els.views.list.querySelector(`.vol-${id}`);
		this.table_entry = elements ? elements.table_entry : library_els.views.table.querySelector(`.vol-${id}`);
	}

	setMonitored(monitored) {
		return sendAPI('PUT', `/volumes/${this.id}`, this.api_key, {}, { monitored })
		.then(() => {
			const volume = libraryVolumes.get(this.id);
			if (!volume) return;
			volume.monitored = monitored;
			const entry = new LibraryEntry(this.id, this.api_key);
			entry.updateMonitored(monitored);
			entry.setProgressBar(volume.issues_downloaded, volume.issue_count);
		});
	}

	updateMonitored(monitored) {
		if (this.list_entry) this.list_entry.toggleAttribute('monitored', monitored);
		if (this.table_entry) {
			const button = this.table_entry.querySelector('.table-monitored');
			setIcon(button, monitored ? icons.monitored : icons.unmonitored,
				monitored ? 'Monitored' : 'Unmonitored');
			button.onclick = () => this.setMonitored(!monitored);
		}
	}

	setProgressBar(downloaded_count, total_count) {
		downloaded_count = Math.min(downloaded_count, total_count);
		const progress = total_count > 0 ? downloaded_count / total_count * 100 : 0;
		for (const [entry, prefix] of [[this.list_entry, 'list'], [this.table_entry, 'table']]) {
			if (!entry) continue;
			entry.querySelector(`.${prefix}-prog-num`).innerText = prefix === 'list'
				? `${downloaded_count} of ${total_count} issues` : `${downloaded_count}/${total_count}`;
			const bar = entry.querySelector(`.${prefix}-prog-bar`);
			bar.style.width = `${progress}%`;
			// Organizer mode doesn't download, so an incomplete series isn't an error.
			const monitored = isOrganizerMode()
				|| (libraryVolumes.get(this.id)?.monitored ?? entry.hasAttribute('monitored'));
			bar.style.backgroundColor = progress === 100 ? 'var(--success-color)'
				: monitored ? (prefix === 'list' ? 'var(--progress-fill-color)' : 'var(--accent-color)') : 'var(--error-color)';
		}
		if (this.list_entry) this.list_entry.querySelector('.list-prog-container').title = total_count > 0
			? `${downloaded_count} of ${total_count} issues have files` : 'No issues';
	}
}

function publisherOf(volume) {
	return volume.publisher || UNKNOWN_PUBLISHER;
}

function inScope(volume) {
	return activePublisher === null || publisherOf(volume) === activePublisher;
}

function visibleVolumeIds() {
	return [...libraryVolumes.values()].filter(inScope).map(v => v.id);
}

function currentView() {
	return library_els.view_options.view.value === 'table' ? 'table' : 'list';
}

function populateLibrary(volumes, api_key) {
	libraryVolumes.clear();
	for (const volume of volumes) libraryVolumes.set(volume.id, volume);
	for (const id of [...selectedVolumes])
		if (!libraryVolumes.has(id)) selectedVolumes.delete(id);
	renderedViews.clear();
	entryElements.clear();
	library_els.views.list.querySelectorAll('.list-entry').forEach(e => e.remove());
	library_els.views.table.innerHTML = '';
	renderPublishers();
	renderLibraryView(api_key);
}

//
// Publishers
//
function publisherCounts() {
	const counts = new Map();
	for (const volume of libraryVolumes.values()) {
		const name = publisherOf(volume);
		counts.set(name, (counts.get(name) || 0) + 1);
	}
	return [...counts.entries()].sort(([a], [b]) => {
		if (a === UNKNOWN_PUBLISHER) return 1;
		if (b === UNKNOWN_PUBLISHER) return -1;
		return a.localeCompare(b, undefined, {sensitivity: 'base'});
	});
}

const TOP_PUBLISHER_CHIPS = 5;

function topPublishers(counts, limit=TOP_PUBLISHER_CHIPS) {
	// The biggest publishers become one-click chips; the one being shown
	// always gets a chip too.
	const top = [...counts]
		.filter(([name]) => name !== UNKNOWN_PUBLISHER)
		.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], undefined, {sensitivity: 'base'}))
		.slice(0, limit);
	if (activePublisher !== null && !top.some(([name]) => name === activePublisher)) {
		const active = counts.find(([name]) => name === activePublisher);
		if (active) top.unshift(active);
	}
	return top;
}

function publisherButton(name, label, count) {
	const button = document.createElement('button');
	button.type = 'button';
	button.dataset.publisher = name ?? '';
	button.setAttribute('aria-pressed', String(activePublisher === name));
	const text = document.createElement('span');
	text.textContent = label;
	const number = document.createElement('span');
	number.className = 'lb-count';
	number.textContent = count;
	button.append(text, number);
	return button;
}

function renderPublishers() {
	const counts = publisherCounts();
	if (libraryVolumes.size && activePublisher !== null
	&& !counts.some(([name]) => name === activePublisher))
		activePublisher = null;

	const container = library_els.publishers;
	container.innerHTML = '';
	const add = (name, label, count) => {
		const button = publisherButton(name, label, count);
		button.onclick = () => {
			setPublisher(name);
			closePublisherPicker(true);
		};
		container.appendChild(button);
	};
	add(null, 'All publishers', libraryVolumes.size);
	for (const [name, count] of counts) add(name, name, count);
	filterPublisherPicker();

	const chips = library_els.publisher_picker.chips;
	if (!chips) return;
	chips.innerHTML = '';
	for (const [name, count] of topPublishers(counts)) {
		const chip = publisherButton(name, name, count);
		chip.onclick = () => setPublisher(activePublisher === name ? null : name);
		chips.appendChild(chip);
	}
}

function filterPublisherPicker() {
	const picker = library_els.publisher_picker;
	if (!picker.search) return;
	const query = picker.search.value.trim().toLowerCase();
	let shown = 0;
	library_els.publishers.querySelectorAll('button').forEach(button => {
		const match = !query || button.textContent.toLowerCase().includes(query);
		button.classList.toggle('hidden', !match);
		if (match) shown++;
	});
	picker.none.classList.toggle('hidden', shown > 0);
}

function openPublisherPicker() {
	const picker = library_els.publisher_picker;
	picker.popover.classList.remove('hidden');
	picker.button.setAttribute('aria-expanded', 'true');
	picker.search.value = '';
	filterPublisherPicker();
	picker.search.focus();
	library_els.publishers.querySelector('[aria-pressed="true"]')?.scrollIntoView?.({block: 'nearest'});
}

function closePublisherPicker(focus=false) {
	const picker = library_els.publisher_picker;
	if (!picker.popover || picker.popover.classList.contains('hidden')) return false;
	picker.popover.classList.add('hidden');
	picker.button.setAttribute('aria-expanded', 'false');
	if (focus) picker.button.focus();
	return true;
}

function setPublisher(name) {
	if (activePublisher === name) return;
	activePublisher = name;
	selectedVolumes.clear();
	selectionAnchor = null;
	try {
		const url = new URL(window.location.href);
		if (name === null) url.searchParams.delete('publisher');
		else url.searchParams.set('publisher', name);
		window.history.replaceState(null, '', url);
	} catch (_) {}
	renderPublishers();
	applyScope();
	updateSelection();
	library_els.views[currentView()].closest('.lb-content')?.scrollTo?.(0, 0);
}

function applyScope() {
	for (const volume of libraryVolumes.values()) {
		const hidden = !inScope(volume);
		const {list, table} = entriesFor(volume.id);
		if (list) list.classList.toggle('hidden', hidden);
		if (table) table.classList.toggle('hidden', hidden);
	}
	const count = visibleVolumeIds().length;
	library_els.scope.title.textContent = activePublisher ?? 'All publishers';
	library_els.publisher_picker.button?.classList.toggle('is-filtered', activePublisher !== null);
	library_els.scope.count.textContent = `${count} series`;
}

function renderLibraryView(api_key) {
	const view = currentView();
	if (!renderedViews.has(view)) {
		const fragment = document.createDocumentFragment();
		for (const volume of libraryVolumes.values()) {
			const entry = pre_build_els[`${view}_entry`].cloneNode(true);
			entry.ariaLabel = `${volume.title} (${volume.year}) Volume ${volume.volume_number}`;
			entry.classList.add(`vol-${volume.id}`);
			entry.dataset.id = volume.id;
			const href = `${url_base}/volumes/${volume.id}`;
			if (view === 'list') {
				entry.href = href;
				entry.querySelector('.list-img').src = `${url_base}/api/volumes/${volume.id}/cover?api_key=${api_key}`;
				const title = entry.querySelector('.list-title');
				title.innerText = title.title = volume.title;
				entry.querySelector('.list-volume').innerText = `${volume.year ? volume.year + ', ' : ''}Volume ${volume.volume_number}`;
			} else {
				entry.querySelector('.table-link').href = href;
				entry.querySelector('.table-link').innerText = volume.title;
				entry.querySelector('.table-year').innerText = volume.year;
				entry.querySelector('.table-volume').innerText = `Volume ${volume.volume_number}`;
			}
			const instance = new LibraryEntry(volume.id, api_key, {
				list_entry: view === 'list' ? entry : null,
				table_entry: view === 'table' ? entry : null
			});
			instance.updateMonitored(volume.monitored);
			instance.setProgressBar(volume.issues_downloaded, volume.issue_count);
			entryElements.set(volume.id, {...entriesFor(volume.id), [view]: entry});
			fragment.appendChild(entry);
		}
		if (view === 'list') library_els.views.list.insertBefore(fragment, document.querySelector('.space-taker'));
		else library_els.views.table.appendChild(fragment);
		renderedViews.add(view);
	}
	applyScope();
	updateSelection();
}

function updateDownloadedStatus(data, api_key) {
	const volume = libraryVolumes.get(data.volume_id);
	if (!volume) return;
	volume.issues_downloaded = Math.max(0, Math.min(volume.issue_count,
		volume.issues_downloaded + data.downloaded_issues.length - data.not_downloaded_issues.length));
	new LibraryEntry(volume.id, api_key).setProgressBar(volume.issues_downloaded, volume.issue_count);
}

let libraryRequest = 0;
function fetchLibrary(api_key, quiet=false) {
	const request = ++libraryRequest;
	if (!quiet) showLibraryPage(library_els.pages.loading);

	const params = {
		sort: library_els.view_options.sort.value,
		filter: library_els.view_options.filter.value
	};
	const query = library_els.search.input.value;
	if (query !== '')
		params.query = query;

	return fetchAPI('/volumes', api_key, params)
	.then(json => {
		if (request !== libraryRequest) return;
		populateLibrary(json.result, api_key);
		if (json.result.length === 0) {
			const filtered = Boolean(query || params.filter);
			document.querySelector('#library-empty-title').textContent = filtered ? 'No matching comics' : 'Your collection starts here';
			document.querySelector('#library-empty-description').textContent = filtered
				? 'Try another title or clear your search and filters.'
				: 'Import the files you already have to get started.';
			document.querySelector('#reset-library').classList.toggle('hidden', !filtered);
			document.querySelector('#library-empty-actions').classList.toggle('hidden', filtered);
			showLibraryPage(library_els.pages.empty);
		} else {
			showLibraryPage(library_els.pages.view);
		};
		updateSelection();
	}).catch(() => {
		if (request === libraryRequest) showLibraryPage(library_els.pages.error);
	});
};

function searchLibrary() {
	usingApiKey().then(api_key => fetchLibrary(api_key));
};

function clearSearch(api_key) {
	library_els.search.input.value = '';
	library_els.search.input.focus();
	fetchLibrary(api_key);
};

function fetchStats(api_key) {
	fetchAPI('/volumes/stats', api_key)
	.then(json => {
		library_els.stats.volume_count.innerText = json.result.volumes;
		library_els.stats.volume_monitored_count.innerText = json.result.monitored;
		library_els.stats.volume_unmonitored_count.innerText = json.result.unmonitored;
		library_els.stats.issue_count.innerText = json.result.issues;
		library_els.stats.issue_download_count.innerText = json.result.downloaded_issues;
		library_els.stats.file_count.innerText = json.result.files;
		library_els.stats.total_file_size.innerText =
			json.result.total_file_size > 0
			? convertSize(json.result.total_file_size, 2)
			: '0 MB';
	});
};

//
// Selection
//
function selectOnly(id) {
	selectedVolumes.clear();
	selectedVolumes.add(id);
	selectionAnchor = id;
}

function toggleSelected(id) {
	if (selectedVolumes.has(id)) selectedVolumes.delete(id);
	else selectedVolumes.add(id);
	selectionAnchor = id;
}

function selectRange(id, keep=false) {
	const ids = visibleVolumeIds();
	const from = ids.indexOf(selectionAnchor), to = ids.indexOf(id);
	if (from === -1 || to === -1) return selectOnly(id);
	if (!keep) selectedVolumes.clear();
	for (const rid of ids.slice(Math.min(from, to), Math.max(from, to) + 1))
		selectedVolumes.add(rid);
}

function clickSelect(event, id) {
	const add = event.metaKey || event.ctrlKey;
	if (event.shiftKey && selectionAnchor !== null) selectRange(id, add);
	else if (add) toggleSelected(id);
	else selectOnly(id);
	updateSelection();
}

function clearSelection() {
	selectedVolumes.clear();
	selectionAnchor = null;
	updateSelection();
}

function updateSelection() {
	for (const volume of libraryVolumes.values()) {
		const selected = selectedVolumes.has(volume.id);
		const {list, table} = entriesFor(volume.id);
		if (list) list.classList.toggle('selected', selected);
		if (table) {
			table.classList.toggle('selected', selected);
			const box = table.querySelector('input[type="checkbox"]');
			if (box) box.checked = selected;
		}
	}
	const visible = visibleVolumeIds();
	const count = visible.filter(id => selectedVolumes.has(id)).length;
	library_els.select_all.checked = visible.length > 0 && count === visible.length;
	library_els.select_all.indeterminate = count > 0 && count < visible.length;
	library_els.main.classList.toggle('has-selection', selectedVolumes.size > 0);
	renderInspector();
}

//
// Inspector
//
function setInspectorStatus(text, error=false) {
	const status = library_els.inspector.status;
	status.textContent = text;
	status.classList.toggle('error', error);
}

function setInspectorBusy(busy) {
	inspectorBusy = busy;
	library_els.inspector.content.querySelectorAll('button, select, input').forEach(el => {
		if (el.id === 'insp-close' || el.id === 'insp-clear') return;
		if (busy) {
			el.dataset.wasDisabled = el.disabled ? '1' : '';
			el.disabled = true;
		} else {
			el.disabled = el.dataset.wasDisabled === '1';
			delete el.dataset.wasDisabled;
		}
	});
	if (!busy) updateDirty();
}

function selectedList() {
	return [...selectedVolumes].map(id => libraryVolumes.get(id)).filter(Boolean);
}

function fileName(path) {
	return String(path).split(/[\\/]/).pop();
}

function loadRootFolders(api_key) {
	if (rootFolders) return Promise.resolve(rootFolders);
	return fetchAPI('/rootfolder', api_key).then(json => {
		rootFolders = json.result;
		const select = library_els.inspector.root_folder;
		for (const rf of rootFolders) {
			const option = document.createElement('option');
			option.value = rf.id;
			option.textContent = rf.folder;
			select.appendChild(option);
		}
		return rootFolders;
	});
}

function editionLabel(data) {
	return EDITION_NAMES[data.special_version || ''] || data.special_version;
}

function inspectorOriginal() {
	if (selectedVolumes.size !== 1) return {edition: '__keep', root_folder: '__keep', folder: null};
	if (!inspectorData) return null;
	return {
		edition: inspectorData.special_version_locked ? (inspectorData.special_version || '') : 'auto',
		root_folder: String(inspectorData.root_folder),
		folder: inspectorData.volume_folder
	};
}

function updateDirty() {
	const insp = library_els.inspector;
	const original = inspectorOriginal();
	const dirty = Boolean(original) && (
		insp.edition.value !== original.edition
		|| insp.root_folder.value !== original.root_folder
		|| (original.folder !== null && insp.folder.value !== original.folder)
	);
	if (inspectorBusy) return;
	insp.save.disabled = !dirty;
	insp.undo.disabled = !dirty;
}

function resetInspectorForm() {
	const insp = library_els.inspector;
	const original = inspectorOriginal();
	if (!original) return;
	insp.edition.value = original.edition;
	insp.root_folder.value = original.root_folder;
	if (original.folder !== null) insp.folder.value = original.folder;
	updateDirty();
}

function renderNaming(previews) {
	const insp = library_els.inspector;
	const renames = Object.assign({}, ...previews);
	const count = Object.keys(renames).length;
	insp.rename_list.innerHTML = '';
	insp.naming.classList.toggle('warn', count > 0);
	if (count === 0) {
		insp.naming.textContent = 'All files follow your naming.';
		insp.rename_details.classList.add('hidden');
		return;
	}
	insp.naming.textContent = count === 1
		? '1 file doesn\'t follow your naming yet.'
		: `${count} files don't follow your naming yet.`;
	for (const [before, after] of Object.entries(renames).slice(0, 60)) {
		const item = document.createElement('li');
		const from = document.createElement('span');
		from.textContent = fileName(before);
		const to = document.createElement('span');
		to.textContent = fileName(after);
		item.append(from, to);
		insp.rename_list.appendChild(item);
	}
	insp.rename_details.classList.remove('hidden');
}

function checkNaming(ids, request) {
	const insp = library_els.inspector;
	insp.rename_details.classList.add('hidden');
	insp.naming.classList.remove('warn');
	if (ids.length > 20) {
		insp.naming.textContent = 'Select 20 series or fewer to check their file names.';
		return;
	}
	insp.naming.textContent = 'Checking file names…';
	Promise.all(ids.map(id => fetchAPI(`/volumes/${id}/rename`, currentApiKey).then(j => j.result)))
	.then(previews => {
		if (request === inspectorRequest) renderNaming(previews);
	})
	.catch(() => {
		if (request === inspectorRequest) insp.naming.textContent = '';
	});
}

function renderInspector() {
	const insp = library_els.inspector;
	if (!insp.root) return;
	const volumes = selectedList();
	const request = ++inspectorRequest;
	inspectorData = null;
	// Keep a result message while the same series stay selected.
	const key = volumes.map(v => v.id).sort((a, b) => a - b).join(',');
	if (key !== inspectorSelectionKey && !inspectorBusy) setInspectorStatus('');
	inspectorSelectionKey = key;

	if (!volumes.length) {
		insp.empty.classList.remove('hidden');
		insp.content.classList.add('hidden');
		return;
	}
	insp.empty.classList.add('hidden');
	insp.content.classList.remove('hidden');

	const single = volumes.length === 1;
	const first = volumes[0];
	if (insp.count) insp.count.textContent = single ? '1 series selected' : `${volumes.length} series selected`;
	insp.content.classList.toggle('multi', !single);
	insp.title.textContent = single ? first.title : `${volumes.length} series selected`;

	const publishers = new Set(volumes.map(publisherOf));
	const issues = volumes.reduce((n, v) => n + v.issue_count, 0);
	const with_files = volumes.reduce((n, v) => n + Math.min(v.issues_downloaded, v.issue_count), 0);
	const size = volumes.reduce((n, v) => n + (v.total_size || 0), 0);
	insp.meta.textContent = single
		? [first.year, `Volume ${first.volume_number}`, publisherOf(first)].filter(Boolean).join(' · ')
		: (publishers.size === 1 ? [...publishers][0] : `${publishers.size} publishers`);

	insp.cover.classList.toggle('hidden', !single);
	insp.stack.classList.toggle('hidden', single);
	insp.open.classList.toggle('hidden', !single);
	insp.cv.classList.add('hidden');
	if (single) {
		insp.cover.src = `${url_base}/api/volumes/${first.id}/cover?api_key=${currentApiKey}`;
		insp.open.href = `${url_base}/volumes/${first.id}`;
	} else {
		insp.stack.innerHTML = '';
		for (const v of volumes.slice(0, 3)) {
			const img = document.createElement('img');
			img.alt = '';
			img.src = `${url_base}/api/volumes/${v.id}/cover?api_key=${currentApiKey}`;
			insp.stack.appendChild(img);
		}
	}

	insp.selection.innerHTML = '';
	insp.selection.classList.toggle('hidden', single);
	if (!single) {
		for (const v of volumes.slice(0, 6)) {
			const item = document.createElement('li');
			item.textContent = `${v.title} (${v.year})`;
			insp.selection.appendChild(item);
		}
		if (volumes.length > 6) {
			const more = document.createElement('li');
			more.className = 'more';
			more.textContent = `and ${volumes.length - 6} more`;
			insp.selection.appendChild(more);
		}
	}

	// Details form
	const keep_edition = insp.edition.querySelector('option[value="__keep"]');
	const keep_root = insp.root_folder.querySelector('option[value="__keep"]');
	keep_edition.hidden = keep_edition.disabled = single;
	keep_root.hidden = keep_root.disabled = single;
	insp.folder_field.classList.toggle('hidden', !single);
	insp.edition.querySelector('option[value="auto"]').textContent = 'Detect automatically';
	if (!single) {
		insp.edition.value = '__keep';
		insp.root_folder.value = '__keep';
	}
	insp.save.textContent = single ? 'Save' : `Save for ${volumes.length} series`;
	updateDirty();

	// Files
	insp.files.textContent = `${with_files} of ${issues} issues have files`
		+ (size > 0 ? ` · ${convertSize(size, 1)}` : '');
	checkNaming(volumes.map(v => v.id), request);

	// Downloads and removal
	const monitored = volumes.filter(v => v.monitored).length;
	insp.downloads_state.textContent = single
		? (monitored ? 'Monitored' : 'Off')
		: (monitored === 0 ? 'Off for all' : `${monitored} of ${volumes.length} monitored`);
	insp.remove_button.textContent = single ? 'Remove this series' : `Remove ${volumes.length} series`;

	if (single) {
		Promise.all([
			fetchAPI(`/volumes/${first.id}`, currentApiKey),
			loadRootFolders(currentApiKey)
		]).then(([json]) => {
			if (request !== inspectorRequest) return;
			inspectorData = json.result;
			insp.cv.href = inspectorData.site_url;
			insp.cv.classList.toggle('hidden', !inspectorData.site_url);
			if (!inspectorData.special_version_locked)
				insp.edition.querySelector('option[value="auto"]').textContent =
					`Detect automatically (${editionLabel(inspectorData)})`;
			resetInspectorForm();
		}).catch(() => {
			if (request === inspectorRequest) setInspectorStatus('Couldn\'t load this series.', true);
		});
	} else {
		loadRootFolders(currentApiKey).catch(() => {});
	}
}

async function errorText(error) {
	const json = await apiError(error);
	return json.result?.description || json.error || 'Something went wrong.';
}

function massEdit(api_key, action, volume_ids, args={}) {
	return sendAPI('POST', '/masseditor', api_key, {}, {volume_ids, action, args});
}

const ACTION_DONE = {
	rename: 'Files renamed.',
	convert: 'Files converted.',
	update: 'Refreshed and scanned.',
	monitor: 'Monitoring is on.',
	unmonitor: 'Monitoring is off.',
	monitoring_scheme: 'Issue monitoring updated.',
	search: 'Search finished. Anything found was added to the queue.',
	root_folder: 'Saved.',
	special_version: 'Saved.'
};

function runAction(api_key, action, args={}) {
	const volume_ids = [...selectedVolumes];
	if (!volume_ids.length || inspectorBusy) return;
	if (action === 'delete') {
		args = {delete_folder: Boolean(library_els.inspector.delete_folder.checked), ...args};
		const what = volume_ids.length === 1 ? 'this series' : `${volume_ids.length} series`;
		if (!window.confirm(
			`Remove ${what} from your library?${args.delete_folder ? ' Their folders and files will also be permanently deleted.' : ' The files stay on disk.'}`
		)) return;
	}
	if (action === 'monitoring_scheme' && !args.monitoring_scheme)
		args = {monitoring_scheme: library_els.inspector.scheme.value};

	setInspectorBusy(true);
	setInspectorStatus('Working…');
	return massEdit(api_key, action, volume_ids, args)
	.then(() => {
		if (action === 'delete') {
			selectedVolumes.clear();
			inspectorSelectionKey = '';
			library_els.inspector.remove.open = false;
			library_els.inspector.delete_folder.checked = false;
		}
		setInspectorBusy(false);
		setInspectorStatus(action === 'delete'
			? `Removed ${volume_ids.length} series.` : ACTION_DONE[action] || 'Done.');
		fetchLibrary(api_key, true);
		fetchStats(api_key);
	})
	.catch(async error => {
		setInspectorBusy(false);
		setInspectorStatus(`Couldn't finish: ${await errorText(error)}`, true);
	});
};

function saveInspector(api_key) {
	const insp = library_els.inspector;
	const ids = [...selectedVolumes];
	if (!ids.length || insp.save.disabled) return;
	const edition = insp.edition.value, root = insp.root_folder.value;
	let work;

	if (ids.length === 1) {
		const original = inspectorOriginal();
		if (!original) return;
		const data = {};
		if (root !== original.root_folder) data.root_folder = parseInt(root);
		if (insp.folder.value !== original.folder) data.volume_folder = insp.folder.value;
		if (edition !== original.edition) {
			data.special_version_locked = edition !== 'auto';
			if (edition !== 'auto') data.special_version = edition || null;
		}
		work = sendAPI('PUT', `/volumes/${ids[0]}`, api_key, {}, data);
	} else {
		work = Promise.resolve();
		if (edition !== '__keep')
			work = work.then(() => massEdit(api_key, 'special_version', ids, {special_version: edition}));
		if (root !== '__keep')
			work = work.then(() => massEdit(api_key, 'root_folder', ids, {root_folder_id: parseInt(root)}));
	}

	setInspectorBusy(true);
	setInspectorStatus('Saving…');
	return work.then(() => {
		setInspectorBusy(false);
		setInspectorStatus(ids.length === 1 ? 'Saved.' : `Saved for ${ids.length} series.`);
		return fetchLibrary(api_key, true);
	}).catch(async error => {
		setInspectorBusy(false);
		setInspectorStatus(`Couldn't save: ${await errorText(error)}`, true);
	});
}

function isTyping(target) {
	return target && target.closest && Boolean(target.closest('input, select, textarea, [contenteditable]'));
}

// code run on load

const lib_options = getLocalStorage('lib_sorting', 'lib_view', 'lib_filter');
library_els.view_options.sort.value = lib_options.lib_sorting;
library_els.view_options.view.value = lib_options.lib_view;
library_els.view_options.filter.value = lib_options.lib_filter;

usingApiKey()
.then(api_key => {
	currentApiKey = api_key;
	fetchLibrary(api_key);
	fetchStats(api_key);

	library_els.search.clear.onclick =
		e => clearSearch(api_key);

	library_els.task_buttons.update_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {
			'cmd': 'update_all',
			'allow_skipping': false
		});

	document.querySelector('#searchall-button').onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {
			'cmd': 'search_all',
			'allow_skipping': false
		});

	library_els.view_options.sort.onchange = e => {
		setLocalStorage({'lib_sorting': library_els.view_options.sort.value});
		fetchLibrary(api_key);
	};
	library_els.view_options.view.onchange = () => {
		setLocalStorage({'lib_view': library_els.view_options.view.value});
		renderLibraryView(api_key);
	};
	library_els.view_options.filter.onchange = e => {
		setLocalStorage({'lib_filter': library_els.view_options.filter.value});
		fetchLibrary(api_key);
	};

	const insp = library_els.inspector;
	insp.form.addEventListener('submit', e => {
		e.preventDefault();
		saveInspector(api_key);
	});
	insp.undo.onclick = resetInspectorForm;
	[insp.edition, insp.root_folder, insp.folder].forEach(el => {
		el.addEventListener('input', updateDirty);
		el.addEventListener('change', updateDirty);
	});
	insp.content.querySelectorAll('[data-insp-action]').forEach(button =>
		button.onclick = () => runAction(api_key, button.dataset.inspAction)
	);

	socket_ready.then(socket => socket.on(
		'downloaded_status',
		data => updateDownloadedStatus(data, api_key)
	));
	// Socket is init after API key so wait for that like this
	socket_ready.then(socket => socket.on(
		'mass_editor_status',
		data => {
			if (inspectorBusy)
				setInspectorStatus(`Working… ${data.current_item} of ${data.total_items}`);
		}
	));
});
library_els.search.container.addEventListener('submit', event => {
	event.preventDefault();
	searchLibrary();
});
let searchTimer;
library_els.search.input.addEventListener('input', () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(searchLibrary, 250);
});
document.querySelector('#retry-library').onclick = searchLibrary;
document.querySelector('#reset-library').onclick = () => {
	library_els.search.input.value = '';
	library_els.view_options.filter.value = '';
	setLocalStorage({lib_filter: ''});
	searchLibrary();
};

// Covers: click selects, modifier keys extend, double-click opens.
library_els.views.list.addEventListener('click', event => {
	const entry = event.target.closest('.list-entry');
	if (!entry || event.button !== 0) return;
	event.preventDefault();
	const id = parseInt(entry.dataset.id);
	if (event.target.closest('.list-check')) {
		toggleSelected(id);
		updateSelection();
	} else clickSelect(event, id);
});
library_els.views.list.addEventListener('dblclick', event => {
	const entry = event.target.closest('.list-entry');
	if (entry) window.location.href = entry.href;
});

// List rows: the checkbox toggles, a row click selects, the title link opens.
library_els.views.table.addEventListener('click', event => {
	const row = event.target.closest('.table-entry');
	if (!row || event.target.closest('a, button, input, label')) return;
	clickSelect(event, parseInt(row.dataset.id));
});
library_els.views.table.addEventListener('change', event => {
	const row = event.target.closest('.table-entry');
	if (!row) return;
	const id = parseInt(row.dataset.id);
	if (event.target.checked) selectedVolumes.add(id);
	else selectedVolumes.delete(id);
	selectionAnchor = id;
	updateSelection();
});
library_els.select_all.onchange = () => {
	for (const id of visibleVolumeIds()) {
		if (library_els.select_all.checked) selectedVolumes.add(id);
		else selectedVolumes.delete(id);
	}
	updateSelection();
};
library_els.inspector.clear.onclick = clearSelection;
library_els.inspector.close.onclick = clearSelection;

document.addEventListener('keydown', event => {
	if (event.key === 'Escape' && closePublisherPicker(true)) return;
	if (isTyping(event.target) || event.altKey) return;
	if (event.key === 'Escape' && selectedVolumes.size) {
		if (document.querySelector('.library-tools[open]')) return;
		clearSelection();
	} else if (event.key.toLowerCase() === 'a' && (event.metaKey || event.ctrlKey)
	&& !library_els.pages.view.classList.contains('hidden')) {
		event.preventDefault();
		visibleVolumeIds().forEach(id => selectedVolumes.add(id));
		updateSelection();
	}
});

const library_tools = document.querySelector('.library-tools');
library_tools.querySelectorAll('button').forEach(button => {
	button.addEventListener('click', () => {
		library_tools.open = false;
		library_tools.querySelector('summary').focus();
	});
});

// Publisher picker: a searchable list in a popover.
const publisher_picker = library_els.publisher_picker;
publisher_picker.button.onclick = () => {
	if (publisher_picker.popover.classList.contains('hidden')) openPublisherPicker();
	else closePublisherPicker();
};
publisher_picker.search.addEventListener('input', filterPublisherPicker);
publisher_picker.search.addEventListener('keydown', event => {
	const shown = [...library_els.publishers.querySelectorAll('button:not(.hidden)')];
	if (event.key === 'Enter') {
		event.preventDefault();
		shown[0]?.click();
	} else if (event.key === 'ArrowDown') {
		event.preventDefault();
		shown[0]?.focus();
	}
});
library_els.publishers.addEventListener('keydown', event => {
	if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
	event.preventDefault();
	const shown = [...library_els.publishers.querySelectorAll('button:not(.hidden)')];
	const index = shown.indexOf(document.activeElement);
	if (event.key === 'ArrowUp' && index <= 0) publisher_picker.search.focus();
	else shown[Math.min(shown.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1))]?.focus();
});
document.addEventListener('click', event => {
	if (!event.target.closest('.lb-picker')) closePublisherPicker();
});
