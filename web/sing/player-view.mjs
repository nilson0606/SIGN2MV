// Move the viewport, never the media element: reparenting an iframe reloads it.
export function revealPlayerVideo() {
  const section=document.getElementById('player-section');
  const video=section?.querySelector('.video-shell');
  if(!video)return;
  section.focus({preventScroll:true});
  const align=()=>{
    const nav=document.querySelector('.section-nav');
    if(nav)document.documentElement.style.setProperty('--nav-offset',`${nav.offsetHeight+16}px`);
    video.scrollIntoView({block:'start',behavior:'instant'});
  };
  align();
  // The recording guide updates on the next frame and may wrap differently.
  requestAnimationFrame(()=>requestAnimationFrame(align));
}
