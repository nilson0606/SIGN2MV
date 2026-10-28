// Interface translations. English keys; zh-TW and en dictionaries.
// Elements use data-i18n="key" (text), data-i18n-title, data-i18n-placeholder.
import zh from './i18n.zh-TW.js';
import en from './i18n.en.js';

const DICTS = { 'zh-TW': zh, en };
let current = 'zh-TW';
const listeners = new Set();

export function setLanguage(lang) {
  current = DICTS[lang] ? lang : 'en';
  document.documentElement.lang = current;
  applyTranslations(document);
  listeners.forEach((fn) => fn(current));
}

export function language() { return current; }
export function onLanguageChange(fn) { listeners.add(fn); }

export function t(key, ...args) {
  const dict = DICTS[current] || en;
  let text = dict[key] ?? en[key] ?? key;
  args.forEach((a, i) => { text = text.replaceAll(`{${i}}`, String(a)); });
  return text;
}

// Server error codes -> readable message in the current language.
export function errorText(err) {
  const code = (err && err.code) || String(err || 'unknown_error');
  const key = `err.${code}`;
  const dict = DICTS[current] || en;
  if (dict[key] || en[key]) return t(key);
  return t('err.generic', code);
}

export function applyTranslations(root) {
  root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  root.querySelectorAll('[data-i18n-aria]').forEach((el) => { el.setAttribute('aria-label', t(el.dataset.i18nAria)); });
}
