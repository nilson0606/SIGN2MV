const normalize = value => String(value || '').normalize('NFKC').toLocaleLowerCase().trim();

// Filter existing rows so playback, recording badges and button locks stay intact.
export function createLibrarySearch({input, clear, status, list}) {
  let entries = [], ready = false;
  const folds = new Map();
  function apply() {
    const words = normalize(input.value).split(/\s+/).filter(Boolean);
    let count = 0;
    for (const {row, text} of entries) {
      row.hidden = !words.every(word => text.includes(word));
      if (!row.hidden) count++;
    }
    for (const group of list.querySelectorAll('.song-key-group')) {
      group.hidden = ![...group.querySelectorAll('.key-versions > li')].some(row => !row.hidden);
      const fold = group.querySelector('details');
      if (words.length) {
        if (!folds.has(fold)) folds.set(fold, fold.open);
        if (!group.hidden) fold.open = true;
      } else if (folds.has(fold)) {
        fold.open = folds.get(fold); folds.delete(fold);
      }
    }
    clear.disabled = !input.value;
    status.hidden = !ready;
    status.textContent = !ready ? '' : words.length && !count
      ? '找不到符合的歌曲，請換個關鍵字或清除搜尋。'
      : `顯示 ${count}／${entries.length} 個歌曲基準。`;
  }
  function reset() { input.value = ''; apply(); input.focus(); }
  input.addEventListener('input', apply);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !event.isComposing) { event.preventDefault(); reset(); }
  });
  clear.addEventListener('click', reset);
  apply();
  return {
    update(rows) {
      folds.clear();
      entries = rows.map(({row, song}) => ({row, text: normalize(`${song.title || ''} ${song.baseTitle || ''}`)}));
      ready = true; apply();
    }
  };
}
