import {repairChannels} from './recording-repair.mjs';
self.onmessage=({data})=>{
  try{
    const result=repairChannels(data.channels,data.rate,data.settings,data.meta,data.shift,(phase,percent)=>self.postMessage({phase,percent}));
    self.postMessage({result},result.channels.map(x=>x.buffer));
  }catch(error){self.postMessage({error:error.message});}
};
