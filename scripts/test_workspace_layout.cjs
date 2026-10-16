const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/js/workspace-layout.js'),'utf8');
function setup(mobile){
  const events={},navEvents={},toggleEvents={};
  const icon={textContent:''};
  const document={activeElement:null,addEventListener:(name,callback)=>events[name]=callback};
  const toggle={hidden:true,attributes:{},setAttribute(key,value){this.attributes[key]=value;},querySelector:()=>icon,addEventListener:(name,callback)=>toggleEvents[name]=callback,focus(){document.activeElement=toggle;}};
  const navigation={hidden:false,contains:element=>element==='link',addEventListener:(name,callback)=>navEvents[name]=callback};
  const media={matches:mobile,addEventListener(name,callback){this.changed=callback;}};
  document.querySelector=selector=>selector.startsWith('[data-workspace-nav')?toggle:navigation;
  vm.runInNewContext(source,{document,window:{matchMedia:()=>media},String});events.DOMContentLoaded();
  return {document,toggle,navigation,media,icon,navEvents,toggleEvents};
}
test('compact menu starts closed, opens on click, and Escape restores focus',()=>{
  const h=setup(true);assert.equal(h.navigation.hidden,true);assert.equal(h.toggle.hidden,false);
  h.toggleEvents.click();assert.equal(h.navigation.hidden,false);assert.equal(h.toggle.attributes['aria-expanded'],'true');
  h.navEvents.keydown({key:'Escape'});assert.equal(h.navigation.hidden,true);assert.equal(h.document.activeElement,h.toggle);
  h.toggleEvents.click();h.toggleEvents.keydown({key:'Escape'});assert.equal(h.navigation.hidden,true);
});
test('desktop navigation stays visible; entering compact layout restores focused link to toggle',()=>{
  const h=setup(false);assert.equal(h.navigation.hidden,false);assert.equal(h.toggle.hidden,true);
  h.document.activeElement='link';h.media.matches=true;h.media.changed();
  assert.equal(h.navigation.hidden,true);assert.equal(h.document.activeElement,h.toggle);
  h.media.matches=false;h.media.changed();assert.equal(h.navigation.hidden,false);assert.equal(h.toggle.hidden,true);
});
