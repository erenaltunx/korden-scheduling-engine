'use strict';
const $ = (id) => document.getElementById(id);
let currentScenario = null;
let currentUniversalScenario = null;
let currentTimeUnit = 'hour';
let lastResult = null;
let activeView = 'optimized';
let maxSolverSeconds = 60;
const COLORS = ['#5979e8','#ae74d4','#42a98f','#d18d5d','#be657e','#778ed6','#c3a65a','#56a2bd','#9382d4','#74a67d'];
function e(tag, text, cls) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = String(text);
  if (cls) el.className = cls; return el;
}
function setStatus(msg, error=false) {
  const output=$('statusLine');
  output.textContent=msg;
  output.style.color=error ? '#ab3434' : '#526b74';
}
function setInputMode(mode) {
  // Only the selected input path is shown; both paths keep their data.
  const excel=mode==='excel';
  $('demoPanel').hidden=excel;
  $('excelPanel').hidden=!excel;
  $('modeDemo').classList.toggle('active',!excel);
  $('modeExcel').classList.toggle('active',excel);
  $('modeDemo').setAttribute('aria-pressed',String(!excel));
  $('modeExcel').setAttribute('aria-pressed',String(excel));
}
function refreshMachineOptions(s) {
  const select=$('outageMachine'), prev=select.value;
  select.replaceChildren();
  for (const m of s.machines) {const o=e('option',m.id);o.value=m.id;select.append(o)}
  if(s.machines.some(m=>m.id===prev)) select.value=prev;
}
function applyOutage() {
  if (currentUniversalScenario) {setStatus('Use Resource Studio to change unavailability for this cross-industry workflow.', true);return;}
  let scenario;
  try {scenario=readScenario()} catch(err) {setStatus('Invalid JSON: '+err.message,true);return}
  const mid=$('outageMachine').value,start=Number($('outageStart').value),end=Number($('outageEnd').value);
  if(!mid || !Number.isInteger(start) || !Number.isInteger(end) || start<0 || end>10000 || start>=end){
    setStatus('Enter a valid machine and integer outage start/end times.',true);return;
  }
  const machine=scenario.machines.find(m=>m.id===mid);
  if(!machine){setStatus('Machine not found in current scenario.',true);return}
  const intervals=[...(machine.downtime||[]).map(x=>[x.start,x.end]),[start,end]].sort((a,b)=>a[0]-b[0]);
  const merged=[];
  for(const [a,b] of intervals){const prior=merged[merged.length-1];
    if(!prior||a>prior[1]) merged.push([a,b]);else prior[1]=Math.max(prior[1],b);}
  machine.downtime=merged.map(([a,b])=>({start:a,end:b}));
  scenario.factory_name=(scenario.factory_name||'Factory')+' | what-if outage '+mid+' '+start+'–'+end+'h';
  $('jsonEditor').value=JSON.stringify(scenario,null,2);
  displayStats(scenario);lastResult=null;$('downloadButton').disabled=true;$('exportBiButton').disabled=true;$('rescheduleButton').disabled=true;
  setStatus('Outage applied to scenario; run optimization to calculate new feasible schedule.');
}
function applyShift() {
  if(currentUniversalScenario){setStatus('Working periods are available for production-cell scenarios only.',true);return;}
  let scenario;try{scenario=readScenario()}catch(err){setStatus('Invalid JSON: '+err.message,true);return;}
  const mid=$('outageMachine').value,start=Number($('shiftStart').value),end=Number($('shiftEnd').value);
  if(!mid||!Number.isInteger(start)||!Number.isInteger(end)||start<0||end>10000||start>=end){
    setStatus('Choose a machine and valid working hours.',true);return;
  }
  const machine=scenario.machines.find(m=>m.id===mid);
  if(!machine){setStatus('Unknown machine.',true);return;}
  const periods=[...(machine.working_windows||[]),{start,end}].sort((a,b)=>a.start-b.start);
  if(periods.some((w,i)=>i>0&&periods[i-1].end>w.start)){
    setStatus('Working periods cannot overlap.',true);return;
  }
  machine.working_windows=periods;
  $('jsonEditor').value=JSON.stringify(scenario,null,2);
  displayStats(scenario);lastResult=null;
  $('downloadButton').disabled=true;$('exportBiButton').disabled=true;$('rescheduleButton').disabled=true;
  setStatus('Working period added. Run optimization again to enforce all closures.');
}
function displayStats(s) {
  refreshMachineOptions(s);
  const box=$('scenarioStats');box.replaceChildren();
  const vals=[['Resources', s.machines.length],['Work orders',s.jobs.length],
    ['Operations',s.jobs.reduce((a,j)=>a+j.operations.length,0)],
    ['Unavailable intervals',s.machines.reduce((a,m)=>a+(m.downtime||[]).length,0)],
    ['Changeover-enabled machines',s.machines.filter(m=>(m.changeover_time||0)>0).length],
    ['Work-calendar resources',s.machines.filter(m=>Array.isArray(m.working_windows)).length]];
  for(const [key,val] of vals){const r=e('div',undefined,'scenario-stat-row');r.append(e('span',key),e('strong',val));box.append(r)}
}
function readScenario() {
  const parsed=JSON.parse($('jsonEditor').value);
  if(currentUniversalScenario){if(!parsed.resources||!parsed.work_orders)throw new Error('Expected universal resources and work_orders.');return parsed;}
  if(!parsed.jobs||!parsed.machines)throw new Error('Expected legacy machines and jobs.');
  return parsed;
}
async function loadScenario(name) {
  if(name.startsWith('industry:')){await loadUniversal(name.slice(9));return;}
  currentUniversalScenario = null;currentTimeUnit = 'hour';$('studioEditor').hidden=true;
  setInputMode('demo');
  const isPublic=name.startsWith('public:');
  const res=await fetch(isPublic?('/api/public-benchmarks/'+encodeURIComponent(name.slice(7))):('/api/scenarios/'+encodeURIComponent(name)));
  $('objectiveSelect').value=isPublic?'makespan':'weighted_tardiness';if(!res.ok)throw Error('Could not load scenario');
  currentScenario=await res.json();$('jsonEditor').value=JSON.stringify(currentScenario,null,2);
  displayStats(currentScenario);lastResult=null;$('downloadButton').disabled=true;
  $('kpis').replaceChildren(e('div','Run this scenario to generate your measured benchmark.','empty-kpi'));
  $('timeline').replaceChildren();$('timeline').append(e('div','Ready to optimize.','empty-state'));
  $('experimentMeta').replaceChildren(e('div','No experiment executed.','placeholder'));
  $('runState').textContent='Ready to run';$('rescheduleButton').disabled=true;setStatus('Ready: '+currentScenario.factory_name);
}
function kpi(label, value, old, detail, positive) {
  const c=e('div',undefined,'kpi');c.append(e('div',label,'kpi-label'));
  const vals=e('div',undefined,'kpi-values');vals.append(e('span',value,'kpi-main '+(positive?'good':'neutral')));
  if(old!==null&&old!==undefined)vals.append(e('span',old,'kpi-old'));
  c.append(vals,e('div',detail,'kpi-detail'));return c;
}
function meta(key,val) {const c=e('div');c.append(e('div',key,'meta-key'),e('div',val,'meta-value'));return c}
function renderResult() {
  if(!lastResult||!currentScenario)return;
  const b=lastResult.baseline.metrics,o=lastResult.optimized.metrics,sol=lastResult.solver;
  const baselineName=lastResult.baseline.name||'selected baseline';
  const improvement=lastResult.improvement_percent;
  const isMakespan=lastResult.target_metric==='makespan';
  const area=$('kpis');
  if(isMakespan){
    const target=currentScenario.benchmark_known_optimum_makespan;
    area.replaceChildren(
      kpi('Makespan · '+(currentScenario.benchmark_source?'time units':currentTimeUnit+'s'),o.makespan,b.makespan, improvement===null?'Baseline is zero':`${improvement.toFixed(2)}% shorter vs. ${baselineName}`,o.makespan<b.makespan),
      kpi('Published benchmark optimum',target??'N/A',null, target===undefined?'Not a public benchmark':o.makespan===target?'Reached published value':'Reference target',false),
      kpi('Allocated resource-time',o.machine_busy_hours?Object.values(o.machine_busy_hours).reduce((a,b)=>a+b,0)+' resource-units':'—',null,'Includes concurrent support allocations',false),
      kpi('Solve time · sec',sol.solve_seconds.toFixed(3),null,sol.optimality_proven?'Mathematical optimum proven':'Feasible result; proof not obtained',false)
    );
  }else{
    area.replaceChildren(
      kpi('Weighted tardiness',o.weighted_tardiness,b.weighted_tardiness,improvement===null?'Selected baseline has zero tardiness':`${improvement.toFixed(2)}% improvement vs. ${baselineName}`, o.weighted_tardiness<b.weighted_tardiness),
      kpi('Late customer orders',o.late_jobs,b.late_jobs,`${currentScenario.jobs.length} total orders`,o.late_jobs<b.late_jobs),
      kpi('Makespan · '+currentTimeUnit+'s',o.makespan,b.makespan,'Final completion time',o.makespan<b.makespan),
      kpi('Solve time · sec',sol.solve_seconds.toFixed(3),null,sol.optimality_proven?'Mathematical optimum proven':'Best feasible plan / time limit',false)
    );
  }
  if (currentScenario.machines.some(m => (m.changeover_time || 0) > 0)) {
    area.append(kpi('Required machine changeovers',o.changeover_count,b.changeover_count,
      `${o.setup_time_units} ${currentTimeUnit} setup units vs. ${b.setup_time_units} baseline`,
      o.changeover_count < b.changeover_count));
  }
  $('runState').textContent=sol.optimality_proven ? 'Optimal solution proven' : 'Feasible plan ready';
  const m=$('experimentMeta');m.replaceChildren(meta('Solver',sol.solver),meta('Solver status',sol.status),
    meta('Objective',lastResult.target_metric || 'weighted_tardiness'),
    meta('Variables',sol.model_variables),meta('Linear constraints',sol.model_constraints),
    meta('Optimality proof',sol.optimality_proven?'Yes':'No'),
    meta('Relative optimality gap',sol.relative_mip_gap===null?'Not available':`${(100*sol.relative_mip_gap).toFixed(2)}%`),
    meta('Storage', lastResult.persisted ? 'Saved locally · '+ lastResult.run_id : 'Public demo · not saved'),
    ...(lastResult.stability ? [meta('Frozen operations',lastResult.stability.frozen_operations),
      meta('Changed remaining operations',lastResult.stability.rescheduled_operations),
      meta('Machine reassignments',lastResult.stability.machine_reassignments),
      meta('Start-time shift (hours)',lastResult.stability.total_absolute_start_shift_hours)] : [])); 
  $('downloadButton').disabled=false;$('exportBiButton').disabled=!currentUniversalScenario;$('rescheduleButton').disabled=Boolean(currentUniversalScenario);renderTimeline();
}
function renderTimeline() {
  if(!lastResult||!currentScenario)return;
  const schedule=lastResult[activeView].schedule;
  const machines=currentScenario.machines;
  const extent=Math.max(10,...schedule.map(s=>s.end),...machines.flatMap(m=>(m.downtime||[]).map(w=>w.end)));
  const horizon=Math.ceil(extent/5)*5;
  const plot=$('timeline');plot.replaceChildren();
  const frame=e('div',undefined,'chart-frame');
  const jobIds=currentScenario.jobs.map(j=>j.id);const jobColors=Object.fromEntries(jobIds.map((name,i)=>[name,COLORS[i%COLORS.length]]));
  const percent=v=>(100*v/horizon).toFixed(4)+'%';
  const unit=currentScenario.benchmark_source?'units':(currentTimeUnit==='minute'?'min':'h');
  const replanningClock=lastResult.planning_clock;
  for(const machine of machines){
    const row=e('div',undefined,'timeline-row');row.append(e('div',machine.id,'machine-name'));
    const track=e('div',undefined,'track');
    if(machine.working_windows){
      let cursor=0;
      for(const period of [...machine.working_windows].sort((a,b)=>a.start-b.start)){
        if(cursor<period.start){
          const closed=e('div',undefined,'closed-shift-bar');
          closed.style.left=percent(cursor);closed.style.width=percent(period.start-cursor);
          closed.title=`Closed shift: ${cursor}–${period.start} ${unit}`;track.append(closed);
        }
        cursor=period.end;
      }
      if(cursor<horizon){
        const closed=e('div',undefined,'closed-shift-bar');
        closed.style.left=percent(cursor);closed.style.width=percent(horizon-cursor);
        closed.title=`Closed after ${cursor} ${unit}`;track.append(closed);
      }
    }
    for(const down of machine.downtime||[]){const bar=e('div',undefined,'downtime-bar');bar.style.left=percent(down.start);bar.style.width=percent(down.end-down.start);bar.title=`Maintenance: ${down.start}–${down.end}h`;track.append(bar)}
    for(const task of schedule.filter(t=>t.machine===machine.id || (t.support_resources||[]).includes(machine.id))){
      const bar=e('div',task.job,'task-bar');
      const supporting=task.machine!==machine.id; if(supporting)bar.classList.add('support-task');bar.style.left=percent(task.start);bar.style.width=percent(task.duration);
      bar.style.background=jobColors[task.job];
      const frozen=Number.isInteger(replanningClock)&&task.start<replanningClock;
      if(frozen)bar.classList.add('frozen');
      bar.title=`${task.job} | ${task.operation} | ${task.start}–${task.end} ${unit}`+(supporting?' | Concurrent support resource':' | Primary resource')+(frozen?' | Frozen: already started':'');
      track.append(bar)}
    if(Number.isInteger(replanningClock)) {const clock=e('div',undefined,'planning-clock');clock.style.left=percent(replanningClock);clock.title=`Current simulated factory time: ${replanningClock}`;track.append(clock)}
    row.append(track);frame.append(row)
  }
  const axis=e('div',undefined,'axis');const steps=10;
  for(let i=0;i<=steps;i++){let mark=e('span',String(Math.round(horizon*i/steps))+unit,'axis-mark');mark.style.left=(100*i/steps)+'%';axis.append(mark)}
  frame.append(axis);plot.append(frame);
  const lg=$('chartLegend');lg.replaceChildren();
  for(const name of jobIds){const item=e('span',undefined,'legend-item'),dot=e('span',undefined,'legend-dot');dot.style.background=jobColors[name];item.append(dot,e('span',name));lg.append(item)}
  const item=e('span',undefined,'legend-item'),dot=e('span',undefined,'legend-dot');dot.style.background='#75465b';item.append(dot,e('span','Maintenance'));lg.append(item);
  if(machines.some(m=>m.working_windows)){const closed=e('span',undefined,'legend-item');closed.append(e('span','▤'),'Closed shift');lg.append(closed)}
  if(schedule.some(t=>(t.support_resources||[]).length)){const support=e('span',undefined,'legend-item');support.append(e('span','▥'),'Simultaneous support resource');lg.append(support)}
  if(Number.isInteger(replanningClock)){const fixed=e('span',undefined,'legend-item');fixed.append(e('span','▣'),'Started/locked operations');lg.append(fixed)}
}
function setTab(name){activeView=name;$('tabOptimized').classList.toggle('active',name==='optimized');$('tabBaseline').classList.toggle('active',name==='baseline');renderTimeline()}
async function run(){
  let scenario;try{scenario=readScenario()}catch(err){setStatus('Invalid JSON: '+err.message,true);return}
  const time=Number($('limitInput').value);
  if(!Number.isFinite(time)||time<0.5||time>maxSolverSeconds){setStatus('Time limit must be between 0.5 and '+maxSolverSeconds+' seconds.',true);return}
  if(!currentUniversalScenario){currentScenario=scenario;displayStats(scenario);}
  const btn=$('runButton');btn.disabled=true;btn.textContent='Optimizing workflow…';
  $('runState').textContent='Solving';setStatus('Computing feasible schedule and MILP optimality…');
  try {
    const endpoint=currentUniversalScenario?'/api/universal/run':'/api/run';
    const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario,time_limit:time,engine:$('objectiveSelect').value==='makespan'?'milp_highs':$('engineSelect').value,baseline_policy:$('baselinePolicy').value,objective:$('objectiveSelect').value})});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Server error');
    if(currentUniversalScenario){currentUniversalScenario=scenario;currentScenario=data.normalized_scenario;currentTimeUnit=scenario.time_unit;displayStats(currentScenario);populateStudioEditor();}
    lastResult=data;setTab('optimized');renderResult();await refreshHistory();
    setStatus('Plan ready and validated. '+(data.persisted?'Saved locally. ':'Public demo: download your result to keep it. ')+data.note);
    $('results').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  }catch(err){$('runState').textContent='Error';setStatus('Cannot run: '+err.message,true)}
  finally{btn.disabled=false;btn.innerHTML='<span class="run-icon">▶</span> Generate plan'}
}

async function rollingReplan() {
  if(currentUniversalScenario){setStatus('Rolling rescheduling for universal workflows requires a separate validated resource adapter; not available yet.',true);return;}
  if(!lastResult || !currentScenario){setStatus('Run an optimization first to establish a committed schedule.',true);return}
  const now=Number($('rescheduleNow').value), start=Number($('outageStart').value),end=Number($('outageEnd').value);
  const mid=$('outageMachine').value, time=Number($('limitInput').value);
  if(!Number.isInteger(now)||now<0||now>10000||!Number.isInteger(start)||!Number.isInteger(end)||start<now||end<=start){
    setStatus('Outage must begin at or after a valid current hour, and end after it starts.',true);return;
  }
  if(!Number.isFinite(time)||time<0.5||time>maxSolverSeconds){setStatus('Invalid solver time limit.',true);return}
  const button=$('rescheduleButton');button.disabled=true;
  setStatus('Freezing already-started operations and optimizing remaining work…');
  try{
    const request={scenario:currentScenario,prior_schedule:lastResult.optimized.schedule,
      now,machine_id:mid,outage_start:start,outage_end:end,time_limit:time,
      baseline_policy:$('baselinePolicy').value,objective:$('objectiveSelect').value};
    const resp=await fetch('/api/reschedule',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    const data=await resp.json();if(!resp.ok)throw Error(typeof data.detail==='string'?data.detail:'Server error');
    currentScenario=data.revised_scenario;$('jsonEditor').value=JSON.stringify(currentScenario,null,2);
    lastResult=data;displayStats(currentScenario);setTab('optimized');renderResult();await refreshHistory();
    setStatus(`Rolling schedule validated. ${data.stability.frozen_operations} operations frozen; ${data.stability.rescheduled_operations} future operations changed.`);
  } catch(error){setStatus('Rescheduling refused: '+error.message,true)}
  finally{button.disabled=!lastResult}
}

function downloadResult(){if(!lastResult)return;const b=new Blob([JSON.stringify({scenario:currentUniversalScenario||currentScenario,experiment:lastResult},null,2)],{type:'application/json'});
  const link=document.createElement('a');link.href=URL.createObjectURL(b);link.download='optera_experiment_'+new Date().toISOString().slice(0,10)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}
async function refreshHistory(){
  const history=$('savedHistory');if(!history||$('historyPanel').hidden)return;
  try{
    const resp=await fetch('/api/history?limit=10');if(!resp.ok)throw Error('History not available');
    const items=await resp.json();history.replaceChildren();
    if(!items.length){history.append(e('div','No saved experiments yet.','placeholder'));return}
    for(const item of items){
      const button=e('button', new Date(item.created_at).toLocaleString()+' · '+item.id.slice(0,8),'history-button');
      button.type='button';button.title='Reload saved scenario and result';
      button.addEventListener('click',async()=>{
        try{
          const response=await fetch('/api/history/'+item.id);if(!response.ok)throw Error('Could not retrieve saved experiment');
          const record=await response.json();currentUniversalScenario=record.scenario.resources?record.scenario:null;
          currentTimeUnit=currentUniversalScenario?.time_unit||'hour';currentScenario=currentUniversalScenario?record.result.normalized_scenario:record.scenario;
          $('jsonEditor').value=JSON.stringify(record.scenario,null,2);displayStats(currentScenario);
          $('studioEditor').hidden=!currentUniversalScenario;if(currentUniversalScenario)populateStudioEditor();
          lastResult={...record.result,run_id:record.id,persisted:true};setTab('optimized');renderResult();
          setStatus('Recovered validated experiment '+record.id.slice(0,8)+' from your local history.');
        }catch(err){setStatus(err.message,true)}
      });
      history.append(button);
    }
  }catch(err){history.replaceChildren(e('div','Saved runs cannot be loaded right now.','placeholder'))}
}

function enterpriseFeedback(message, isError=false) {
  const output=$('enterpriseFeedback');
  output.textContent=message;
  output.style.color=isError?'#a53a3a':'#226f5b';
  setStatus(message,isError);
}
function acceptImportedEnterprise(data, format) {
  currentUniversalScenario=data.scenario;currentScenario=data.normalized_scenario;currentTimeUnit=data.scenario.time_unit;
  $('jsonEditor').value=JSON.stringify(data.scenario,null,2);lastResult=null;
  $('downloadButton').disabled=true;$('exportBiButton').disabled=true;$('rescheduleButton').disabled=true;
  $('objectiveSelect').value='weighted_tardiness';
  displayStats(currentScenario);populateStudioEditor();
  $('kpis').replaceChildren(e('div',format+' data validated. Click Run optimization to generate a schedule.','empty-kpi'));
  $('timeline').replaceChildren(e('div','Imported '+data.scenario.industry+' data. Ready to optimize.','empty-state'));
  setInputMode('excel');
  enterpriseFeedback('Ready: '+data.profile.work_orders+' work orders and '+data.profile.steps+' operations validated. Now select Generate plan.');
}
async function importEnterpriseWorkbook() {
  const file=$('enterpriseWorkbook').files[0];
  if(!file || !file.name.toLowerCase().endsWith('.xlsx') || file.size>320*1024 || !file.size) {
    enterpriseFeedback('Choose one .xlsx workbook (up to 320 KiB). Download the example above to see the required tabs.',true);return;
  }
  const button=$('enterpriseWorkbookImport');button.disabled=true;
  try {
    const bytes=new Uint8Array(await file.arrayBuffer());
    const parts=[];
    for(let i=0;i<bytes.length;i+=8192) parts.push(String.fromCharCode(...bytes.subarray(i,i+8192)));
    const workbook_base64=btoa(parts.join(''));
    const response=await fetch('/api/enterprise/import-xlsx',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({workbook_base64,name:$('enterpriseName').value,
        industry:$('enterpriseIndustry').value,time_unit:$('enterpriseUnit').value})
    });
    const data=await response.json();
    if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:'Workbook validation failed');
    acceptImportedEnterprise(data,'Excel');
  }catch(error){enterpriseFeedback('Excel import rejected: '+error.message,true)}
  finally{button.disabled=false}
}

async function importEnterpriseFiles() {
  const selected=[...$('enterpriseFiles').files];
  if(selected.length<3 || selected.length>4) {setStatus('Select 3 required CSV tables and optionally unavailability.csv.',true);return}
  const accepted=['resources.csv','orders.csv','steps.csv','unavailability.csv'];
  const tables={};
  for(const file of selected){
    const basename=file.name.toLowerCase();
    if(!accepted.includes(basename) || tables[basename.slice(0,-4)] !== undefined || file.size>128*1024){
      setStatus('Duplicate, unknown or oversized CSV file: '+file.name,true);return;
    }
    tables[basename.slice(0,-4)]=await file.text();
  }
  const button=$('enterpriseImport');button.disabled=true;
  try {
    const resp=await fetch('/api/enterprise/import-csv',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({tables,name:$('enterpriseName').value,industry:$('enterpriseIndustry').value,time_unit:$('enterpriseUnit').value})});
    const data=await resp.json();if(!resp.ok)throw Error(typeof data.detail==='string'?data.detail:'CSV import failed');
    acceptImportedEnterprise(data,'CSV');
  }catch(error){enterpriseFeedback('CSV import rejected: '+error.message,true)}
  finally{button.disabled=false}
}
async function exportBi() {
  if(!currentUniversalScenario || !lastResult)return;
  const button=$('exportBiButton');button.disabled=true;
  try {
    const resp=await fetch('/api/enterprise/export-bi',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({scenario:currentUniversalScenario,result:lastResult})});
    if(!resp.ok){const err=await resp.json();throw Error(err.detail||'Could not export validated reports')}
    const objectUrl=URL.createObjectURL(await resp.blob()),link=document.createElement('a');
    link.href=objectUrl;link.download='optera-bi-export.zip';link.click();setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
    setStatus('Validated relational report exported for Excel / Power BI.');
  }catch(error){setStatus(error.message,true)}
  finally{button.disabled=false}
}

async function validateUniversal(source) {
  const response=await fetch('/api/universal/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:source})});
  const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Invalid universal workflow');
  return data;
}
function populateStudioEditor() {
  const src=currentUniversalScenario;if(!src)return;
  const orders=$('studioOrder'),selected=orders.value;orders.replaceChildren();
  for(const o of src.work_orders){const option=e('option',o.name);option.value=o.id;orders.append(option)}
  if(src.work_orders.some(o=>o.id===selected))orders.value=selected;
  updateStudioOrderInputs();
  const resources=$('studioResource'),old=resources.value;resources.replaceChildren();
  for(const r of src.resources){const option=e('option',r.name+' · '+r.capabilities.join(', '));option.value=r.id;resources.append(option)}
  if(src.resources.some(r=>r.id===old))resources.value=old;
  $('studioEditor').hidden=false;
  updateStudioResourceInputs();
  $('industrySummary').textContent=src.industry+' · '+src.resources.length+' resources · '+src.work_orders.length+' work orders · '+src.time_unit+' grid. Each step occupies one qualified resource; unsupported real-world constraints remain explicitly excluded.';
}
function updateStudioOrderInputs() {
  const src=currentUniversalScenario;if(!src)return;
  const found=src.work_orders.find(o=>o.id===$('studioOrder').value);
  if(found){$('studioDue').value=String(found.due_at);$('studioPriority').value=String(found.priority)}
  const stepSelect=$('studioStep'), existing=stepSelect.value;stepSelect.replaceChildren();
  for (const st of found?.steps||[]) { const o=e('option',st.name);o.value=st.id;stepSelect.append(o) }
  if ((found?.steps||[]).some(st=>st.id===existing)) stepSelect.value=existing;
  updateStudioStepInputs();
}
function updateStudioStepInputs() {
  const order=currentUniversalScenario?.work_orders.find(o=>o.id===$('studioOrder').value);
  const step=order?.steps.find(st=>st.id===$('studioStep').value);
  $('studioSetupFamily').value=step?.setup_family||'';
}
function updateStudioResourceInputs() {
  const machine=currentUniversalScenario?.resources.find(r=>r.id===$('studioResource').value);
  $('studioChangeoverTime').value=String(machine?.changeover_time||0);
}
async function loadUniversal(id) {
  const response=await fetch('/api/universal/templates/'+encodeURIComponent(id));
  if(!response.ok)throw Error('Could not load sector template');
  const source=await response.json(), validated=await validateUniversal(source);
  currentUniversalScenario=source;currentTimeUnit=source.time_unit;currentScenario=validated.normalized_scenario;
  $('jsonEditor').value=JSON.stringify(source,null,2);$('objectiveSelect').value='weighted_tardiness';
  $('scenarioSelect').value='industry:'+id;$('industrySelect').value=id;
  lastResult=null;$('downloadButton').disabled=true;$('exportBiButton').disabled=true;$('rescheduleButton').disabled=true;
  displayStats(currentScenario);populateStudioEditor();
  $('kpis').replaceChildren(e('div','Run this sector workflow to compare a baseline with optimized resource allocation.','empty-kpi'));
  $('timeline').replaceChildren(e('div','Ready to optimize '+source.industry+'.','empty-state'));
  $('experimentMeta').replaceChildren(e('div','No experiment executed.','placeholder'));
  $('runState').textContent='Ready to run';setStatus('Loaded '+source.industry+' workflow — '+source.name+'.');
}
async function updateUniversalScenario(kind) {
  if(!currentUniversalScenario)return;
  const draft=JSON.parse(JSON.stringify(currentUniversalScenario));
  if(kind==='setup'){
    const resource=draft.resources.find(r=>r.id===$('studioResource').value);
    const order=draft.work_orders.find(o=>o.id===$('studioOrder').value);
    const step=order?.steps.find(st=>st.id===$('studioStep').value);
    const family=$('studioSetupFamily').value.trim(),setup=Number($('studioChangeoverTime').value);
    if(!resource||!step||!Number.isInteger(setup)||setup<0||setup>120||family.length>40){setStatus('Choose a machine and operation; enter setup time 0–120.',true);return}
    if(family) step.setup_family=family;else delete step.setup_family;
    if(setup) resource.changeover_time=setup;else delete resource.changeover_time;
  } else if(kind==='order'){
    const target=draft.work_orders.find(o=>o.id===$('studioOrder').value);
    const due=Number($('studioDue').value),priority=Number($('studioPriority').value);
    if(!target||!Number.isInteger(due)||due<0||due>10000||!Number.isInteger(priority)||priority<1||priority>100){setStatus('Enter a valid due time and a priority between 1 and 100.',true);return}
    target.due_at=due;target.priority=priority;
  } else {
    const target=draft.resources.find(r=>r.id===$('studioResource').value);
    const start=Number($('studioDownStart').value),end=Number($('studioDownEnd').value);
    if(!target||!Number.isInteger(start)||!Number.isInteger(end)||start<0||end>10000||end<=start){setStatus('Enter a valid resource-unavailability interval.',true);return}
    const windows=[...(target.unavailable||[]),{start,end}].sort((a,b)=>a.start-b.start);const merged=[];
    for(const win of windows){const last=merged[merged.length-1];if(last&&win.start<=last.end)last.end=Math.max(last.end,win.end);else merged.push({...win})}
    target.unavailable=merged;
  }
  try{
    const validated=await validateUniversal(draft);
    currentUniversalScenario=draft;currentScenario=validated.normalized_scenario;
    $('jsonEditor').value=JSON.stringify(draft,null,2);
    lastResult=null;$('downloadButton').disabled=true;$('exportBiButton').disabled=true;$('rescheduleButton').disabled=true;
    displayStats(currentScenario);populateStudioEditor();
    setStatus('Resource/work order update validated. Run optimization to compare the revised schedule.');
  }catch(err){setStatus('Update rejected without changing your scenario: '+err.message,true)}
}

async function boot(){
  // Align the solver control with the public demo's resource limits.
  try {
    const cfgResponse = await fetch('/api/config');
    if (cfgResponse.ok) {
      const cfg = await cfgResponse.json();
      maxSolverSeconds = cfg.max_solver_seconds;
      $('historyPanel').hidden = !cfg.archive_enabled;
      $('limitInput').max = String(maxSolverSeconds);
      if (Number($('limitInput').value) > maxSolverSeconds)
        $('limitInput').value = String(Math.min(4, maxSolverSeconds));
    }
  } catch (error) { /* Local fallback retains documented 60-second cap. */ }
  $('modeDemo').addEventListener('click',()=>setInputMode('demo'));
  $('modeExcel').addEventListener('click',()=>setInputMode('excel'));
  $('applyOutage').addEventListener('click',applyOutage);
  $('applyShift').addEventListener('click',applyShift);
  $('rescheduleButton').addEventListener('click',rollingReplan);
  $('enterpriseWorkbookImport').addEventListener('click',importEnterpriseWorkbook);
  $('enterpriseImport').addEventListener('click',importEnterpriseFiles);$('exportBiButton').addEventListener('click',exportBi);
  $('runButton').addEventListener('click',run);$('tabOptimized').addEventListener('click',()=>setTab('optimized'));
  $('tabBaseline').addEventListener('click',()=>setTab('baseline'));$('downloadButton').addEventListener('click',downloadResult);
  $('toggleEditor').addEventListener('click',()=>{$('editorPanel').hidden=!$('editorPanel').hidden});
  $('scenarioSelect').addEventListener('change',async(ev)=>{try{await loadScenario(ev.target.value)}catch(err){setStatus(err.message,true)}});
  $('loadIndustryButton').addEventListener('click',async()=>{try{await loadUniversal($('industrySelect').value)}catch(err){setStatus(err.message,true)}});
  $('studioOrder').addEventListener('change',updateStudioOrderInputs);
  $('studioStep').addEventListener('change',updateStudioStepInputs);
  $('studioResource').addEventListener('change',updateStudioResourceInputs);
  $('studioApplySetup').addEventListener('click',()=>updateUniversalScenario('setup'));
  $('studioApplyOrder').addEventListener('click',()=>updateUniversalScenario('order'));
  $('studioApplyDown').addEventListener('click',()=>updateUniversalScenario('resource')); 
  try{const resp=await fetch('/api/scenarios');if(!resp.ok)throw Error('Could not load scenarios');
    const scenarios=await resp.json();const selector=$('scenarioSelect');selector.replaceChildren();
    for(const s of scenarios){const opt=e('option',s.name);opt.value=s.id;selector.append(opt)}
    if(!$('historyPanel').hidden){
      const publicResp=await fetch('/api/public-benchmarks');
      if(publicResp.ok){for(const s of await publicResp.json()){
        const opt=e('option',s.name);opt.value='public:'+s.id;selector.append(opt);
      }}
    }
    try{const industryResponse=await fetch('/api/universal/templates');if(industryResponse.ok){
      const templates=await industryResponse.json();const industrySelector=$('industrySelect');industrySelector.replaceChildren();
      for(const item of templates){const opt=e('option',item.industry+' · '+item.name);opt.value=item.id;industrySelector.append(opt);
        const opt2=e('option',item.industry+' · '+item.name);opt2.value='industry:'+item.id;selector.append(opt2);}
      if(templates.length)$('industrySummary').textContent='Choose one of '+templates.length+' sector templates, then edit priorities and availability without writing JSON.';
    }}catch(err){setStatus('Sector templates are temporarily unavailable: '+err.message,true);}
    const chosen=scenarios.find(x=>x.id==='setup_cell')||scenarios[0];if(chosen){selector.value=chosen.id;await loadScenario(chosen.id)}
  }catch(err){setStatus(err.message,true)}
  await refreshHistory();
}
boot();
