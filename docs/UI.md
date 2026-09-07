# Interface

The workspace keeps Flask templates and the existing API. No frontend build step or additional runtime is required.

## Layout

- Collection, Activity, and Manage destinations remain visible in the desktop rail. On phones, the menu opens a drawer; hidden links are excluded from keyboard navigation.
- Library search lives with the collection. Covers use a responsive grid; list view supports selecting multiple volumes. Search updates after a short typing pause and ignores superseded responses.
- Volume search actions remain visible. The Manage volume disclosure contains renaming, conversion, file management, editing, and deletion.
- Settings categories appear above each settings page. The save toolbar stays visible as the form scrolls.
- Empty collections, searches without matches, and failed library requests have distinct recovery paths. Bulk deletion explains whether files will be retained.

## Styling

`frontend/static/css/workspace.css` is the shared visual layer, loaded after component styles. It owns workspace colors, navigation, headings, toolbar presentation, cover layout, and responsive overrides. Component files retain their behavior-dependent selectors and form/table structure. Use the existing Manrope typography and blue action tokens; reserve color in the library for covers and meaningful status.

## Validation

Run:

```sh
node --test tests/frontend/frontend.test.cjs
python -m unittest discover -s tests -p '*.py'
git diff --check
```

Check every frontend JavaScript file with `node --check`. Use a separate database and download folder for browser testing. Exercise desktop and 390px mobile views, both themes, a populated and empty library, no-match recovery, cover/list switching, bulk selection, settings categories, and volume dialogs. External Comic Vine searches and downloads need configured services; sample-library UI checks do not verify those integrations.
