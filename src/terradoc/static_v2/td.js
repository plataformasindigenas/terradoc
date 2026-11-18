/* terradoc v2: small enhancements; every page works without this file. */
(function () {
  'use strict';
  // Phone menu: Esc and a click outside close it, focus goes back to the button.
  var menu = document.querySelector('.td-menu');
  if (menu) {
    var summary = menu.querySelector('summary');
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.open) { menu.open = false; summary.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
  }
  // Offline: the service worker sits at the site root (data-root on <html>).
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    var root = document.documentElement.getAttribute('data-root') || '';
    if (root.charAt(0) !== '/' && !/^https?:/.test(root)) {
      navigator.serviceWorker.register(root + 'sw.js').catch(function () {});
    }
  }
  // Remember the language chosen with the switch (read by the site root page).
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-td-locale]');
    if (a) { try { localStorage.setItem('td-locale', a.getAttribute('data-td-locale')); } catch (err) {} }
  });
})();
