const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/workspace-reminders.js'), 'utf8');
function harness(fetch) {
  const badge = {textContent:'2'}, unassigned = {textContent:'1'};
  const link = {setAttribute(key,value) { this[key]=value; }};
  const handlers = {};
  let interval;
  const root = {dataset:{reminderCountsUrl:'/workspace/notifications/counts/'}, querySelectorAll(selector) { return selector.includes('unassigned') ? [unassigned] : [badge]; }, querySelector() { return link; }};
  const document = {hidden:false,querySelector() { return root; },addEventListener(name,callback) { handlers[name]=callback; }};
  const window = {setInterval(callback,ms) { assert.equal(ms,60000);interval=callback; },addEventListener(name,callback) { handlers[name]=callback; }};
  vm.runInNewContext(source,{document,window,fetch,Number,String});
  handlers.DOMContentLoaded();
  return {badge,unassigned,link,document,tick:()=>interval(),handlers};
}
const response = counts => ({ok:true,status:200,redirected:false,headers:{get:()=> 'application/json'},json:async()=>counts});
test('poll updates personal and unassigned counts and accessible badge text',async()=>{
  const h=harness(async(url,options)=>{assert.equal(url,'/workspace/notifications/counts/');assert.equal(options.cache,'no-store');return response({total:3,overdue:2,today:1,unassigned:4});});
  await h.tick();
  assert.equal(h.badge.textContent,'3'); assert.equal(h.unassigned.textContent,'4');assert.match(h.link['aria-label'],/^3 follow-up reminders/);
});
test('hidden tabs do not poll; authentication expiry stops further polling',async()=>{
  let calls=0;
  const h=harness(async()=>{calls++;return {redirected:true,status:200};});
  h.document.hidden=true; await h.tick();assert.equal(calls,0);
  h.document.hidden=false; await h.handlers.visibilitychange();assert.equal(calls,1);
  await h.tick();assert.equal(calls,1);assert.equal(h.badge.textContent,'2');
});
test('temporary network errors and invalid payloads preserve the previous count',async()=>{
  let calls=0;
  const h=harness(async()=>{calls++;if(calls===1)throw new Error('offline');return response({total:-1,overdue:0,today:0,unassigned:0});});
  await h.tick();await h.tick();assert.equal(calls,2);assert.equal(h.badge.textContent,'2');
});
