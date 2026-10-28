import {messages,templates} from './i18n-catalog.mjs';

export const languageKey='karaoke.language.v1';
const han=/[\u3400-\u9fff]/;
const normalize=text=>text.trim().replace(/\s+/g,' ');
const dictionary=new Map(Object.entries(messages).map(([source,target])=>[normalize(source),target]));
const escape=text=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const patterns=templates.map(([source,target,translate=[],segmentNames=[]])=>{
  const slots=[];let cursor=0,pattern='';
  for(const match of source.matchAll(/\{(\d+)\}/g)){
    pattern+=escape(source.slice(cursor,match.index)).replace(/\s+/g,'\\s+');
    const slot=Number(match[1]),adjacent=/^\{\d+\}/.test(source.slice(match.index+match[0].length));
    pattern+=!translate.includes(slot)&&adjacent?'([\\s\\S]*)':'([\\s\\S]*?)';slots.push(slot);cursor=match.index+match[0].length;
  }
  pattern+=escape(source.slice(cursor)).replace(/\s+/g,'\\s+');
  return {source,target,translate,segmentNames,slots,regex:new RegExp('^'+pattern+'$'),weight:source.replace(/\{\d+\}/g,'').length};
}).sort((a,b)=>b.weight-a.weight);
let language='zh-Hant';
try{if(globalThis.localStorage?.getItem(languageKey)==='en')language='en';}catch{}
export const getLanguage=()=>language;

// Translate only known application messages. Captured titles, names and paths
// stay literal; templates explicitly opt UI fragments into recursive translation.
export function translateMessage(text,locale=language,depth=0){
  if(typeof text!=='string'||locale!=='en'||!han.test(text)||depth>5)return text;
  const trimmed=text.trim(),direct=dictionary.get(normalize(trimmed));
  if(direct!==undefined)return text.slice(0,text.indexOf(trimmed))+direct+text.slice(text.indexOf(trimmed)+trimmed.length);
  for(const item of patterns){
    const match=item.regex.exec(trimmed);if(!match)continue;
    const values=new Map(item.slots.map((slot,i)=>[slot,match[i+1]]));
    const translated=item.target.replace(/\{(\d+)\}/g,(_,key)=>{
      const slot=Number(key),value=values.get(slot)??'';
      if(item.segmentNames.includes(slot))return value.split('、').map(name=>/^第\s*\d+\s*段(?:（後段）)*$/.test(name)?translateMessage(name,locale,depth+1):name).join(', ');
      return item.translate.includes(slot)?translateMessage(value,locale,depth+1):value;
    });
    return text.slice(0,text.indexOf(trimmed))+translated+text.slice(text.indexOf(trimmed)+trimmed.length);
  }
  return text;
}
export const localizedConfirm=message=>window.confirm(translateMessage(message));
export function userOption(label,value){const option=new Option(label,value);option.dataset.i18nUser='';return option;}

export function userText(text){const span=document.createElement('span');span.dataset.i18nUser='';span.textContent=text;return span;}

const originals=new WeakMap(),attributes=new WeakMap();
const skip='script,style,code,textarea,svg,[translate="no"],[data-i18n-user],[data-i18n-skip]';
export function originalText(node){
  if(!node)return '';
  if(node.nodeType===3){const entry=originals.get(node);return entry&&node.data===entry.rendered?entry.source:node.data;}
  return [...node.childNodes].map(originalText).join('');
}
function textNode(node){
  const parent=node.parentElement;if(!parent||parent.closest(skip))return;
  const old=originals.get(node),source=old&&node.data===old.rendered?old.source:node.data;
  if(!han.test(source)&&!old)return;
  // Translating an implicit option value must not change what the application saves.
  if(parent.tagName==='OPTION'&&!parent.hasAttribute('value'))parent.value=parent.textContent;
  const rendered=translateMessage(source);originals.set(node,{source,rendered});
  if(node.data!==rendered)node.data=rendered;
}
const translatedAttributes=['title','aria-label','placeholder','alt'];
function element(node){
  if(node.closest(skip))return;
  let saved=attributes.get(node);if(!saved){saved={};attributes.set(node,saved);}
  for(const name of translatedAttributes){
    const value=node.getAttribute(name);if(value===null){delete saved[name];continue;}
    const old=saved[name],source=old&&value===old.rendered?old.source:value;
    if(!han.test(source)&&!old)continue;
    const rendered=translateMessage(source);saved[name]={source,rendered};
    if(value!==rendered)node.setAttribute(name,rendered);
  }
}
function scan(root){
  if(root.nodeType===3){textNode(root);return;}
  if(root.nodeType!==1&&root.nodeType!==9)return;
  if(root.nodeType===1){if(root.closest(skip))return;element(root);}
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_ELEMENT|NodeFilter.SHOW_TEXT,{acceptNode:node=>node.nodeType===1&&node.matches(skip)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
  while(walker.nextNode()){const node=walker.currentNode;if(node.nodeType===3)textNode(node);else element(node);}
}
function manualLinks(){for(const link of document.querySelectorAll('a[data-language-manual]'))link.href=language==='en'?'manual.en.html':'manual.html';}
export function setLanguage(value,{persist=true}={}){
  language=value==='en'?'en':'zh-Hant';
  if(persist)try{localStorage.setItem(languageKey,language);}catch{}
  if(typeof document==='undefined')return;
  document.documentElement.lang=language;
  for(const picker of document.querySelectorAll('[data-language-picker]'))picker.value=language;
  scan(document);manualLinks();
  const manual=document.documentElement.dataset.manualLanguage;
  if(manual&&manual!==language){location.replace((language==='en'?'manual.en.html':'manual.html')+location.hash);return;}
  window.dispatchEvent(new CustomEvent('karaoke-language-change',{detail:{language}}));
}
if(typeof document!=='undefined'){
  const init=()=>{
    setLanguage(language,{persist:false});
    for(const picker of document.querySelectorAll('[data-language-picker]'))picker.addEventListener('change',()=>setLanguage(picker.value));
    const observer=new MutationObserver(records=>{
      for(const record of records){
        if(record.type==='characterData')textNode(record.target);
        else if(record.type==='attributes')element(record.target);
        else for(const node of record.addedNodes)scan(node);
      }
    });
    observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:translatedAttributes});
    window.addEventListener('storage',event=>{if(event.key===languageKey)setLanguage(event.newValue,{persist:false});});
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
}
