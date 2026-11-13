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
function displayStats(s) {
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
  const res=await fetch('/api/scenarios/'+encodeURIComponent(name));if(!res.ok)throw Error('Could not load scenario');
  currentScenario=await res.json();$('jsonEditor').value=JSON.stringify(currentScenario,null,2);
  displayStats(currentScenario);lastResult=null;$('downloadButton').disabled=true;
  $('kpis').replaceChildren(e('div','Run this scenario to generate your measured benchmark.','empty-kpi'));
  $('timeline').replaceChildren();$('timeline').append(e('div','Ready to optimize.','empty-state'));
  $('experimentMeta').replaceChildren(e('div','No experiment executed.','placeholder'));
  $('runState').textContent='Ready to run';setStatus('Ready: '+currentScenario.factory_name);
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
  const improvement=lastResult.improvement_percent;
  const area=$('kpis');area.replaceChildren(
    kpi('Weighted tardiness',o.weighted_tardiness,b.weighted_tardiness,improvement===null?'EDD baseline has zero tardiness':`${improvement.toFixed(2)}% improvement vs. EDD`, o.weighted_tardiness<b.weighted_tardiness),
    kpi('Late customer orders',o.late_jobs,b.late_jobs,`${currentScenario.jobs.length} total orders`,o.late_jobs<b.late_jobs),
    kpi('Makespan · hours',o.makespan,b.makespan,'Final completion time',o.makespan<b.makespan),
    kpi('Solve time · sec',sol.solve_seconds.toFixed(3),null,sol.optimality_proven?'Mathematical optimum proven':'Best feasible plan / time limit',false)
  );
  $('runState').textContent=sol.status.replaceAll('_',' ');
  const m=$('experimentMeta');m.replaceChildren(meta('Solver',sol.solver),meta('Solver status',sol.status),
    meta('Variables',sol.model_variables),meta('Linear constraints',sol.model_constraints),
    meta('Optimality proof',sol.optimality_proven?'Yes':'No'),
    meta('Relative optimality gap',sol.relative_mip_gap===null?'Not available':`${(100*sol.relative_mip_gap).toFixed(2)}%`),
    meta('Storage', lastResult.persisted ? 'Saved locally · '+ lastResult.run_id : 'Public demo · not saved')); 
  $('downloadButton').disabled=false;renderTimeline();
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
  for(const machine of machines){
    const row=e('div',undefined,'timeline-row');row.append(e('div',machine.id,'machine-name'));
    const track=e('div',undefined,'track');
    for(const down of machine.downtime||[]){const bar=e('div',undefined,'downtime-bar');bar.style.left=percent(down.start);bar.style.width=percent(down.end-down.start);bar.title=`Maintenance: ${down.start}–${down.end}h`;track.append(bar)}
    for(const task of schedule.filter(t=>t.machine===machine.id)){
      const bar=e('div',task.job,'task-bar');bar.style.left=percent(task.start);bar.style.width=percent(task.duration);
      bar.style.background=jobColors[task.job];bar.title=`${task.job} | ${task.operation} | ${task.start}–${task.end}h`;track.append(bar)}
    row.append(track);frame.append(row)
  }
  const axis=e('div',undefined,'axis');const steps=10;
  for(let i=0;i<=steps;i++){let mark=e('span',String(Math.round(horizon*i/steps))+'h','axis-mark');mark.style.left=(100*i/steps)+'%';axis.append(mark)}
  frame.append(axis);plot.append(frame);
  const lg=$('chartLegend');lg.replaceChildren();
  for(const name of jobIds){const item=e('span',undefined,'legend-item'),dot=e('span',undefined,'legend-dot');dot.style.background=jobColors[name];item.append(dot,e('span',name));lg.append(item)}
  const item=e('span',undefined,'legend-item'),dot=e('span',undefined,'legend-dot');dot.style.background='#75465b';item.append(dot,e('span','Maintenance'));lg.append(item);
}
function setTab(name){activeView=name;$('tabOptimized').classList.toggle('active',name==='optimized');$('tabBaseline').classList.toggle('active',name==='baseline');renderTimeline()}
async function run(){
  let scenario;try{scenario=readScenario()}catch(err){setStatus('Invalid JSON: '+err.message,true);return}
  const time=Number($('limitInput').value);
  if(!Number.isFinite(time)||time<0.5||time>maxSolverSeconds){setStatus('Time limit must be between 0.5 and '+maxSolverSeconds+' seconds.',true);return}
  currentScenario=scenario;displayStats(scenario);const btn=$('runButton');btn.disabled=true;btn.textContent='Optimizing production…';
  $('runState').textContent='Solving';setStatus('Computing feasible schedule and MILP optimality…');
  try {
    const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario,time_limit:time})});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Server error');
    lastResult=data;setTab('optimized');renderResult();await refreshHistory();setStatus('Completed and validated. '+(data.persisted?'Saved to your local experiment history. ': 'Public demo, export results to keep them. ')+data.note);
  }catch(err){$('runState').textContent='Error';setStatus('Cannot run: '+err.message,true)}
  finally{btn.disabled=false;btn.innerHTML='<span class="run-icon">▶</span> Run optimization'}
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
  $('runButton').addEventListener('click',run);$('tabOptimized').addEventListener('click',()=>setTab('optimized'));
  $('tabBaseline').addEventListener('click',()=>setTab('baseline'));$('downloadButton').addEventListener('click',downloadResult);
  $('toggleEditor').addEventListener('click',()=>{$('editorPanel').hidden=!$('editorPanel').hidden});
  $('scenarioSelect').addEventListener('change',async(ev)=>{try{await loadScenario(ev.target.value)}catch(err){setStatus(err.message,true)}});
  try{const resp=await fetch('/api/scenarios');if(!resp.ok)throw Error('Could not load scenarios');
    const scenarios=await resp.json();const selector=$('scenarioSelect');selector.replaceChildren();
    for(const s of scenarios){const opt=e('option',s.name);opt.value=s.id;selector.append(opt)}
    const chosen=scenarios.find(x=>x.id==='assembly_cell')||scenarios[0];if(chosen){selector.value=chosen.id;await loadScenario(chosen.id)}
  }catch(err){setStatus(err.message,true)}
  await refreshHistory();
}
boot();
