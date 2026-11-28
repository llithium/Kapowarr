// Series page: the issue list on the left, and a docked panel on the right
// that edits the series or shows the selected issue. Everything that used to
// open in a window (edit, delete, rename, convert, file matching, general
// files, issue info) lives in the panel now. Only "Find links" is a window.

const ViewEls = {
	views: {
		loading: document.querySelector('#loading-screen'),
		main: document.querySelector('main')
	},
	pre_build: {
		issue_entry: document.querySelector('.pre-build-els .issue-entry'),
		manual_search: document.querySelector('.pre-build-els .search-entry')
	},
	vol_data: {
		monitor: document.querySelector('#volume-monitor'),
		title: document.querySelector('#sp-title'),
		cover: document.querySelector('#sp-cover'),
		meta: document.querySelector('#sp-meta'),
		chips: document.querySelector('#sp-chips'),
		path: document.querySelector('#volume-path'),
		cv: document.querySelector('#sp-cv'),
		description: document.querySelector('#volume-description')
	},
	vol_edit: {
		form: document.querySelector('#sp-form'),
		monitor: document.querySelector('#monitored-input'),
		monitor_new_issues: document.querySelector('#monitor-issues-input'),
		monitoring_scheme: document.querySelector('#monitoring-scheme-input'),
		root_folder: document.querySelector('#root-folder-input'),
		volume_folder: document.querySelector('#volumefolder-input'),
		special_version: document.querySelector('#specialoverride-input'),
		save: document.querySelector('#sp-save'),
		undo: document.querySelector('#sp-undo'),
		open_folder: document.querySelector('#sp-open-folder'),
		status: document.querySelector('#sp-form-status')
	},
	tool_bar: {
		refresh: document.querySelector('#refresh-button'),
		auto_search: document.querySelector('#autosearch-button'),
		manual_search: document.querySelector('#manualsearch-button'),
		rename: document.querySelector('#rename-button'),
		convert: document.querySelector('#convert-button'),
		editor: document.querySelector('#open-editor')
	},
	panel: {
		root: document.querySelector('#sp-panel'),
		tab_series: document.querySelector('#tab-series'),
		tab_issue: document.querySelector('#tab-issue'),
		series: document.querySelector('#panel-series'),
		issue: document.querySelector('#panel-issue'),
		close: document.querySelector('#close-panel')
	},
	issues_list: document.querySelector('#issues-list')
};

const enqueueFailureReasonMap = {
	webpage_broken: "Webpage unavailable",
	no_matches: "No links found on webpage that match to volume and are not blocklisted",
	no_working_links: "All download links found on the webpage are broken",
	only_rate_limited_links: "All working download links on the webpage are from rate limited services",

	link_broken: "Download link broken",
	link_rate_limited: "Download link rate limited"
};

const EDITION_NAMES = {
	'': 'Standard', 'tpb': 'Trade paperback', 'one-shot': 'One-shot',
	'hard-cover': 'Hardcover', 'omnibus': 'Omnibus',
	'volume-as-issue': 'Volume as issue', 'cover': 'Cover', 'metadata': 'Metadata'
};

//
// Issue rows
//
function updateIssueSummary() {
	const rows = ViewEls.issues_list.querySelectorAll('.issue-entry');
	const with_files = ViewEls.issues_list.querySelectorAll('.issue-status.success');
	document.querySelector('#issue-summary').textContent =
		`${with_files.length} of ${rows.length} issues have files`;
};

class IssueEntry {
	constructor(id, api_key, row_entry=null) {
		this.id = id;
		this.api_key = api_key;
		this.entry = row_entry !== null
			? row_entry
			: ViewEls.issues_list.querySelector(`tr[data-id="${id}"]`);
		this.monitored = this.entry.querySelector('.issue-monitored button');
		this.status = this.entry.querySelector('.issue-status');
	};

	setMonitorIcon() {
		const monitored = this.monitored.dataset.monitored === 'true';
		setIcon(this.monitored, monitored ? icons.monitored : icons.unmonitored,
			monitored ? 'Issue is monitored. Click to stop monitoring.' : 'Issue is not monitored. Click to monitor.');
	};

	toggleMonitored() {
		const monitored = this.monitored.dataset.monitored !== 'true';
		sendAPI('PUT', `/issues/${this.id}`, this.api_key, {}, {monitored})
		.then(() => {
			this.monitored.dataset.monitored = monitored;
			const issue = seriesIssues().find(i => i.id === this.id);
			if (issue) issue.monitored = monitored;
			this.setMonitorIcon();
		});
	};

	setDownloaded(downloaded, update_summary=true) {
		this.status.classList.toggle('success', Boolean(downloaded));
		this.status.classList.toggle('error', !downloaded);
		this.status.title = downloaded ? 'This issue has a file' : 'No file for this issue yet';
		this.status.querySelector('.issue-status-label').textContent = downloaded ? 'Has file' : 'Missing';
		if (update_summary) updateIssueSummary();
	};
};

let seriesData = null;
function seriesIssues() {
	return seriesData ? seriesData.issues : [];
}

function fillTable(issues, api_key) {
	ViewEls.issues_list.innerHTML = '';
	// Newest issue first, like the old list.
	for (let i = issues.length - 1; i >= 0; i--) {
		const obj = issues[i];
		const entry = ViewEls.pre_build.issue_entry.cloneNode(true);
		entry.dataset.id = obj.id;
		entry.tabIndex = 0;
		entry.ariaLabel = `Issue ${obj.issue_number}${obj.title ? ': ' + obj.title : ''}`;
		ViewEls.issues_list.appendChild(entry);

		const inst = new IssueEntry(obj.id, api_key, entry);
		inst.monitored.dataset.monitored = obj.monitored;
		inst.monitored.dataset.id = obj.id;
		inst.monitored.onclick = e => {
			e.stopPropagation();
			inst.toggleMonitored();
		};
		inst.setMonitorIcon();

		entry.querySelector('.issue-number').textContent = obj.issue_number;
		entry.querySelector('.issue-title-label').textContent = obj.title || `Issue #${obj.issue_number}`;
		entry.querySelector('.issue-title-label').classList.toggle('untitled', !obj.title);
		entry.querySelector('.issue-date').textContent = obj.date || '';
		entry.querySelector('.issue-inline-date').textContent = obj.date || '';
		inst.setDownloaded(obj.files.length, false);
		entry.classList.toggle('selected', obj.id === selectedIssueId);
	};
	updateIssueSummary();
	applyIssueFilter();
};

let issueFilter = 'all';
function applyIssueFilter() {
	let shown = 0;
	ViewEls.issues_list.querySelectorAll('.issue-entry').forEach(row => {
		const has_file = row.querySelector('.issue-status').classList.contains('success');
		const show = issueFilter === 'all'
			|| (issueFilter === 'missing' && !has_file)
			|| (issueFilter === 'files' && has_file);
		row.classList.toggle('hidden', !show);
		if (show) shown++;
	});
	document.querySelector('#issues-empty').classList.toggle('hidden', shown > 0);
	document.querySelectorAll('.sp-filter button').forEach(b =>
		b.setAttribute('aria-pressed', String(b.dataset.filter === issueFilter)));
}

//
// Small helpers
//
function shortPath(filepath) {
	const folder = seriesData?.folder;
	if (folder && filepath.startsWith(folder))
		return filepath.slice(folder.length).replace(/^[\\/]/, '');
	return filepath.split(/[\\/]/).pop();
}

function fileName(path) {
	return String(path).split(/[\\/]/).pop();
}

function setStatus(el, text, error=false) {
	el.textContent = text;
	el.classList.toggle('error', error);
}

async function errorText(error) {
	const json = await apiError(error);
	return json.result?.description || json.error || 'Something went wrong.';
}

function issueLabel(issue_id) {
	const issue = seriesIssues().find(i => i.id === issue_id);
	return issue ? `#${issue.issue_number}` : `#?`;
}

//
// Header
//
function setVolumeMonitor(monitored) {
	const monitor = ViewEls.vol_data.monitor;
	setIcon(monitor, monitored ? icons.monitored : icons.unmonitored,
		monitored ? 'Series is monitored. Click to stop monitoring.' : 'Series is not monitored. Click to monitor.');
	const label = document.createElement('span');
	label.textContent = monitored ? 'Monitored' : 'Not monitored';
	monitor.appendChild(label);
	monitor.classList.toggle('on', monitored);
	ViewEls.vol_edit.monitor.checked = monitored;
	document.querySelector('#downloads-state').textContent = monitored ? 'Monitored' : 'Off';
};

function fillHeader(data, api_key) {
	ViewEls.vol_data.cover.src = `${url_base}/api/volumes/${data.id}/cover?api_key=${api_key}`;
	ViewEls.vol_data.cover.alt = `${data.title} cover`;
	ViewEls.vol_data.title.textContent = data.title;
	document.title = `${data.title} - Kapowarr`;

	const meta = [data.year, `Volume ${data.volume_number || 1}`, data.publisher].filter(Boolean);
	ViewEls.vol_data.meta.textContent = meta.join(' · ');

	const chips = ViewEls.vol_data.chips;
	chips.innerHTML = '';
	const chip = (text, cls='') => {
		const el = document.createElement('span');
		el.className = `sp-chip ${cls}`;
		el.textContent = text;
		chips.appendChild(el);
	};
	const with_files = data.issues.filter(i => i.files.length).length;
	chip(`${with_files} of ${data.issues.length} issues`, with_files === data.issues.length && data.issues.length ? 'ok' : '');
	chip(data.total_size > 0 ? convertSize(data.total_size, 1) : '0 MB');
	chip(EDITION_NAMES[data.special_version || ''] || data.special_version);

	ViewEls.vol_data.path.textContent = data.folder;
	ViewEls.vol_data.path.title = data.folder;
	ViewEls.vol_data.cv.href = data.site_url || '#';
	ViewEls.vol_data.cv.classList.toggle('hidden', !data.site_url);
	ViewEls.vol_data.description.innerHTML = data.description || '<p>No description.</p>';

	const monitor = ViewEls.vol_data.monitor;
	monitor.dataset.monitored = data.monitored;
	monitor.onclick = () => setSeriesMonitored(api_key, monitor.dataset.monitored !== 'true');
	setVolumeMonitor(data.monitored);
	ViewEls.vol_edit.monitor_new_issues.checked = Boolean(data.monitor_new_issues);
}

function setSeriesMonitored(api_key, monitored) {
	return sendAPI('PUT', `/volumes/${volume_id}`, api_key, {}, {monitored})
	.then(() => {
		ViewEls.vol_data.monitor.dataset.monitored = monitored;
		if (seriesData) seriesData.monitored = monitored;
		setVolumeMonitor(monitored);
	});
}

//
// Loading
//
let currentApiKey = null;
function loadSeries(api_key) {
	return fetchAPI(`/volumes/${volume_id}`, api_key)
	.then(json => {
		seriesData = json.result;
		fillHeader(seriesData, api_key);
		fillTable(seriesData.issues, api_key);
		fillDetails(api_key);
		fillOtherFiles(api_key);
		loadPreviews(api_key);
		loadMatches(api_key);
		if (selectedIssueId !== null) showIssue(selectedIssueId, api_key, false);
		mapButtons(volume_id);
		hide([ViewEls.views.loading], [ViewEls.views.main]);
	});
}

// Rename, convert and refresh run as background tasks. Reload once none of
// this series' tasks are left, so the page shows the result.
let taskWatch = null;
function reloadWhenTasksFinish(api_key, onDone=null) {
	clearTimeout(taskWatch);
	const started = Date.now();
	const check = () => fetchAPI('/system/tasks', api_key).then(json => {
		const busy = json.result.some(t => t.volume_id === volume_id);
		if (busy && Date.now() - started < 10 * 60 * 1000) {
			taskWatch = setTimeout(check, 1000);
			return;
		}
		loadSeries(api_key).then(() => onDone && onDone());
	}).catch(() => { taskWatch = setTimeout(check, 3000); });
	taskWatch = setTimeout(check, 600);
}

function runTask(api_key, data, onDone=null) {
	return sendAPI('POST', '/system/tasks', api_key, {}, {volume_id, ...data})
	.then(() => reloadWhenTasksFinish(api_key, onDone));
}

//
// Panel
//
let selectedIssueId = null;
function openPanel(tab) {
	const series = tab === 'series';
	ViewEls.panel.tab_series.setAttribute('aria-selected', String(series));
	ViewEls.panel.tab_issue.setAttribute('aria-selected', String(!series));
	ViewEls.panel.series.classList.toggle('hidden', !series);
	ViewEls.panel.issue.classList.toggle('hidden', series);
	ViewEls.views.main.classList.add('panel-open');
}

function closePanel() {
	ViewEls.views.main.classList.remove('panel-open');
}

//
// Details form
//
let rootFoldersLoaded = false;
function detailsOriginal() {
	if (!seriesData) return null;
	return {
		edition: seriesData.special_version_locked ? (seriesData.special_version || '') : 'auto',
		root_folder: String(seriesData.root_folder),
		folder: seriesData.volume_folder
	};
}

function updateDetailsDirty() {
	const e = ViewEls.vol_edit, o = detailsOriginal();
	const dirty = Boolean(o) && (e.special_version.value !== o.edition
		|| e.root_folder.value !== o.root_folder || e.volume_folder.value !== o.folder);
	e.save.disabled = !dirty;
	e.undo.disabled = !dirty;
}

function resetDetails() {
	const e = ViewEls.vol_edit, o = detailsOriginal();
	if (!o) return;
	e.special_version.value = o.edition;
	if (rootFoldersLoaded) e.root_folder.value = o.root_folder;
	e.volume_folder.value = o.folder;
	updateDetailsDirty();
}

function fillDetails(api_key) {
	const auto = ViewEls.vol_edit.special_version.querySelector('option[value="auto"]');
	auto.textContent = seriesData.special_version_locked
		? 'Detect automatically'
		: `Detect automatically (${EDITION_NAMES[seriesData.special_version || ''] || seriesData.special_version})`;
	const ready = rootFoldersLoaded ? Promise.resolve() : fetchAPI('/rootfolder', api_key).then(json => {
		const select = ViewEls.vol_edit.root_folder;
		select.innerHTML = '';
		json.result.forEach(rf => {
			const option = document.createElement('option');
			option.value = rf.id;
			option.textContent = rf.folder;
			select.appendChild(option);
		});
		rootFoldersLoaded = true;
	});
	ready.then(resetDetails);
}

function saveDetails(api_key) {
	const e = ViewEls.vol_edit, o = detailsOriginal();
	if (!o || e.save.disabled) return;
	const data = {};
	if (e.root_folder.value !== o.root_folder) data.root_folder = parseInt(e.root_folder.value);
	if (e.volume_folder.value !== o.folder) data.volume_folder = e.volume_folder.value;
	if (e.special_version.value !== o.edition) {
		data.special_version_locked = e.special_version.value !== 'auto';
		if (data.special_version_locked) data.special_version = e.special_version.value || null;
	}
	e.save.disabled = e.undo.disabled = true;
	setStatus(e.status, 'Saving…');
	sendAPI('PUT', `/volumes/${volume_id}`, api_key, {}, data)
	.then(() => loadSeries(api_key))
	.then(() => setStatus(e.status, 'Saved.'))
	.catch(async error => {
		setStatus(e.status, `Couldn't save: ${await errorText(error)}`, true);
		updateDetailsDirty();
	});
}

function openFolder(api_key) {
	const e = ViewEls.vol_edit;
	e.open_folder.disabled = true;
	setStatus(e.status, '');
	sendAPI('POST', `/volumes/${volume_id}/openfolder`, api_key)
	.catch(async error => {
		const json = await apiError(error);
		if (json.error === 'FolderNotFound')
			setStatus(e.status, "This folder isn't on disk yet. Kapowarr creates it when files are added.", true);
		else
			setStatus(e.status, `Couldn't open the folder: ${json.result?.description || json.error || 'Something went wrong.'}`, true);
	})
	.finally(() => e.open_folder.disabled = false);
}

//
// Rename and convert previews
//
function renderChanges(list, mapping, limit=80) {
	list.innerHTML = '';
	for (const [before, after] of Object.entries(mapping).slice(0, limit)) {
		const item = document.createElement('li');
		const label = document.createElement('label');
		const box = document.createElement('input');
		box.type = 'checkbox';
		box.checked = true;
		box.dataset.filepath = before;
		const text = document.createElement('span');
		const from = document.createElement('span');
		from.className = 'from';
		from.textContent = shortPath(before);
		const to = document.createElement('span');
		to.className = 'to';
		to.textContent = shortPath(after);
		text.append(from, to);
		label.append(box, text);
		item.appendChild(label);
		list.appendChild(item);
	}
}

function checkedPaths(list) {
	return [...list.querySelectorAll('input[type="checkbox"]:checked')].map(b => b.dataset.filepath);
}

function setPreview(kind, mapping) {
	const count = Object.keys(mapping).length;
	const list = document.querySelector(`#${kind}-list`);
	const summary = document.querySelector(`#${kind}-summary`);
	const button = kind === 'rename' ? ViewEls.tool_bar.rename : ViewEls.tool_bar.convert;
	renderChanges(list, mapping);
	button.classList.toggle('hidden', count === 0);
	summary.classList.toggle('warn', count > 0);
	if (kind === 'rename') {
		summary.textContent = count === 0 ? 'All files follow your naming.'
			: `${count} ${count === 1 ? 'file doesn\'t' : 'files don\'t'} follow your naming yet.`;
		button.querySelector('span').textContent = count === 1 ? 'Rename 1 file' : `Rename ${count} files`;
	} else {
		summary.textContent = count === 0 ? 'All files are in your preferred format.'
			: `${count} ${count === 1 ? 'file' : 'files'} can be converted to your preferred format.`;
		button.querySelector('span').textContent = count === 1 ? 'Convert 1 file' : `Convert ${count} files`;
	}
}

let previewsRequest = 0;
function loadPreviews(api_key) {
	const request = ++previewsRequest;
	document.querySelector('#rename-summary').textContent = 'Checking file names…';
	document.querySelector('#convert-summary').textContent = 'Checking formats…';
	fetchAPI(`/volumes/${volume_id}/rename`, api_key)
	.then(json => { if (request === previewsRequest) setPreview('rename', json.result); })
	.catch(() => { document.querySelector('#rename-summary').textContent = ''; });
	fetchAPI(`/volumes/${volume_id}/convert`, api_key)
	.then(json => { if (request === previewsRequest) setPreview('convert', json.result); })
	.catch(() => { document.querySelector('#convert-summary').textContent = ''; });
	loadConvertPreference(api_key);
}

function loadConvertPreference(api_key) {
	const el = document.querySelector('#convert-preference');
	if (el.textContent !== '') return;
	fetchAPI('/settings', api_key).then(json => {
		const formats = json.result.format_preference;
		el.textContent = formats.length
			? `Preferred formats, in order: ${formats.join(', ')}.`
			: 'No preferred format is set, so nothing is converted. Set one in Media management settings.';
	});
}

function runRenameOrConvert(api_key, kind) {
	const list = document.querySelector(`#${kind}-list`);
	const paths = checkedPaths(list);
	if (!paths.length) return;
	const button = kind === 'rename' ? ViewEls.tool_bar.rename : ViewEls.tool_bar.convert;
	button.disabled = true;
	document.querySelector(`#${kind}-summary`).textContent = kind === 'rename' ? 'Renaming…' : 'Converting…';
	runTask(api_key, {
		cmd: kind === 'rename' ? 'mass_rename' : 'mass_convert',
		filepath_filter: paths
	}, () => { button.disabled = false; });
}

//
// File matching (was "Manage issues")
//
let matchOriginal = [];
let matchChanges = new Map();

function matchValue(mapping) {
	if (mapping.general_file) return 'general';
	if (!mapping.forced_match || !mapping.issue_ids.length) return mapping.issue_ids.length ? `auto:${mapping.issue_ids.join(',')}` : 'auto';
	return `issue:${mapping.issue_ids.join(',')}`;
}

function matchLabel(mapping) {
	if (mapping.general_file) return 'Other file';
	if (!mapping.issue_ids.length) return 'Not matched';
	const first = issueLabel(mapping.issue_ids[0]);
	const last = issueLabel(mapping.issue_ids[mapping.issue_ids.length - 1]);
	return mapping.issue_ids.length > 1 ? `${first} – ${last}` : first;
}

function matchOptions(select, mapping) {
	const add = (value, text) => {
		const option = document.createElement('option');
		option.value = value;
		option.textContent = text;
		select.appendChild(option);
	};
	const current = matchValue(mapping);
	add(current.startsWith('auto') ? current : 'auto',
		mapping.forced_match || !mapping.issue_ids.length
			? 'Match automatically'
			: `Automatic (${matchLabel(mapping)})`);
	if (current.startsWith('issue:') && mapping.issue_ids.length > 1)
		add(current, `${matchLabel(mapping)} (set by you)`);
	add('general', 'Other file (cover, extras)');
	for (const issue of seriesIssues())
		add(`issue:${issue.id}`, `#${issue.issue_number}${issue.title ? ' · ' + issue.title : ''}`);
	select.value = current;
}

function changeFromValue(filepath, value) {
	if (value.startsWith('auto'))
		return {filepath, issue_ids: [], general_file: false, forced_match: false};
	if (value === 'general')
		return {filepath, issue_ids: [], general_file: true, forced_match: true};
	return {filepath, issue_ids: value.slice(6).split(',').map(Number), general_file: false, forced_match: true};
}

function updateMatchButtons() {
	const changed = matchChanges.size > 0;
	document.querySelector('#match-save').classList.toggle('hidden', !changed);
	document.querySelector('#match-undo').classList.toggle('hidden', !changed);
	document.querySelector('#match-save').textContent = matchChanges.size === 1
		? 'Save 1 change' : `Save ${matchChanges.size} changes`;
}

function renderMatches() {
	const list = document.querySelector('#match-list');
	list.innerHTML = '';
	matchChanges.clear();
	updateMatchButtons();
	if (!matchOriginal.length) {
		const empty = document.createElement('li');
		empty.className = 'sp-note';
		empty.textContent = 'No files in this folder yet.';
		list.appendChild(empty);
		return;
	}
	matchOriginal.forEach(mapping => {
		const item = document.createElement('li');
		item.className = 'sp-file';
		const name = document.createElement('span');
		name.className = 'sp-file-name';
		name.textContent = shortPath(mapping.filepath);
		name.title = mapping.filepath;
		const select = document.createElement('select');
		select.setAttribute('aria-label', `Issue for ${fileName(mapping.filepath)}`);
		matchOptions(select, mapping);
		const original = select.value;
		select.onchange = () => {
			if (select.value === original) matchChanges.delete(mapping.filepath);
			else matchChanges.set(mapping.filepath, changeFromValue(mapping.filepath, select.value));
			item.classList.toggle('changed', select.value !== original);
			updateMatchButtons();
		};
		item.append(name, select);
		list.appendChild(item);
	});
}

function loadMatches(api_key) {
	return fetchAPI(`/volumes/${volume_id}/manualmatch`, api_key).then(json => {
		matchOriginal = json.result;
		renderMatches();
	});
}

function saveMatches(api_key) {
	if (!matchChanges.size) return;
	const status = document.querySelector('#match-status');
	setStatus(status, 'Saving…');
	sendAPI('PUT', `/volumes/${volume_id}/manualmatch`, api_key, {}, [...matchChanges.values()])
	.then(() => loadSeries(api_key))
	.then(() => setStatus(status, 'Matches saved.'))
	.catch(async error => setStatus(status, `Couldn't save: ${await errorText(error)}`, true));
}

//
// Other (general) files
//
function fileRow(file, label, api_key, onDeleted) {
	const item = document.createElement('li');
	item.className = 'sp-file';
	const name = document.createElement('span');
	name.className = 'sp-file-name';
	name.textContent = shortPath(file.filepath);
	name.title = file.filepath;
	const meta = document.createElement('span');
	meta.className = 'sp-file-meta';
	meta.textContent = [label, convertSize(file.size, 1)].filter(Boolean).join(' · ');
	const remove = document.createElement('button');
	remove.type = 'button';
	remove.className = 'sp-link sp-delete-file';
	remove.textContent = 'Delete';
	remove.onclick = () => {
		if (remove.dataset.confirm !== '1') {
			remove.dataset.confirm = '1';
			remove.textContent = 'Delete file?';
			setTimeout(() => { remove.dataset.confirm = ''; remove.textContent = 'Delete'; }, 4000);
			return;
		}
		sendAPI('DELETE', `/files/${file.id}`, api_key)
		.then(() => { item.remove(); onDeleted && onDeleted(); });
	};
	item.append(name, meta, remove);
	return item;
}

function fillOtherFiles(api_key) {
	const list = document.querySelector('#other-files');
	list.innerHTML = '';
	seriesData.general_files.forEach(gf =>
		list.appendChild(fileRow(gf, gf.file_type, api_key, () => loadSeries(api_key))));
	document.querySelector('#other-empty').classList.toggle('hidden', seriesData.general_files.length > 0);
}

//
// Issue details
//
function selectIssue(issue_id, api_key) {
	selectedIssueId = issue_id;
	ViewEls.issues_list.querySelectorAll('.issue-entry').forEach(row =>
		row.classList.toggle('selected', parseInt(row.dataset.id) === issue_id));
	showIssue(issue_id, api_key, true);
}

let issueRequest = 0;
function showIssue(issue_id, api_key, focusPanel) {
	const issue = seriesIssues().find(i => i.id === issue_id);
	if (!issue) return;
	const request = ++issueRequest;
	ViewEls.panel.tab_issue.textContent = `Issue #${issue.issue_number}`;
	ViewEls.panel.tab_issue.classList.remove('hidden');
	document.querySelector('#issue-info-title').textContent = issue.title
		? `#${issue.issue_number} · ${issue.title}` : `Issue #${issue.issue_number}`;
	document.querySelector('#issue-info-meta').textContent =
		[issue.date ? `Released ${issue.date}` : '', issue.files.length ? 'Has file' : 'Missing'].filter(Boolean).join(' · ');
	const desc = document.querySelector('#issue-info-desc');
	desc.innerHTML = issue.description || '';
	desc.classList.toggle('hidden', !issue.description);

	const files = document.querySelector('#issue-files-list');
	files.innerHTML = '';
	issue.files.forEach(f => files.appendChild(fileRow(f, '', api_key, () => loadSeries(api_key))));
	document.querySelector('#issue-files-empty').classList.toggle('hidden', issue.files.length > 0);

	const tidy = document.querySelector('#issue-tidy-list');
	const summary = document.querySelector('#issue-tidy-summary');
	const rename = document.querySelector('#issue-rename');
	const convert = document.querySelector('#issue-convert');
	tidy.innerHTML = '';
	rename.classList.add('hidden');
	convert.classList.add('hidden');
	setStatus(document.querySelector('#issue-status-line'), '');
	if (!issue.files.length) {
		summary.textContent = 'Nothing to rename or convert until this issue has a file.';
	} else {
		summary.textContent = 'Checking…';
		Promise.all([
			fetchAPI(`/issues/${issue_id}/rename`, api_key),
			fetchAPI(`/issues/${issue_id}/convert`, api_key)
		]).then(([renames, converts]) => {
			if (request !== issueRequest) return;
			const r = Object.keys(renames.result).length, c = Object.keys(converts.result).length;
			const notes = [];
			notes.push(r ? 'The file name doesn\'t follow your naming.' : 'The file name follows your naming.');
			if (c) notes.push('It can be converted to your preferred format.');
			summary.textContent = notes.join(' ');
			summary.classList.toggle('warn', Boolean(r || c));
			renderChanges(tidy, {...renames.result});
			rename.classList.toggle('hidden', !r);
			convert.classList.toggle('hidden', !c);
			rename.onclick = () => runIssueTask(api_key, issue_id, 'mass_rename_issue', Object.keys(renames.result));
			convert.onclick = () => runIssueTask(api_key, issue_id, 'mass_convert_issue', Object.keys(converts.result));
		}).catch(() => { summary.textContent = ''; });
	}

	document.querySelector('#issue-autosearch').onclick = () => {
		setStatus(document.querySelector('#issue-status-line'), 'Searching…');
		runTask(api_key, {cmd: 'auto_search_issue', issue_id},
			() => setStatus(document.querySelector('#issue-status-line'), 'Search finished. Anything found is in the download queue.'));
	};
	document.querySelector('#issue-manualsearch').onclick = () => showManualSearch(api_key, issue_id);
	if (focusPanel) openPanel('issue');
}

function runIssueTask(api_key, issue_id, cmd, paths) {
	const status = document.querySelector('#issue-status-line');
	setStatus(status, cmd === 'mass_rename_issue' ? 'Renaming…' : 'Converting…');
	runTask(api_key, {cmd, issue_id, filepath_filter: paths},
		() => setStatus(status, 'Done.'));
}

//
// Remove
//
function deleteVolume(api_key) {
	const delete_folder = document.querySelector('#delete-folder-input').checked;
	const status = document.querySelector('#delete-status');
	if (!window.confirm(`Remove ${seriesData.title} from your library?${delete_folder
		? ' Its folder and files will also be permanently deleted.' : ' The files stay on disk.'}`))
		return;
	setStatus(status, 'Removing…');
	sendAPI('DELETE', `/volumes/${volume_id}`, api_key, {delete_folder})
	.then(() => { window.location.href = `${url_base}/`; })
	.catch(async e => {
		const j = await apiError(e);
		const reason = j.error === 'TaskForVolumeRunning'
			? 'A task is running for this series. Try again when it finishes.'
			: j.error === 'VolumeDownloadedFor'
			? 'A download for this series is in the queue.'
			: await errorText(e);
		setStatus(status, `Couldn't remove: ${reason}`, true);
	});
}

//
// Manual search (still a window, downloads only)
//
function showManualSearch(api_key, issue_id=null) {
	const message = document.querySelector('#searching-message');
	const table = document.querySelector('#search-result-table');
	const tbody = table.querySelector('tbody');
	hide([table], [message]);
	showWindow('manual-search-window');
	tbody.innerHTML = '';
	const url = issue_id ? `/issues/${issue_id}/manualsearch` : `/volumes/${volume_id}/manualsearch`;

	fetchAPI(url, api_key)
	.then(json => {
		json.result.forEach(result => {
			const entry = ViewEls.pre_build.manual_search.cloneNode(true);
			tbody.appendChild(entry);

			const match = entry.querySelector('.match-column');
			if (result.match) setImage(match, images.check, 'Search result matches');
			else setImage(match, images.cancel, result.match_issue);

			const title = entry.querySelector('a');
			title.href = result.link;
			title.innerText = result.display_title;
			entry.querySelector('.source-column').innerText = result.indexer_title;
			entry.querySelector('.size-column').innerText = convertSize(result.size, 1);

			const download_button = entry.querySelector('.search-action-column :nth-child(1)');
			download_button.classList.add('icon-text-color');
			download_button.onclick = () => addManualSearch(result.link, result.indexer_id, false, download_button, api_key, issue_id);

			const force_download_button = entry.querySelector('.search-action-column :nth-child(2)');
			force_download_button.classList.add('icon-text-color');
			force_download_button.onclick = () => addManualSearch(result.link, result.indexer_id, true, force_download_button, api_key, issue_id);

			const blocklist_button = entry.querySelector('.search-action-column :nth-child(3)');
			if (result.match_issue === null || !result.match_issue.includes('blocklist'))
				blocklist_button.onclick = () => blockManualSearch(
					result.link, result.display_title, volume_id, issue_id, blocklist_button, match, api_key);
			else
				blocklist_button.remove();
		});
		hide([message], [table]);
	});
};

function addManualSearch(link, indexer_id, force, button, api_key, issue_id=null) {
	button.classList.remove('error');
	button.title = 'Download';
	const img = button.querySelector('img');
	img.src = `${url_base}/static/img/loading.svg`;
	img.classList.add('spinning');
	const url = issue_id ? `/issues/${issue_id}/download` : `/volumes/${volume_id}/download`;

	sendAPI('POST', url, api_key, {}, {link: link, indexer_id: indexer_id, force_match: force})
	.then(() => {
		img.classList.remove('spinning');
		img.src = `${url_base}/static/img/check.svg`;
	})
	.catch(async e => {
		const json = await apiError(e);
		img.classList.remove('spinning');
		img.src = `${url_base}/static/img/download.svg`;
		button.classList.add('error');
		button.title = json.error === 'EnqueuingDownloadFailure'
			? (enqueueFailureReasonMap[json.result?.reason] || 'Download failed. Please try again.')
			: 'Download failed. Please try again.';
	});
};

function blockManualSearch(web_link, web_title, volume_id, issue_id, button, match, api_key) {
	sendAPI('POST', '/blocklist', api_key, {}, {
		web_link, web_title, volume_id, issue_id, reason_id: 4
	})
	.then(() => {
		button.querySelector('img').src = `${url_base}/static/img/check.svg`;
		setImage(match, 'cancel.svg', 'Link is blocklisted');
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	currentApiKey = api_key;
	loadSeries(api_key).catch(e => {
		if (e.status === 404) window.location.href = `${url_base}/`;
		else console.log(e);
	});

	ViewEls.tool_bar.refresh.onclick = () => runTask(api_key, {cmd: 'refresh_and_scan'});
	ViewEls.tool_bar.auto_search.onclick = () => runTask(api_key, {cmd: 'auto_search'});
	ViewEls.tool_bar.manual_search.onclick = () => showManualSearch(api_key);
	ViewEls.tool_bar.rename.onclick = () => runRenameOrConvert(api_key, 'rename');
	ViewEls.tool_bar.convert.onclick = () => runRenameOrConvert(api_key, 'convert');

	const edit = ViewEls.vol_edit;
	edit.form.addEventListener('submit', e => {
		e.preventDefault();
		saveDetails(api_key);
	});
	edit.undo.onclick = resetDetails;
	edit.open_folder.onclick = () => openFolder(api_key);
	[edit.special_version, edit.root_folder, edit.volume_folder].forEach(el => {
		el.addEventListener('input', updateDetailsDirty);
		el.addEventListener('change', updateDetailsDirty);
	});
	edit.monitor.onchange = () => setSeriesMonitored(api_key, edit.monitor.checked);
	edit.monitor_new_issues.onchange = () =>
		sendAPI('PUT', `/volumes/${volume_id}`, api_key, {}, {monitor_new_issues: edit.monitor_new_issues.checked});
	document.querySelector('#apply-scheme').onclick = () =>
		sendAPI('PUT', `/volumes/${volume_id}`, api_key, {}, {monitoring_scheme: edit.monitoring_scheme.value})
		.then(() => loadSeries(api_key));

	document.querySelector('#match-save').onclick = () => saveMatches(api_key);
	document.querySelector('#match-undo').onclick = renderMatches;
	document.querySelector('#submit-delete').onclick = () => deleteVolume(api_key);

	ViewEls.issues_list.addEventListener('click', event => {
		const row = event.target.closest('.issue-entry');
		if (row && !event.target.closest('button')) selectIssue(parseInt(row.dataset.id), api_key);
	});
	ViewEls.issues_list.addEventListener('keydown', event => {
		const row = event.target.closest('.issue-entry');
		if (!row) return;
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			selectIssue(parseInt(row.dataset.id), api_key);
		} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			let next = row;
			do next = event.key === 'ArrowDown' ? next.nextElementSibling : next.previousElementSibling;
			while (next && next.classList.contains('hidden'));
			if (next) {
				next.focus();
				selectIssue(parseInt(next.dataset.id), api_key);
			}
		}
	});

	socket_ready.then(socket => socket.on('downloaded_status', data => {
		if (data.volume_id !== volume_id) return;
		data.downloaded_issues.forEach(id => new IssueEntry(id, api_key).setDownloaded(true));
		data.not_downloaded_issues.forEach(id => new IssueEntry(id, api_key).setDownloaded(false));
	}));
});

ViewEls.panel.tab_series.onclick = () => openPanel('series');
ViewEls.panel.tab_issue.onclick = () => openPanel('issue');
ViewEls.panel.close.onclick = closePanel;
ViewEls.tool_bar.editor.onclick = () => openPanel('series');
document.querySelectorAll('.sp-filter button').forEach(button => button.onclick = () => {
	issueFilter = button.dataset.filter;
	applyIssueFilter();
});
document.addEventListener('keydown', event => {
	if (event.key === 'Escape' && ViewEls.views.main.classList.contains('panel-open')
	&& !document.querySelector('.window[show-window]')
	&& !event.target.closest?.('input, select, textarea'))
		closePanel();
});
