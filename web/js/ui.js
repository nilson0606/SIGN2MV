// Shared UI helpers: toast, confirm dialog, element creation, formatting.
import { t } from './i18n.js';

export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function toast(message, bad = false, ms = 4500) {
  const box = el('div', { class: bad ? 'bad' : '' }, message);
  $('#toast').append(box);
  setTimeout(() => box.remove(), ms);
}

export function confirmDialog(message, okLabel) {
  const dlg = $('#confirm-dialog');
  $('#confirm-text').textContent = message;
  $('#confirm-yes').textContent = okLabel || t('common.ok');
  return new Promise((resolve) => {
    const done = (v) => { dlg.close(); cleanup(); resolve(v); };
    const yes = () => done(true);
    const no = () => done(false);
    const cancel = (e) => { e.preventDefault(); done(false); };
    function cleanup() {
      $('#confirm-yes').removeEventListener('click', yes);
      $('#confirm-no').removeEventListener('click', no);
      dlg.removeEventListener('cancel', cancel);
    }
    $('#confirm-yes').addEventListener('click', yes);
    $('#confirm-no').addEventListener('click', no);
    dlg.addEventListener('cancel', cancel);
    dlg.showModal();
  });
}

// several named choices plus 取消; resolves the chosen id, or null for 取消 / Esc
export function choiceDialog(message, choices) {
  return new Promise((resolve) => {
    const done = (v) => { dlg.close(); dlg.remove(); resolve(v); };
    const dlg = el('dialog', { class: 'choice-dialog' },
      el('p', { style: 'white-space:pre-line' }, message),
      el('div', { class: 'row', style: 'justify-content:flex-end' },
        el('button', { class: 'btn', type: 'button', onclick: () => done(null) }, t('common.cancel')),
        ...choices.map((c) => el('button', { class: `btn${c.primary ? ' primary' : ''}`, type: 'button', onclick: () => done(c.id) }, c.label))));
    dlg.addEventListener('cancel', (e) => { e.preventDefault(); done(null); });
    document.body.append(dlg);
    dlg.showModal();
  });
}

export function fmtTime(sec) {
  if (!Number.isFinite(sec) || sec < 0) return '--:--';
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, '0')}`;
}

export function fmtBytes(n) {
  if (!Number.isFinite(n)) return '-';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0; let v = Math.abs(n);
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${n < 0 ? '-' : ''}${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

export function fmtDate(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'zh-TW');
}
