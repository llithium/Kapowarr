const SearchEls = {
	pre_build: {
		search_entry: document.querySelector('.pre-build-els .search-entry')
	},
	search_bar: {
		bar: document.querySelector('.search-bar'),
		cancel: document.querySelector('#search-cancel-button'),
		input: document.querySelector('#search-input')
	},
	search_results: document.querySelector('#search-results'),
	result_count: document.querySelector('#result-count'),
	page: document.querySelector('main.add-page'),
	panel: {
		empty: document.querySelector('#add-empty'),
		close: document.querySelector('#close-panel'),
		meta: document.querySelector('#add-meta'),
		cv_link: document.querySelector('#add-cv'),
		status: document.querySelector('#add-status')
	},
	msgs: {
		blocked: document.querySelector('#search-blocked'),
		failed: document.querySelector('#search-failed'),
		rate_limited: document.querySelector('#search-rate-limited'),
		empty: document.querySelector('#search-empty'),
		explain: document.querySelector('#search-explain'),
		loading: document.querySelector('#search-loading')
	},
	filters: {
		translations: document.querySelector('#filter-translations'),
		publisher: document.querySelector('#filter-publisher'),
		volume_number: document.querySelector('#filter-volume-number'),
		year: document.querySelector('#filter-year'),
		issue_count: document.querySelector('#filter-issue-count')
	},
	window: {
		form: document.querySelector('#add-form'),
		title: document.querySelector('#add-window h2'),
		cover: document.querySelector('#add-cover'),
		cv_input: document.querySelector('#comicvine-input'),
		monitor_volume_input: document.querySelector('#monitor-volume-input'),
		monitor_issues_input: document.querySelector('#monitor-issues-input'),
		monitoring_scheme: document.querySelector('#monitoring-scheme-input'),
		root_folder_input: document.querySelector('#rootfolder-input'),
		volume_folder_input: document.querySelector('#volumefolder-input'),
        special_state_input: document.querySelector('#specialoverride-input'),
		auto_search_input: document.querySelector('#auto-search-input'),
		submit: document.querySelector('#add-volume')
	}
};

//
// Searching
//
function addAlreadyAdded(entry, id) {
	entry.onclick = e => window.location.href = `${url_base}/volumes/${id}`;
	entry.classList.add('is-added');
	entry.title = 'Already in your library. Open the series.';
	entry.querySelector('.entry-added').classList.remove('hidden');
};

function plainText(html) {
	// Comic Vine descriptions are HTML. Show them as plain text so that
	// their images and links don't load inside the result list.
	if (!html)
		return '';
	const doc = new DOMParser().parseFromString(html, 'text/html');
	return (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
};

function addTag(container, text, className='') {
	const tag = document.createElement('span');
	tag.innerText = text;
	if (className)
		tag.className = className;
	container.appendChild(tag);
	return tag;
};

function buildResults(results, api_key) {
	SearchEls.search_results
        .querySelectorAll('button.search-entry')
        .forEach(e => e.remove());
	closePanel(true);

	results.forEach(result => {
		const entry = SearchEls.pre_build.search_entry.cloneNode(true);
		entry.dataset.title =
		entry.ariaLabel =
			result.year !== null
            ? `${result.title} (${result.year})`
            : result.title;
		entry.dataset.cover = result.cover_link;
		entry.dataset.comicvine_id = result.comicvine_id;
		entry.dataset._translated = result.translated;
		entry.dataset._title = result.title;
		entry.dataset._year = result.year || '';
		entry.dataset._volume_number = result.volume_number;
		entry.dataset._publisher = result.publisher || '';
		entry.dataset._issue_count = result.issue_count;
		entry.dataset.site_url = result.site_url || '';

		// Only allow adding volume if it isn't already added
		if (result.already_added === null)
			entry.onclick = e => showAddWindow(result.comicvine_id, api_key);

		entry.querySelector('.entry-cover').src = result.cover_link;

		const title = entry.querySelector('h2');
		title.innerText = result.title;

		if (result.year !== null) {
			const year = document.createElement("span");
			year.className = 'entry-year';
			year.innerText = ` (${result.year})`;
			title.appendChild(year);
		};

		if (result.already_added !== null)
			addAlreadyAdded(entry, result.already_added);

		const tags = entry.querySelector('.entry-tags');
		addTag(tags, result.publisher || 'Publisher unknown', 'entry-publisher');
		if (result.volume_number !== null)
			addTag(tags, `Volume ${result.volume_number}`);
		addTag(tags, result.issue_count === 1 ? '1 issue' : `${result.issue_count} issues`);
		if (result.translated)
			addTag(tags, 'Translated');

		const aliases = entry.querySelector('.entry-aliases');
		if (result.aliases.length)
			aliases.innerText = 'Also known as ' + result.aliases.slice(0, 3).join(', ')
				+ (result.aliases.length > 3 ? '…' : '');
		else
			aliases.remove();

		const description = plainText(result.description);
		const description_el = entry.querySelector('.entry-description');
		if (description)
			description_el.innerText = description;
		else
			description_el.remove();

		SearchEls.search_results.appendChild(entry);
	});

	// Fill filters
	const years = new Set(results.map(r => r.year).sort());
	SearchEls.filters.year.innerHTML = '';
	const all_years_option = document.createElement('option');
	all_years_option.value = '';
	all_years_option.innerText = 'All years';
	all_years_option.selected = true;
	SearchEls.filters.year.appendChild(all_years_option);

	years.forEach(y => {
		const entry = document.createElement('option');
		if (y === null) {
			entry.value = y;
			entry.innerText = '(No year)';
		} else {
			entry.value = entry.innerText = y;
		};
		SearchEls.filters.year.appendChild(entry);
	});

	const issue_counts = new Set(results
        .map(r => r.issue_count)
        .sort((a, b) => a - b)
    );
	SearchEls.filters.issue_count.innerHTML = '';
	const all_issue_counts_option = document.createElement('option');
	all_issue_counts_option.value = '';
	all_issue_counts_option.innerText = 'Any issue count';
	all_issue_counts_option.selected = true;
	SearchEls.filters.issue_count.appendChild(all_issue_counts_option);
	const one_higher_issue_counts_option = document.createElement('option');
	one_higher_issue_counts_option.value = '>1 issues';
	one_higher_issue_counts_option.innerText = 'More than 1 issue';
	SearchEls.filters.issue_count.appendChild(one_higher_issue_counts_option);

	issue_counts.forEach(ic => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = `${ic} issues`;
		SearchEls.filters.issue_count.appendChild(entry);
	});

	const volume_numbers = new Set(results
        .map(r => r.volume_number)
        .sort((a, b) => a - b)
    );
	SearchEls.filters.volume_number.innerHTML = '';
	const all_volume_numbers_option = document.createElement('option');
	all_volume_numbers_option.value = '';
	all_volume_numbers_option.innerText = 'Any volume';
	all_volume_numbers_option.selected = true;
	SearchEls.filters.volume_number.appendChild(all_volume_numbers_option);

	volume_numbers.forEach(vn => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = `Volume ${vn}`;
		SearchEls.filters.volume_number.appendChild(entry);
	});

	const publishers = new Set(results.map(r => r.publisher).sort());
	SearchEls.filters.publisher.innerHTML = '';
	const all_publishers_option = document.createElement('option');
	all_publishers_option.value = '';
	all_publishers_option.innerText = 'All publishers';
	all_publishers_option.selected = true;
	SearchEls.filters.publisher.appendChild(all_publishers_option);

	publishers.forEach(pub => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = pub;
		SearchEls.filters.publisher.appendChild(entry);
	});

    processURLFilters();
	applyFilters();
};

function search(reset_url_params=true) {
	if (!SearchEls.msgs.blocked.classList.contains('hidden'))
		return;

	SearchEls.search_bar.input.blur();

	hide([
		SearchEls.msgs.empty,
		SearchEls.msgs.explain,
		SearchEls.msgs.failed,
		SearchEls.msgs.rate_limited,
		SearchEls.search_results
	], [
		SearchEls.msgs.loading
	]);

    if (reset_url_params)
        emptyParams();

    usingApiKey().then(api_key => {
		const query = SearchEls.search_bar.input.value;
		fetchAPI('/volumes/search', api_key, {query: query})
		.then(json => {

			buildResults(json.result, api_key);

			if (!SearchEls.search_results.querySelector('button.search-entry'))
				hide([SearchEls.msgs.loading], [SearchEls.msgs.empty]);
			else
				hide([SearchEls.msgs.loading], [SearchEls.search_results]);
		})
		.catch(e => {
			if (e.status === 400)
				hide([SearchEls.msgs.loading], [SearchEls.msgs.failed]);
			else if (e.status === 509)
				hide([SearchEls.msgs.loading], [SearchEls.msgs.rate_limited]);
			else
				hide([SearchEls.msgs.loading], [SearchEls.msgs.failed]);
		});
	});
};

function clearSearch(e) {
	hide([
		SearchEls.search_results,
		SearchEls.msgs.empty,
		SearchEls.msgs.failed,
		SearchEls.msgs.rate_limited
	], [
		SearchEls.msgs.explain
	]);
	SearchEls.search_results
        .querySelectorAll('button.search-entry')
        .forEach(e => e.remove());
	closePanel(true);
	SearchEls.search_bar.input.value = '';
	SearchEls.search_bar.input.focus();
    setURLParams();
};

function applyFilters() {
	const translation = SearchEls.filters.translations.value,
		year = SearchEls.filters.year.value,
		issue_count = (
			SearchEls.filters.issue_count.value || ' issues'
		).split(' issues')[0],
		volume_number = (
			SearchEls.filters.volume_number.value || 'Volume '
			).split('Volume ')[1],
		publisher = SearchEls.filters.publisher.value;

	setLocalStorage({'translated_filter': translation});

	let filter = '';

	if (translation === 'only-english')
		filter += '[data-_translated="false"]';
	if (year !== '')
		filter += `[data-_year="${year}"]`;
	if (issue_count === '>1')
		filter += `:not([data-_issue_count="0"]):not([data-_issue_count="1"])`
	else if (issue_count !== '')
		filter += `[data-_issue_count="${issue_count}"]`;
	if (volume_number !== '')
		filter += `[data-_volume_number="${volume_number}"]`;
	if (publisher !== '')
		filter += `[data-_publisher="${publisher}"]`;

	const entries = SearchEls.search_results.querySelectorAll('button.search-entry');
	if (filter === '')
		hide([], entries);
	else
		hide(
			entries,
			SearchEls.search_results.querySelectorAll(`button.search-entry${filter}`)
		);

	const shown = [...entries].filter(e => !e.classList.contains('hidden')).length;
	SearchEls.result_count.innerText =
		shown === entries.length
		? `${entries.length} ${entries.length === 1 ? 'result' : 'results'}`
		: `${shown} of ${entries.length} results`;

    setURLParams();
};

//
// URL params
//
function emptyParams() {
    history.pushState(
        {}, "",
        window.location.origin + window.location.pathname
    );
};

function setURLParams() {
    const params = new URLSearchParams();

    if (SearchEls.search_bar.input.value === "") {
        emptyParams();
        return;
    };

    if (SearchEls.search_bar.input.value)
        params.set('q', SearchEls.search_bar.input.value);
    if (SearchEls.filters.translations.value)
        params.set('t', SearchEls.filters.translations.value);
    if (SearchEls.filters.year.value)
        params.set('y', SearchEls.filters.year.value);
    if (SearchEls.filters.issue_count.value)
        params.set('i', SearchEls.filters.issue_count.value);
    if (SearchEls.filters.volume_number.value)
        params.set('v', SearchEls.filters.volume_number.value);
    if (SearchEls.filters.publisher.value)
        params.set('p', SearchEls.filters.publisher.value);

    history.pushState({}, "", `?${params.toString()}`);
};

function processURLParams() {
    const params = new URLSearchParams(window.location.search);

    const query = params.get('q');
    if ((query || null) === null)
        return;
    SearchEls.search_bar.input.value = query;

    search(reset_url_params=false);
};

function processURLFilters() {
    const params = new URLSearchParams(window.location.search);

    if (params.get('t'))
        SearchEls.filters.translations.value = params.get('t');
    if (params.get('y'))
        SearchEls.filters.year.value = params.get('y');
    if (params.get('i'))
        SearchEls.filters.issue_count.value = params.get('i');
    if (params.get('v'))
        SearchEls.filters.volume_number.value = params.get('v');
    if (params.get('p'))
        SearchEls.filters.publisher.value = params.get('p');
};

//
// Adding
//
function fillRootFolderInput(api_key) {
	fetchAPI('/rootfolder', api_key)
	.then(json => {
		if (json.result.length)
			json.result.forEach(folder => {
				const option = document.createElement('option');
				option.value = folder.id;
				option.innerText = folder.folder;
				SearchEls.window.root_folder_input.appendChild(option);
			});
		else
			hide([], [SearchEls.msgs.blocked]);
	});
};

function openPanel() {
	SearchEls.page.classList.add('panel-open');
};

function closePanel(clear=false) {
	SearchEls.page.classList.remove('panel-open');
	if (!clear)
		return;
	SearchEls.search_results
		.querySelectorAll('button.search-entry[aria-pressed="true"]')
		.forEach(e => e.setAttribute('aria-pressed', 'false'));
	hide([SearchEls.window.form.parentElement], [SearchEls.panel.empty]);
};

function setAddStatus(text, error=false) {
	SearchEls.panel.status.innerText = text;
	SearchEls.panel.status.classList.toggle('error', error);
};

function showAddWindow(comicvine_id, api_key) {
	const entry = document.querySelector(
		`button.search-entry[data-comicvine_id="${comicvine_id}"]`
	);
	const volume_data = entry.dataset;

	SearchEls.search_results
		.querySelectorAll('button.search-entry[aria-pressed="true"]')
		.forEach(e => e.setAttribute('aria-pressed', 'false'));
	entry.setAttribute('aria-pressed', 'true');

	SearchEls.window.submit.disabled = false;
	SearchEls.window.submit.innerText = 'Add to library';
	setAddStatus('');

	SearchEls.window.title.innerText = volume_data.title;
	SearchEls.window.cover.src = volume_data.cover;
	SearchEls.window.cv_input.value = comicvine_id;
	SearchEls.panel.meta.innerText = [
		volume_data._publisher || 'Publisher unknown',
		volume_data._issue_count === '1' ? '1 issue' : `${volume_data._issue_count} issues`
	].join(' · ');
	SearchEls.panel.cv_link.href = volume_data.site_url;
	SearchEls.panel.cv_link.classList.toggle('hidden', !volume_data.site_url);
    SearchEls.window.special_state_input.value = "auto";

	SearchEls.window.monitor_volume_input.value = 'false';
	SearchEls.window.monitor_issues_input.value = 'false';
	SearchEls.window.monitoring_scheme.value = 'none';
	SearchEls.window.auto_search_input.checked = false;

	// The suggested folder follows the naming settings
	SearchEls.window.volume_folder_input.value = '';
	SearchEls.window.volume_folder_input.placeholder = 'Working out the folder name…';
	const body = {
		'comicvine_id': volume_data.comicvine_id,
		'title': volume_data._title,
		'year': volume_data._year || null,
		'volume_number': volume_data._volume_number,
		'publisher': volume_data._publisher || null
	};
	sendAPI('POST', '/volumes/search', api_key, {}, body)
	.then(response => response.json())
	.then(json => {
		if (SearchEls.window.cv_input.value !== String(comicvine_id))
			return;
		volume_data._volume_folder = json.result.folder;
		SearchEls.window.volume_folder_input.value = json.result.folder;
		SearchEls.window.volume_folder_input.placeholder = '';
	});

	hide([SearchEls.panel.empty], [SearchEls.window.form.parentElement]);
	openPanel();
};

function addVolume() {
	const volume_folder = SearchEls.window.volume_folder_input.value;

	const data = {
		'comicvine_id': parseInt(SearchEls.window.cv_input.value),
		'root_folder_id': parseInt(SearchEls.window.root_folder_input.value),
		'monitor': SearchEls.window.monitor_volume_input.value === "true",
		'monitoring_scheme': SearchEls.window.monitoring_scheme.value,
		'monitor_new_issues': SearchEls.window.monitor_issues_input.value === "true",
		'volume_folder': '',
        'special_version': SearchEls.window.special_state_input.value || null,
		'auto_search': SearchEls.window.auto_search_input.checked
	};
	const entry = document.querySelector(
		`button.search-entry[data-comicvine_id="${data.comicvine_id}"]`
	);
	if (
		volume_folder !== ''
		&& volume_folder !== entry.dataset._volume_folder
	) {
		// Custom volume folder
		data.volume_folder = volume_folder;
	};

	SearchEls.window.submit.disabled = true;
	SearchEls.window.submit.innerText = 'Adding…';
	setAddStatus('');

	usingApiKey()
	.then(api_key => {
		sendAPI('POST', '/volumes', api_key, {}, data)
		.then(response => response.json())
		.then(json => {
			addAlreadyAdded(entry, json.result.id);
			SearchEls.window.submit.innerText = 'Added';
			SearchEls.panel.status.classList.remove('error');
			SearchEls.panel.status.innerText = 'Added to your library. ';
			const open = document.createElement('a');
			open.href = `${url_base}/volumes/${json.result.id}`;
			open.innerText = 'Open series';
			SearchEls.panel.status.appendChild(open);
		})
		.catch(e => {
			SearchEls.window.submit.disabled = false;
			SearchEls.window.submit.innerText = 'Add to library';
			if (e.status === 509)
				setAddStatus('Comic Vine rate limit reached. Try again in a little while.', true);
			else if (e.status === 400)
				setAddStatus('The Comic Vine API key is invalid.', true);
			else
				setAddStatus('Could not add this series. Please try again.', true);
		});
	});
};

// code run on load
usingApiKey()
.then(api_key => fillRootFolderInput(api_key));

SearchEls.search_bar.cancel.onclick = clearSearch;
SearchEls.window.form.onsubmit = e => {
	e.preventDefault();
	addVolume();
};
SearchEls.panel.close.onclick = e => closePanel();
document.addEventListener('keydown', e => {
	if (e.key === 'Escape' && SearchEls.page.classList.contains('panel-open'))
		closePanel();
});
SearchEls.search_bar.bar.action = 'javascript:search();';

SearchEls.filters.translations.onchange =
SearchEls.filters.publisher.onchange =
SearchEls.filters.volume_number.onchange =
SearchEls.filters.year.onchange =
SearchEls.filters.issue_count.onchange =
	e => applyFilters();

const translated_filter = getLocalStorage('translated_filter')['translated_filter'];
SearchEls.filters.translations
    .querySelector(`option[value="${translated_filter}"]`)
    .setAttribute('selected', '');

processURLParams();
