import {recordingReviewKey} from './recording-review.mjs';

export function libraryRecordingCounts(rows){
  const counts=new Map();
  for(const row of rows){
    const key=recordingReviewKey(row.post?.reference);
    if(!key||row.segmentComposition)continue;
    const kind=row.segmentTake?'segments':row.postPending?'whole':null;
    if(!kind)continue;
    if(!counts.has(key))counts.set(key,{whole:0,segments:0});
    counts.get(key)[kind]++;
  }
  return counts;
}

function label({whole=0,segments=0}={}){
  return [whole?`整首待確認 ${whole} 筆`:'',segments?`分段錄音 ${segments} 筆`:''].filter(Boolean).join(' · ');
}

// Update existing buttons without disturbing selection, focus or folded groups.
export function updateLibraryRecordingBadges(list,counts){
  for(const button of list.querySelectorAll('.song-choice')){
    const text=label(counts.get(button.dataset.reviewKey));
    let badge=button.querySelector('.song-pending-badge');
    if(!badge){badge=document.createElement('span');badge.className='song-pending-badge';button.append(badge);}
    badge.textContent=text;badge.hidden=!text;
    button.classList.toggle('has-pending-review',!!text);
    button.setAttribute('aria-label',`載入 ${button.querySelector('strong').textContent}${text?' · '+text:''}`);
  }
  for(const group of list.querySelectorAll('.song-key-group')){
    const summary=group.querySelector('summary');
    let badge=summary.querySelector('.song-pending-badge');
    if(!badge){badge=document.createElement('span');badge.className='song-pending-badge';summary.append(badge);}
    const totals={whole:0,segments:0};
    for(const button of group.querySelectorAll('.song-choice')){
      const count=counts.get(button.dataset.reviewKey);
      if(count){totals.whole+=count.whole;totals.segments+=count.segments;}
    }
    badge.textContent=label(totals);badge.hidden=!badge.textContent;
  }
}
