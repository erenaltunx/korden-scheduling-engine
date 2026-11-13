'use strict';
const $ = (id) => document.getElementById(id);
let currentScenario = null;
let lastResult = null;
let activeView = 'optimized';
let maxSolverSeconds = 60;
const COLORS = ['#5979e8','#ae74d4','#42a98f','#d18d5d','#be657e','#778ed6','#c3a65a','#56a2bd','#9382d4','#74a67d'];
function e(tag, text, cls) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = String(text);
  if (cls) el.className = cls; return el;
}
function setStatus(msg, error=false) {
  $('statusLine').textContent = msg; $('statusLine').style.color = error ? '#f5a2a2' : '#8997b1';
}
function refreshMachineOptions(s) {
  const select=$('outageMachine'), prev=select.value;
  select.replaceChildren();
  for (const m of s.machines) {const o=e('option',m.id);o.value=m.id;select.append(o)}
  if(s.machines.some(m=>m.id===prev)) select.value=prev;
}
function applyOutage() {
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
  displayStats(scenario);lastResult=null;$('downloadButton').disabled=true;$('rescheduleButton').disabled=true;
  setStatus('Outage applied to scenario; run optimization to calculate new feasible schedule.');
}
function displayStats(s) {
  refreshMachineOptions(s);
  const box=$('scenarioStats');box.replaceChildren();
  const vals=[['Machines', s.machines.length],['Production orders',s.jobs.length],
    ['Operations',s.jobs.reduce((a,j)=>a+j.operations.length,0)],
    ['Maintenance windows',s.machines.reduce((a,m)=>a+(m.downtime||[]).length,0)]];
  for(const [key,val] of vals){const r=e('div',undefined,'scenario-stat-row');r.append(e('span',key),e('strong',val));box.append(r)}
}
function readScenario() {
  const parsed=JSON.parse($('jsonEditor').value);
  if(!parsed.jobs||!parsed.machines)throw new Error('JSON needs machines and jobs arrays.');
  return parsed;
}
async function loadScenario(name) {
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
      kpi('Makespan · '+(currentScenario.benchmark_source?'time units':'hours'),o.makespan,b.makespan, improvement===null?'Baseline is zero':`${improvement.toFixed(2)}% shorter vs. ${baselineName}`,o.makespan<b.makespan),
      kpi('Published benchmark optimum',target??'N/A',null, target===undefined?'Not a public benchmark':o.makespan===target?'Reached published value':'Reference target',false),
      kpi('Scheduled operations',o.machine_busy_hours?Object.values(o.machine_busy_hours).reduce((a,b)=>a+b,0)+' machine-hours':'—',null,'Total processing machine-hours',false),
      kpi('Solve time · sec',sol.solve_seconds.toFixed(3),null,sol.optimality_proven?'Mathematical optimum proven':'Feasible result; proof not obtained',false)
    );
  }else{
    area.replaceChildren(
      kpi('Weighted tardiness',o.weighted_tardiness,b.weighted_tardiness,improvement===null?'Selected baseline has zero tardiness':`${improvement.toFixed(2)}% improvement vs. ${baselineName}`, o.weighted_tardiness<b.weighted_tardiness),
      kpi('Late customer orders',o.late_jobs,b.late_jobs,`${currentScenario.jobs.length} total orders`,o.late_jobs<b.late_jobs),
      kpi('Makespan · hours',o.makespan,b.makespan,'Final completion time',o.makespan<b.makespan),
      kpi('Solve time · sec',sol.solve_seconds.toFixed(3),null,sol.optimality_proven?'Mathematical optimum proven':'Best feasible plan / time limit',false)
    );
  }
  $('runState').textContent=sol.status.replaceAll('_',' ');
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
  $('downloadButton').disabled=false;$('rescheduleButton').disabled=false;renderTimeline();
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
  const unit=currentScenario.benchmark_source?'units':'h';
  const replanningClock=lastResult.planning_clock;
  for(const machine of machines){
    const row=e('div',undefined,'timeline-row');row.append(e('div',machine.id,'machine-name'));
    const track=e('div',undefined,'track');
    for(const down of machine.downtime||[]){const bar=e('div',undefined,'downtime-bar');bar.style.left=percent(down.start);bar.style.width=percent(down.end-down.start);bar.title=`Maintenance: ${down.start}–${down.end}h`;track.append(bar)}
    for(const task of schedule.filter(t=>t.machine===machine.id)){
      const bar=e('div',task.job,'task-bar');bar.style.left=percent(task.start);bar.style.width=percent(task.duration);
      bar.style.background=jobColors[task.job];
      const frozen=Number.isInteger(replanningClock)&&task.start<replanningClock;
      if(frozen)bar.classList.add('frozen');
      bar.title=`${task.job} | ${task.operation} | ${task.start}–${task.end} ${unit}`+(frozen?' | Frozen: already started':'');
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
  if(Number.isInteger(replanningClock)){const fixed=e('span',undefined,'legend-item');fixed.append(e('span','▣'),'Started/locked operations');lg.append(fixed)}
}
function setTab(name){activeView=name;$('tabOptimized').classList.toggle('active',name==='optimized');$('tabBaseline').classList.toggle('active',name==='baseline');renderTimeline()}
async function run(){
  let scenario;try{scenario=readScenario()}catch(err){setStatus('Invalid JSON: '+err.message,true);return}
  const time=Number($('limitInput').value);
  if(!Number.isFinite(time)||time<0.5||time>maxSolverSeconds){setStatus('Time limit must be between 0.5 and '+maxSolverSeconds+' seconds.',true);return}
  currentScenario=scenario;displayStats(scenario);const btn=$('runButton');btn.disabled=true;btn.textContent='Optimizing production…';
  $('runState').textContent='Solving';setStatus('Computing feasible schedule and MILP optimality…');
  try {
    const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario,time_limit:time,baseline_policy:$('baselinePolicy').value,objective:$('objectiveSelect').value})});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Server error');
    lastResult=data;setTab('optimized');renderResult();await refreshHistory();setStatus('Completed and validated. '+(data.persisted?'Saved to your local experiment history. ': 'Public demo, export results to keep them. ')+data.note);
  }catch(err){$('runState').textContent='Error';setStatus('Cannot run: '+err.message,true)}
  finally{btn.disabled=false;btn.innerHTML='<span class="run-icon">▶</span> Run optimization'}
}

async function rollingReplan() {
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

function downloadResult(){if(!lastResult)return;const b=new Blob([JSON.stringify({scenario:currentScenario,experiment:lastResult},null,2)],{type:'application/json'});
  const link=document.createElement('a');link.href=URL.createObjectURL(b);link.download='korden_experiment_'+new Date().toISOString().slice(0,10)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}
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
          const record=await response.json();currentScenario=record.scenario;
          $('jsonEditor').value=JSON.stringify(currentScenario,null,2);displayStats(currentScenario);
          lastResult={...record.result,run_id:record.id,persisted:true};setTab('optimized');renderResult();
          setStatus('Recovered validated experiment '+record.id.slice(0,8)+' from your local history.');
        }catch(err){setStatus(err.message,true)}
      });
      history.append(button);
    }
  }catch(err){history.replaceChildren(e('div','Saved runs cannot be loaded right now.','placeholder'))}
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
  $('applyOutage').addEventListener('click',applyOutage);
  $('rescheduleButton').addEventListener('click',rollingReplan);
  $('runButton').addEventListener('click',run);$('tabOptimized').addEventListener('click',()=>setTab('optimized'));
  $('tabBaseline').addEventListener('click',()=>setTab('baseline'));$('downloadButton').addEventListener('click',downloadResult);
  $('toggleEditor').addEventListener('click',()=>{$('editorPanel').hidden=!$('editorPanel').hidden});
  $('scenarioSelect').addEventListener('change',async(ev)=>{try{await loadScenario(ev.target.value)}catch(err){setStatus(err.message,true)}});
  try{const resp=await fetch('/api/scenarios');if(!resp.ok)throw Error('Could not load scenarios');
    const scenarios=await resp.json();const selector=$('scenarioSelect');selector.replaceChildren();
    for(const s of scenarios){const opt=e('option',s.name);opt.value=s.id;selector.append(opt)}
    if(!$('historyPanel').hidden){
      const publicResp=await fetch('/api/public-benchmarks');
      if(publicResp.ok){for(const s of await publicResp.json()){
        const opt=e('option',s.name);opt.value='public:'+s.id;selector.append(opt);
      }}
    }
    const chosen=scenarios.find(x=>x.id==='assembly_cell')||scenarios[0];if(chosen){selector.value=chosen.id;await loadScenario(chosen.id)}
  }catch(err){setStatus(err.message,true)}
  await refreshHistory();
}
boot();
