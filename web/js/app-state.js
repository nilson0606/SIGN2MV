// Shared state between the shell and the workspaces.
// bus events: 'songs', 'jobs', 'job-finished', 'reload-songs', 'reload-jobs', 'goto',
//             'shutdown', 'settings', 'song-selected'
import { api } from './api.js';

export const bus = new EventTarget();
export const pages = new Map();
export function registerPage(name, handlers) { pages.set(name, handlers); }
export function goto(name) { bus.dispatchEvent(new CustomEvent('goto', { detail: name })); }
export function reloadSongs() { bus.dispatchEvent(new Event('reload-songs')); }
export function reloadJobs() { bus.dispatchEvent(new Event('reload-jobs')); }

export const state = { songs: [], jobs: [], selectedSongId: null, settings: null };

bus.addEventListener('songs', (e) => { state.songs = e.detail; });
bus.addEventListener('jobs', (e) => { state.jobs = e.detail; });
bus.addEventListener('settings', (e) => { state.settings = e.detail; });

export function selectSong(id) {
  state.selectedSongId = id;
  try { localStorage.setItem('sign2mv.song', id || ''); } catch { /* ignore */ }
  bus.dispatchEvent(new CustomEvent('song-selected', { detail: id }));
}
try { state.selectedSongId = localStorage.getItem('sign2mv.song') || null; } catch { /* ignore */ }

export function songById(id) { return state.songs.find((s) => s.song_id === id) || null; }

// Wait until a job finishes; onProgress(job) is called on every poll.
export function waitJob(jobId, onProgress) {
  return new Promise((resolve) => {
    let stopped = false;
    async function poll() {
      if (stopped) return;
      try {
        const job = await api.get(`/api/jobs/${jobId}`);
        if (onProgress) onProgress(job);
        if (['succeeded', 'failed', 'cancelled', 'timeout'].includes(job.status)) {
          stopped = true;
          reloadJobs();
          resolve(job);
          return;
        }
      } catch (e) {
        if (e.code === 'job_not_found') { stopped = true; resolve({ status: 'failed', error_code: 'job_not_found' }); return; }
      }
      setTimeout(poll, 700);
    }
    poll();
  });
}

export function mediaUrl(songId, rel) {
  return `/media/${encodeURIComponent(songId)}/${rel.split('/').map(encodeURIComponent).join('/')}`;
}
