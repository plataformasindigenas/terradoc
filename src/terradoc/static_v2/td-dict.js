/* terradoc v2 dictionary: search as you type, the on-screen keyboard, and the way back from
   a word to the list it was opened from. The letter lists and word pages work without it. */
(function () {
  'use strict';
  var input = document.getElementById('td-q');

  // On-screen keyboard: types the language's letters at the cursor.
  var kb = document.querySelector('.td-keyboard');
  if (kb && input) {
    kb.hidden = false;
    kb.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.td-key');
      if (!b) return;
      var k = b.getAttribute('data-key'), s = input.selectionStart, t = input.selectionEnd;
      if (s == null) { s = t = input.value.length; }
      input.value = input.value.slice(0, s) + k + input.value.slice(t);
      input.focus();
      input.setSelectionRange(s + k.length, s + k.length);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  // From a word opened from search results, "back" returns to those results.
  var back = document.querySelector('[data-td-back]');
  var article = document.querySelector('[data-entry]');
  if (back && article && document.referrer) {
    try {
      var ref = new URL(document.referrer);
      if (ref.origin === location.origin && /\/dictionary\/index\.html$/.test(ref.pathname) && ref.search) {
        back.href = ref.pathname + ref.search + '#e-' + article.getAttribute('data-entry');
      }
    } catch (err) { /* keep the letter list */ }
  }

  // Back on a letter list (#e-<id>): focus the word that was open, not just scroll to it.
  if (/^#e-\d+$/.test(location.hash) && !document.querySelector('.td-dict[data-index]')) {
    var back_li = document.getElementById(location.hash.slice(1));
    var back_a = back_li && back_li.querySelector('a');
    if (back_a) back_a.focus({ preventScroll: true });
  }

  var box = document.querySelector('.td-dict[data-index]');
  if (!box || !input) return;
  var T = JSON.parse(box.getAttribute('data-strings') || '{}');
  var FOLDS = JSON.parse(box.getAttribute('data-folds') || '{}');
  var LANG = box.getAttribute('data-lang') || '';
  var LOCALE = box.getAttribute('data-locale') || 'pt';
  var status = document.getElementById('td-status');
  var results = document.getElementById('td-results');
  var MAX = 100;
  var rows = null, loading = null;

  var foldKeys = Object.keys(FOLDS).sort(function (a, b) { return b.length - a.length; });
  var foldRe = foldKeys.length ? new RegExp(foldKeys.map(function (k) {
    return k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).join('|'), 'g') : null;
  // Accents, case and apostrophes never matter. The site's folds (r = l, ...) apply to words
  // of the language only, not to the Portuguese glosses.
  function fold(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
      .replace(/[’'ʼ`´‘]/g, '').replace(/\s+/g, ' ').trim();
  }
  function vfold(s) {
    s = fold(s);
    return foldRe ? s.replace(foldRe, function (m) { return FOLDS[m]; }) : s;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  function fmt(s, vars) { return String(s || '').replace(/\{(\w+)\}/g, function (_, k) { return vars[k]; }); }
  function say(text) { if (status) status.textContent = text; }

  function load() {
    if (rows) return Promise.resolve(rows);
    if (loading) return loading;
    say(T.ui_dict_loading);
    loading = fetch(box.getAttribute('data-index')).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (d) {
      rows = d.rows.map(function (r, i) {
        return { id: r[0], entry: r[1], homonym: r[2], file: r[3], gloss: r[4], audio: r[7], order: i,
                 hw: vfold(r[1]), g: fold(r[4]), x: fold(r[5] + ' ' + r[6]) };
      });
      say('');
      return rows;
    }).catch(function (err) {
      loading = null;
      say(T.ui_dict_failed);
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'td-button td-button--quiet'; b.textContent = T.ui_retry;
      b.addEventListener('click', function () { b.remove(); run(); });
      if (status) status.appendChild(document.createTextNode(' ')), status.appendChild(b);
      throw err;
    });
    return loading;
  }

  function score(r, q, v, word) {
    if (r.hw === v) return 0;
    if (r.hw.indexOf(v) === 0) return 1;
    if (r.hw.indexOf(v) > 0) return 2;
    if (word.test(r.g)) return 3;
    if (r.g.indexOf(q) >= 0) return 4;
    if (r.x.indexOf(q) >= 0) return 5;
    return -1;
  }

  function render(list, raw) {
    if (!list.length) { results.innerHTML = ''; say(fmt(T.ui_dict_none, { q: raw })); return; }
    var n = list.length.toLocaleString(LOCALE);
    say(fmt(list.length === 1 ? T.ui_dict_results_one : T.ui_dict_results, { n: n, q: raw })
        + (list.length > MAX ? ' ' + fmt(T.ui_dict_more, { shown: MAX }) : ''));
    var lang = LANG ? ' lang="' + esc(LANG) + '"' : '';
    var glossLang = LOCALE.indexOf('pt') === 0 ? '' : ' lang="pt-BR"';
    results.innerHTML = '<ol class="td-words">' + list.slice(0, MAX).map(function (r) {
      return '<li id="e-' + esc(r.id) + '"><a href="' + encodeURI(r.file) + '"><span class="td-word"><span class="td-hw"' + lang + '>'
        + esc(r.entry) + '</span>' + (r.homonym ? '<sup class="td-homonym">' + esc(r.homonym) + '</sup>' : '') + '</span></a>'
        + (r.audio ? ' <span class="td-has-audio" title="' + esc(T.ui_has_audio) + '" aria-label="' + esc(T.ui_has_audio) + '">♪</span>' : '')
        + ' <span class="td-words__gloss"' + glossLang + '>' + esc(r.gloss) + '</span></li>';
    }).join('') + '</ol>';
  }

  var timer = null;
  function run(focusId) {
    var raw = input.value.trim(), q = fold(raw);
    var url = new URL(location.href);
    if (raw) url.searchParams.set('q', raw); else url.searchParams.delete('q');
    if (!focusId) url.hash = '';
    history.replaceState(null, '', url);
    var hint = document.getElementById('td-hint');
    if (hint) hint.hidden = !!raw;
    if (!q) { results.innerHTML = ''; say(''); return; }
    load().then(function (all) {
      if (fold(input.value.trim()) !== q) return; // typed on meanwhile
      var word = new RegExp('(^|[^a-z0-9])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
      var v = vfold(raw), hits = [];
      for (var i = 0; i < all.length; i++) {
        var s = score(all[i], q, v, word);
        if (s >= 0) hits.push([s, all[i]]);
      }
      hits.sort(function (a, b) { return a[0] - b[0] || a[1].order - b[1].order; });
      render(hits.map(function (h) { return h[1]; }), raw);
      if (focusId) {
        var li = document.getElementById(focusId);
        var a = li && li.querySelector('a');
        if (a) { li.scrollIntoView({ block: 'center' }); a.focus(); }
      }
    }, function () {});
  }

  input.addEventListener('focus', function () { load().catch(function () {}); }, { once: true });
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 120); });
  input.form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(timer); run(); });

  var q0 = new URLSearchParams(location.search).get('q');
  if (q0) {
    input.value = q0;
    var hint = document.getElementById('td-hint');
    if (hint) hint.hidden = true;
    run(location.hash.length > 1 ? location.hash.slice(1) : null);
  }
})();
