/* Browser-input safety contract tested without a DOM library.
   Evaluate the real UI functions in an isolated lightweight document stub. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js','utf8');
const start = source.indexOf('function refreshMachineOptions');
const runStart = source.indexOf('async function run(){');
const runEnd = source.indexOf('async function rollingReplan()');
assert(start > 0 && runStart > start && runEnd > runStart);
const elements = new Map();
function element(id) {
  if(!elements.has(id)) {
    const state = {
      disabled:false, hidden:false, textContent:'', style:{},
      attributes:{}, children:[], classList:{toggle(){},contains(){return false;}},
      replaceChildren(...next){this.children=next;},
      setAttribute(key,value){this.attributes[key]=value;},
      append(...next){this.children.push(...next);}
    };
    elements.set(id,state);
  }
  return elements.get(id);
}
const context = vm.createContext({
  document: {
    getElementById:element,
    createElement:tag=>({...element('__created_'+tag),tagName:tag.toUpperCase()})
  }
});
vm.runInContext(source.slice(0,start) + `
  function enterpriseFeedback(message){setStatus(message);}
` + source.slice(runStart,runEnd), context, {timeout:1000});
function evaluate(expr) { return vm.runInContext(expr,context,{timeout:1000}); }
evaluate(`currentScenario={jobs:[],machines:[]}; loadedInputKind='demo'; syncRunAvailability();`);
assert.equal(element('runButton').disabled,false,'Loaded example should be runnable');
evaluate(`lastResult={some:'old result'}; setInputMode('excel');`);
assert.equal(element('runButton').disabled,true,'New Excel mode must not run old demo');
assert.equal(element('modeExcel').attributes['aria-pressed'],'true');
assert.equal(element('excelPanel').hidden,false);
assert.equal(element('demoPanel').hidden,true);
assert.equal(evaluate('lastResult'),null,'Switching source must clear old result');
evaluate(`loadedInputKind='excel'; syncRunAvailability();`);
assert.equal(element('runButton').disabled,false,'Validated workbook enables planning');
evaluate(`invalidateExcelImport();`);
assert.equal(element('runButton').disabled,true,'Changed file invalidates previous validation');
assert.match(element('statusLine').textContent,/Validate/i);
evaluate(`loadedInputKind='demo'; setInputMode('demo');`);
assert.equal(element('runButton').disabled,false,'Returning to loaded sample remains possible');
assert.equal(element('modeDemo').attributes['aria-pressed'],'true');
(async()=>{
  evaluate(`setInputMode('excel'); loadedInputKind=null; syncRunAvailability();`);
  await evaluate('run()');
  assert.match(element('statusLine').textContent,/validate and load your Excel/i,'Run must reject missing workbook at execution too');
  evaluate(`displayPlanningHelp({title:'Shift conflict', explanation:'CNC<script> mismatch', next_step:'Extend the shift.'}, 'fallback');`);
  assert.equal(element('planningHelp').hidden,false);
  assert.equal(element('planningHelpTitle').textContent,'Shift conflict');
  assert.equal(element('planningHelpExplanation').textContent,'CNC<script> mismatch');
  assert.equal(element('planningHelpAction').textContent,'Extend the shift.');
  evaluate('clearPlanningHelp()');
  assert.equal(element('planningHelp').hidden,true);
  console.log('PASS: mode safety and safe accessible planning error guidance.');
})().catch(error=>{console.error(error);process.exitCode=1;});
