const library_els = {
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
		update_all: document.querySelector('#updateall-button'),
		search_all: document.querySelector('#searchall-button')
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
	mass_edit: {
		bar: document.querySelector('.action-bar'),
		button: document.querySelector('#massedit-button'),
		toggle: document.querySelector('#massedit-toggle'),
		select_all: document.querySelector('#selectall-input'),
		cancel: document.querySelector('#cancel-massedit'),
		progress: document.querySelector("#massedit-progress")
	}
};

const pre_build_els = {
	list_entry: document.querySelector('.pre-build-els .list-entry'),
	table_entry: document.querySelector('.pre-build-els .table-entry')
};

function showLibraryPage(el) {
	hide(Object.values(library_els.pages), [el]);
};

const libraryVolumes = new Map();
const renderedViews = new Set();

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
			entry.querySelector(`.${prefix}-prog-num`).innerText = `${downloaded_count}/${total_count}`;
			const bar = entry.querySelector(`.${prefix}-prog-bar`);
			bar.style.width = `${progress}%`;
			const monitored = libraryVolumes.get(this.id)?.monitored ?? entry.hasAttribute('monitored');
			bar.style.backgroundColor = progress === 100 ? 'var(--success-color)'
				: monitored ? 'var(--accent-color)' : 'var(--error-color)';
		}
		if (this.list_entry) this.list_entry.querySelector('.list-prog-container').title = total_count > 0
			? `${downloaded_count} of ${total_count} issues downloaded` : 'No issues';
	}
}

function populateLibrary(volumes, api_key) {
	libraryVolumes.clear();
	for (const volume of volumes) libraryVolumes.set(volume.id, volume);
	renderedViews.clear();
	library_els.views.list.querySelectorAll('.list-entry').forEach(e => e.remove());
	library_els.views.table.innerHTML = '';
	renderLibraryView(api_key);
}

function renderLibraryView(api_key) {
	const view = library_els.mass_edit.toggle.checked || library_els.view_options.view.value === 'table'
		? 'table' : 'list';
	if (renderedViews.has(view)) return;
	const fragment = document.createDocumentFragment();
	for (const volume of libraryVolumes.values()) {
		const entry = pre_build_els[`${view}_entry`].cloneNode(true);
		entry.ariaLabel = `View the volume ${volume.title} (${volume.year}) Volume ${volume.volume_number}`;
		entry.classList.add(`vol-${volume.id}`);
		const href = `${url_base}/volumes/${volume.id}`;
		if (view === 'list') {
			entry.href = href;
			entry.querySelector('.list-img').src = `${url_base}/api/volumes/${volume.id}/cover?api_key=${api_key}`;
			const title = entry.querySelector('.list-title');
			title.innerText = title.title = `${volume.title} (${volume.year})`;
			entry.querySelector('.list-volume').innerText = `Volume ${volume.volume_number}`;
		} else {
			entry.dataset.id = volume.id;
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
		fragment.appendChild(entry);
	}
	if (view === 'list') library_els.views.list.insertBefore(fragment, document.querySelector('.space-taker'));
	else library_els.views.table.appendChild(fragment);
	renderedViews.add(view);
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
function fetchLibrary(api_key) {
	const request = ++libraryRequest;
	library_els.mass_edit.progress.innerText = '';
	showLibraryPage(library_els.pages.loading);

	const params = {
		sort: library_els.view_options.sort.value,
		filter: library_els.view_options.filter.value
	};
	const query = library_els.search.input.value;
	if (query !== '')
		params.query = query;

	fetchAPI('/volumes', api_key, params)
	.then(json => {
		if (request !== libraryRequest) return;
		library_els.mass_edit.select_all.checked = false;
		document.querySelector('#library-result-count').textContent = `${json.result.length} ${json.result.length === 1 ? 'volume' : 'volumes'}`;
		populateLibrary(json.result, api_key);
		if (json.result.length === 0) {
			const filtered = Boolean(query || params.filter);
			document.querySelector('#library-empty-title').textContent = filtered ? 'No matching comics' : 'Your collection starts here';
			document.querySelector('#library-empty-description').textContent = filtered
				? 'Try another title or clear your search and filters.'
				: 'Add a comic series or import the files you already have.';
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
			? convertSize(json.result.total_file_size)
			: '0 MB';
	});
};

//
// Mass Edit
//
function runAction(api_key, action, args={}) {
	const volume_ids = [...library_els.views.table.querySelectorAll(
		'input[type="checkbox"]:checked'
	)].map(v => parseInt(v.parentNode.parentNode.dataset.id))

	if (!volume_ids.length) return;
	if (action === 'delete' && !window.confirm(
		`Remove ${volume_ids.length} selected volumes from your library?${args.delete_folder ? ' Their folders and files will also be permanently deleted.' : ' Their files will be kept.'}`
	)) return;
	showLibraryPage(library_els.pages.loading);

	sendAPI('POST', '/masseditor', api_key, {}, {
		'volume_ids': volume_ids,
		'action': action,
		'args': args
	})
	.then(response => {
		library_els.mass_edit.select_all.checked = false;
		fetchLibrary(api_key);
		fetchStats(api_key);
	}).catch(() => showLibraryPage(library_els.pages.error));
};

function updateSelection() {
	const boxes = [...library_els.views.table.querySelectorAll('input[type="checkbox"]')];
	const count = boxes.filter(box => box.checked).length;
	document.querySelector('#selection-count').textContent = `${count} selected`;
	library_els.mass_edit.select_all.checked = boxes.length > 0 && count === boxes.length;
	library_els.mass_edit.select_all.indeterminate = count > 0 && count < boxes.length;
	library_els.mass_edit.bar.querySelectorAll('button[data-action]').forEach(button => button.disabled = count === 0);
}

// code run on load

const lib_options = getLocalStorage('lib_sorting', 'lib_view', 'lib_filter');
library_els.view_options.sort.value = lib_options.lib_sorting;
library_els.view_options.view.value = lib_options.lib_view;
library_els.view_options.filter.value = lib_options.lib_filter;

usingApiKey()
.then(api_key => {
	fetchLibrary(api_key);
	fetchStats(api_key);

	library_els.search.clear.onclick =
		e => clearSearch(api_key);

	library_els.task_buttons.update_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {
			'cmd': 'update_all',
			'allow_skipping': false
		});
	library_els.task_buttons.search_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {'cmd': 'search_all'});

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

	library_els.mass_edit.button.onclick =
	library_els.mass_edit.cancel.onclick =
		e => {
			const toggle = library_els.mass_edit.toggle;
			if (toggle.checked) {
				toggle.checked = false;
				renderLibraryView(api_key);
			}
			else {
				const select = document.querySelector('select[name="root_folder_id"]');
				if (select.querySelector('option') === null) {
					fetchAPI('/rootfolder', api_key)
					.then(json => {
						json.result.forEach(rf => {
							const entry = document.createElement('option');
							entry.value = rf.id;
							entry.innerText = rf.folder;
							select.appendChild(entry);
						});
						toggle.checked = true;
						renderLibraryView(api_key);
					});
				} else {
					toggle.checked = true;
					renderLibraryView(api_key);
				}
			}
		};
	library_els.mass_edit.bar.querySelectorAll('.action-divider > button[data-action]').forEach(
		b => b.onclick = e => runAction(api_key, e.target.dataset.action)
	);
	library_els.mass_edit.bar.querySelector('button[data-action="delete"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'delete_folder': document.querySelector(
					'select[name="delete_folder"]'
				).value === "true"
			}
		);
	library_els.mass_edit.bar.querySelector('button[data-action="root_folder"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'root_folder_id': parseInt(document.querySelector(
					'select[name="root_folder_id"]'
				).value)
			}
		);
	library_els.mass_edit.bar.querySelector('button[data-action="monitoring_scheme"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'monitoring_scheme': document.querySelector(
					'select[name="monitoring_scheme"]'
				).value
			}
		);

	socket_ready.then(socket => socket.on(
		'downloaded_status',
		data => updateDownloadedStatus(data, api_key)
	));
	// Socket is init after API key so wait for that like this
	socket_ready.then(socket => socket.on(
		'mass_editor_status',
		data => library_els.mass_edit.progress.innerText = `${data.current_item}/${data.total_items}`
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
library_els.views.table.addEventListener('change', updateSelection);
updateSelection();
library_els.mass_edit.select_all.onchange =
	e => {
		library_els.views.table.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = library_els.mass_edit.select_all.checked);
		updateSelection();
	};
