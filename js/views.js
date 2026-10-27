/* views.js - All pages: Dashboard, Students, Teachers, Subjects, Classes, Fees, Salaries, About */
const head=(t,p,btn='')=>`<div class="top"><div><h1>${t}</h1><p>${p}</p></div><div class="row" style="gap:10px">${btn}<button class="btn ghost" data-act="pw">🔑 Password</button><button class="btn ghost" data-act="out">Log out</button></div></div>`;
const stat=(ic,n,l)=>`<div class="card stat"><span class="ic">${ic}</span><b>${n}</b><span>${l}</span></div>`;

function dash(){
  const S=db.students,paid=S.filter(s=>s.paid),pending=S.length-paid.length;
  const got=paid.reduce((a,s)=>a+s.fee,0),due=S.filter(s=>!s.paid).reduce((a,s)=>a+s.fee,0);
  const pct=S.length?Math.round(paid.length/S.length*100):0;
  const pay=db.teachers.reduce((a,t)=>a+t.salary,0);
  const mx=Math.max(1,...db.classes.map(c=>S.filter(s=>s.cid==c.id).length));
  return head('Welcome back 👋','Here is how your college looks today.')+
  `<div class="grid g4">${stat('🧑‍🎓',S.length,'Students')+stat('👨‍🏫',db.teachers.length,'Teachers')+stat('📖',db.subjects.length,'Subjects')+stat('💼',rs(pay),'Total teacher salaries')}</div>
  <div class="grid g2" style="margin-top:16px">
   <div class="card"><h3 style="margin-bottom:16px">Fee collection</h3><div class="row">
    <div class="ring" style="background:conic-gradient(var(--teal) ${pct*3.6}deg,#fde8e1 0)"><div><span>${pct}%<small>paid</small></span></div></div>
    <div><p><span class="pill ok">${paid.length} paid</span> &nbsp;<span class="pill no">${pending} pending</span></p>
    <p style="margin-top:10px">Collected: <b>${rs(got)}</b></p><p>Still due: <b>${rs(due)}</b></p>
    <button class="btn sm" style="margin-top:10px" data-go="fees">See pending fees</button></div></div></div>
   <div class="card"><h3 style="margin-bottom:12px">Students per class</h3>${db.classes.map(c=>{const n=S.filter(s=>s.cid==c.id).length;return `<div><b>${esc(c.name)}</b> <span style="color:var(--muted)">${full(c)?'– '+esc(full(c))+' · ':'– '}${n} students</span><div class="bar"><i style="width:${n/mx*100}%"></i></div></div>`}).join('')}</div>
  </div>`;
}

function filtered(){
  const q=F.q.toLowerCase();
  return db.students.filter(s=>(!q||(s.name+s.email+s.regno+s.phone).toLowerCase().includes(q))&&(!F.c||s.cid==F.c)&&(!F.s||(F.s=='paid')==s.paid));
}
const tools=addBtn=>`<div class="tools"><input id="q" type="search" placeholder="Search name, reg no, email or phone" value="${esc(F.q)}" aria-label="Search students">
  <select id="fc" aria-label="Class"><option value="">All classes</option>${db.classes.map(c=>`<option value="${c.id}" ${F.c==c.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select>
  <select id="fs" aria-label="Fee status"><option value="">All fee status</option><option value="paid" ${F.s=='paid'?'selected':''}>Paid</option><option value="pending" ${F.s=='pending'?'selected':''}>Pending</option></select>${addBtn}</div>`;
function rowsOf(list,fee){
  if(!list.length)return `<div class="empty">No students match. Try clearing the search or filters.</div>`;
  return `<div class="wrap"><table><thead><tr><th>Reg no</th><th>Student</th><th>Class</th>${fee?'<th>Fee</th><th>Status</th><th></th>':'<th>Phone</th><th>Fee</th>'}</tr></thead><tbody>${list.map(s=>`<tr class="click" data-open="${s.regno}"><td>${s.regno}</td><td><div class="row" style="gap:10px;flex-wrap:nowrap">${av(s.name)}<div><b>${esc(s.name)}</b><br><small style="color:var(--muted)">${esc(s.email)}</small></div></div></td><td>${esc(cls(s.cid).name)}</td>${fee?`<td>${rs(s.fee)}</td><td><span class="pill ${s.paid?'ok':'no'}">${s.paid?'Paid':'Pending'}</span></td><td><button class="btn sm ${s.paid?'ghost':''}" data-pay="${s.regno}">${s.paid?'Mark pending':'Mark paid'}</button></td>`:`<td>${esc(s.phone)}</td><td><span class="pill ${s.paid?'ok':'no'}">${s.paid?'Paid':'Pending'}</span></td>`}</tr>`).join('')}</tbody></table></div>`;
}
const students=()=>{const l=filtered();return head('Students',`${l.length} of ${db.students.length} students`,`<button class="btn ghost" data-act="csv">Download CSV</button><button class="btn" data-act="add">+ Add student</button>`)+tools('')+`<div id="list">${rowsOf(l,false)}</div>`};
const fees=()=>{const l=filtered();return head('Fees',`Pending in this list: <b>${rs(l.filter(s=>!s.paid).reduce((a,s)=>a+s.fee,0))}</b>`)+tools('')+`<div id="list">${rowsOf(l,true)}</div>`};
function teachers(){
  return head('Teachers',`${db.teachers.length} teachers`,`<button class="btn" data-act="addt">+ Add teacher</button>`)+`<div class="grid g2">${db.teachers.map(t=>{
    const ss=db.subjects.filter(s=>s.tid==t.id);
    return `<div class="card"><div class="row" style="gap:12px;flex-wrap:nowrap;justify-content:space-between"><div class="row" style="gap:12px;flex-wrap:nowrap">${av(t.name)}<div><h3 style="font-size:19px">${esc(t.name)}</h3><small style="color:var(--muted)">${esc(cap(t.gender))} · ${t.age} years</small><br><small style="color:var(--muted)">📞 ${esc(t.phone||'–')}</small></div></div><button class="btn ghost sm" data-edit="t:${t.id}">Edit</button></div>
    <p style="margin-top:14px">Salary: <b>${rs(t.salary)}</b> &nbsp;<button class="btn ghost sm" data-hist="${t.id}">Salary record</button></p>
    <p style="margin:10px 0 8px"><small style="color:var(--muted)">Teaches</small></p>${ss.map(s=>`<span class="chip">${esc(s.name)}</span>`).join('')||'–'}</div>`}).join('')}</div>`;
}
function subjects(){
  return head('Subjects',`${db.subjects.length} subjects`,`<button class="btn" data-act="addj">+ Add subject</button>`)+`<div class="wrap"><table><thead><tr><th>ID</th><th>Subject</th><th>Teacher</th><th>Classes</th><th></th></tr></thead><tbody>${db.subjects.map(s=>`<tr><td>${s.id}</td><td><b>${esc(s.name)}</b></td><td>${esc(tea(s.tid).name)}</td><td>${db.classes.filter(c=>c.subjects.includes(s.id)).map(c=>`<span class="chip">${esc(c.name)}</span>`).join('')||'–'}</td><td><button class="btn ghost sm" data-edit="j:${s.id}">Edit</button></td></tr>`).join('')}</tbody></table></div>`;
}
function classes(){
  return head('Classes',`Subjects each class studies, and who teaches them`,`<button class="btn" data-act="addc">+ New class</button>`)+`<div class="grid g2">${db.classes.map(c=>`<div class="card"><div class="row" style="justify-content:space-between;flex-wrap:nowrap"><div><h3>${esc(c.name)}</h3><p style="color:var(--muted);margin-bottom:12px">${full(c)?esc(full(c))+' · ':''}${db.students.filter(s=>s.cid==c.id).length} students</p></div><button class="btn ghost sm" data-edit="c:${c.id}">Edit</button></div>${c.subjects.map(id=>{const s=sub(id);return `<div class="row" style="justify-content:space-between;gap:8px;padding:7px 0;border-top:1px solid var(--line)"><b>${esc(s.name)}</b><span style="color:var(--muted)">${esc(tea(s.tid).name)}</span></div>`}).join('')}</div>`).join('')}</div>`;
}

function sal(){
  const R=SAL.rows,P=R.filter(r=>r.paid),tot=a=>a.reduce((x,r)=>x+r.amount,0);
  return head('Salaries','Monthly salary record for every teacher',`<input type="month" id="sm" value="${SM}" aria-label="Month" style="border:1px solid var(--line);border-radius:12px;padding:10px 14px;min-height:44px;background:#fff">`)+
  `<div class="grid g4" style="margin-bottom:16px">${stat('💼',rs(tot(R)),'Total for the month')+stat('✅',rs(tot(P)),P.length+' teachers paid')+stat('⏳',rs(tot(R)-tot(P)),(R.length-P.length)+' pending')}</div>
  <div class="wrap"><table><thead><tr><th>Teacher</th><th>Amount</th><th>Status</th><th>Paid on</th><th></th></tr></thead><tbody>${R.map(r=>`<tr class="click" data-hist="${r.tid}"><td><b>${esc(r.name)}</b>${r.note?`<br><small style="color:var(--muted)">${esc(r.note)}</small>`:''}</td><td>${rs(r.amount)}</td><td><span class="pill ${r.paid?'ok':'no'}">${r.paid?'Paid':'Pending'}</span></td><td>${r.paid_on||'–'}</td><td><div class="row" style="gap:6px;flex-wrap:nowrap"><button class="btn sm ${r.paid?'ghost':''}" data-spay="${r.tid}">${r.paid?'Undo':'Mark paid'}</button><button class="btn ghost sm" data-sedit="${r.tid}">Edit</button></div></td></tr>`).join('')}</tbody></table></div>`;
}
async function hist(tid){
  try{const h=await api('GET','/api/salaries/teacher/'+tid),t=tea(tid);
  $('#dlg').innerHTML=`<h2>${esc(t.name)}</h2><p style="color:var(--muted);margin-bottom:12px">Current salary: <b>${rs(t.salary)}</b> · salary record</p>${h.length?`<div class="wrap"><table style="min-width:0"><thead><tr><th>Month</th><th>Amount</th><th>Status</th></tr></thead><tbody>${h.map(x=>`<tr><td>${x.month}</td><td>${rs(x.amount)}</td><td><span class="pill ${x.paid?'ok':'no'}">${x.paid?'Paid '+(x.paid_on||''):'Pending'}</span></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No payments recorded yet. Use the Salaries page to mark a month as paid.</div>'}<div class="acts"><button class="btn" data-close>Close</button></div>`;
  $('#dlg').showModal()}catch(e){toast(e.message)}
}
function salForm(tid){
  const r=SAL.rows.find(x=>x.tid==tid);
  ask(`${esc(r.name)} – ${SM}`,[{k:'amount',l:'Amount for this month (Rs)',t:'number',a:'min=0 step=500'},{k:'paid',l:'Status',t:'select',b:1,o:[['false','Pending'],['true','Paid']]},{k:'note',l:'Note (optional, e.g. bonus or deduction)',t:'text',opt:1,a:'maxlength=100'}],
    {amount:r.amount,paid:String(r.paid),note:r.note},d=>api('PUT',`/api/salaries/${tid}/${SM}`,d));
}
function about(){
  return `<div class="about">${head('About','Everything you need to know about College Hub')}
  <div class="card"><h2>What is College Hub?</h2><p style="color:var(--muted);margin-top:8px">College Hub is a simple online panel where a college, school or academy manages its students, teachers, subjects, classes, fees and teacher salaries. Every college signs in with its own username and password and only sees its own data.</p></div>
  <div class="card" style="margin-top:16px"><h2>How to use it (follow this order)</h2>
    <ol>
      <li><b>Add Teachers first.</b> Open <i>Teachers</i> and add every teacher with name, age, gender, phone and salary.</li>
      <li><b>Then add Subjects.</b> Open <i>Subjects</i> and create each subject, choosing the teacher who teaches it.</li>
      <li><b>Then create Classes.</b> Open <i>Classes</i>, name the class and tick the subjects that belong to it.</li>
      <li><b>Finally add Students.</b> Open <i>Students</i>, add each student, pick their class and set the fee.</li>
      <li><b>Daily work:</b> use <i>Fees</i> to mark fees paid or pending and <i>Salaries</i> to record teacher salaries month by month.</li>
    </ol></div>
  <div class="card" style="margin-top:16px"><h2>Created by</h2><p style="margin-top:8px"><b>Muhammad Talha Ijaz</b><br><span style="color:var(--muted)">Email:</span> <a href="mailto:mtalhaijaz997@gmail.com">mtalhaijaz997@gmail.com</a></p></div>
  <div class="ft">Contact me to create websites like these for your own use and customize them: <a href="mailto:mtalhaijaz997@gmail.com">mtalhaijaz997@gmail.com</a></div></div>`;
}
function render(){
  if(!tok||!db)return loginView();
  $('#side').style.display='';
  document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('on',b.dataset.v==view));
  $('#view').innerHTML={dash,students,teachers,subjects,classes,fees,sal,about}[view]();
  window.scrollTo(0,0);
}
function refreshList(){
  const l=filtered();$('#list').innerHTML=rowsOf(l,view=='fees');const p=$('.top p');
  if(view=='students')p.textContent=`${l.length} of ${db.students.length} students`;
  else p.innerHTML=`Pending in this list: <b>${rs(l.filter(s=>!s.paid).reduce((a,s)=>a+s.fee,0))}</b>`;
}
