/* forms.js - Add / Edit dialogs (student, teacher, subject, class), student detail, CSV */
/* one reusable edit/add dialog */
function ask(title,fs,v,save,del){
  $('#dlg').innerHTML=`<form id="f"><h2>${title}</h2>${fs.map(f=>`<label>${f.l}${f.t=='select'?`<select name="${f.k}">${f.o.map(([a,b])=>`<option value="${esc(a)}" ${a==v[f.k]?'selected':''}>${esc(b)}</option>`).join('')}</select>`:`<input name="${f.k}" type="${f.t}" ${f.opt?'':'required'} ${f.a||''} value="${esc(v[f.k]??'')}">`}</label>`).join('')}
  <div class="acts">${del?'<button type="button" class="btn red" id="rm">Delete</button>':''}<button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">Save changes</button></div></form>`;
  $('#dlg').showModal();
  $('#f').onsubmit=e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));
    fs.forEach(f=>{if(f.t=='number'||f.n)d[f.k]=+d[f.k];if(f.b)d[f.k]=d[f.k]=='true'});
    $('#dlg').close();run(()=>save(d),'Saved')};
  if(del)$('#rm').onclick=()=>{if(confirm('Delete permanently from the database?')){$('#dlg').close();run(del,'Deleted')}};
}
const GEN=[['Male','Male'],['Female','Female']];
function stuForm(no){
  const s=no?db.students.find(x=>x.regno==no):{name:'',email:'',gender:'Male',phone:'',age:18,cid:db.classes[0]?.id,fee:50000,paid:false};
  ask(no?'Edit student':'Add a new student',[
    {k:'name',l:'Full name',t:'text',a:'maxlength=35'},{k:'email',l:'Email',t:'email',a:'maxlength=60'},
    {k:'phone',l:'Phone (digits only)',t:'tel',a:'pattern="[0-9]{10,13}"'},{k:'gender',l:'Gender',t:'select',o:GEN},
    {k:'age',l:'Age',t:'number',a:'min=5 max=80'},{k:'cid',l:'Class',t:'select',n:1,o:db.classes.map(c=>[c.id,c.name])},
    {k:'fee',l:'Fee (Rs)',t:'number',a:'min=0 step=500'},{k:'paid',l:'Fee status',t:'select',b:1,o:[['false','Pending'],['true','Paid']]}],
    {...s,gender:cap(s.gender),paid:String(s.paid)},
    d=>no?api('PUT','/api/students/'+no,d):api('POST','/api/students',d),no&&(()=>api('DELETE','/api/students/'+no)));
}
function teaForm(id){
  const t=id?db.teachers.find(x=>x.id==id):{name:'',age:30,gender:'Male',phone:'',salary:50000};
  ask(id?'Edit teacher':'Add a teacher',[
    {k:'name',l:'Full name',t:'text',a:'maxlength=25'},{k:'age',l:'Age',t:'number',a:'min=18 max=80'},
    {k:'gender',l:'Gender',t:'select',o:GEN},
    {k:'phone',l:'Phone (digits only)',t:'tel',a:'pattern="[0-9]{10,13}"'},{k:'salary',l:'Salary (Rs)',t:'number',a:'min=0 step=500'}],
    {...t,gender:cap(t.gender)},d=>id?api('PUT','/api/teachers/'+id,d):api('POST','/api/teachers',d),id&&(()=>api('DELETE','/api/teachers/'+id)));
}
function subForm(id){
  const s=id?db.subjects.find(x=>x.id==id):{name:'',tid:db.teachers[0]?.id};
  ask(id?'Edit subject':'Add a subject',[
    {k:'name',l:'Subject name',t:'text',a:'maxlength=25'},{k:'tid',l:'Teacher',t:'select',n:1,o:db.teachers.map(t=>[t.id,t.name])}],
    s,d=>id?api('PUT','/api/subjects/'+id,d):api('POST','/api/subjects',d),id&&(()=>api('DELETE','/api/subjects/'+id)));
}
function editClass(id){
  const c=id?cls(id):{id:Math.max(50,...db.classes.map(x=>x.id))+1,name:'',subjects:[]};
  $('#dlg').innerHTML=`<form id="f"><h2>${id?'Edit class':'New class'}</h2><label>Class name<input name="name" required maxlength="10" value="${esc(c.name)}"></label><p><b>Subjects in this class</b></p>
  <div style="max-height:38vh;overflow:auto;display:grid;gap:6px">${db.subjects.map(s=>`<label style="display:flex;gap:10px;align-items:center;font-weight:400"><input type="checkbox" name="s" value="${s.id}" ${c.subjects.includes(s.id)?'checked':''} style="width:20px;height:20px;min-height:0"> ${esc(s.name)} <small style="color:var(--muted)">(${esc(tea(s.tid).name)})</small></label>`).join('')}</div>
  <div class="acts">${id?'<button type="button" class="btn red" id="rm">Delete class</button>':''}<button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">Save changes</button></div></form>`;
  $('#dlg').showModal();
  $('#f').onsubmit=e=>{e.preventDefault();const ids=[...e.target.querySelectorAll('[name=s]:checked')].map(x=>+x.value);
    if(!ids.length)return toast('Pick at least one subject');
    const name=e.target.name.value;$('#dlg').close();run(()=>api('PUT','/api/classes/'+c.id,{name,subjects:ids}),'Saved')};
  if(id)$('#rm').onclick=()=>{if(confirm('Delete this class?')){$('#dlg').close();run(()=>api('DELETE','/api/classes/'+id),'Deleted')}};
}
function detail(no){
  const s=db.students.find(x=>x.regno==no),c=cls(s.cid);
  $('#dlg').innerHTML=`<div class="row" style="gap:14px;flex-wrap:nowrap">${av(s.name)}<div><h2>${esc(s.name)}</h2><small style="color:var(--muted)">Reg no ${s.regno} · ${esc(c.name)} ${full(c)?'('+esc(full(c))+')':''}</small></div></div>
  <p style="margin-top:14px">📧 ${esc(s.email)}<br>📞 ${esc(s.phone)}<br>${esc(cap(s.gender))} · ${s.age} years<br>💳 ${rs(s.fee)} – <span class="pill ${s.paid?'ok':'no'}">${s.paid?'Paid':'Pending'}</span></p>
  <p style="margin:14px 0 6px"><b>Subjects</b></p>${c.subjects.map(id=>`<span class="chip">${esc(sub(id).name)}</span>`).join('')}
  <div class="acts"><button class="btn ghost" data-edit="s:${s.regno}">Edit / delete</button><button class="btn" data-close>Close</button></div>`;
  $('#dlg').showModal();
}
function csv(){
  const h=['Regno','Name','Email','Gender','Phone','Age','Class','Fee','Fee status'];
  const r=db.students.map(s=>[s.regno,s.name,s.email,s.gender,s.phone,s.age,cls(s.cid).name,s.fee,s.paid?'Paid':'Pending']);
  const t=[h,...r].map(x=>x.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/csv'}));a.download='students.csv';a.click();toast('students.csv downloaded');
}
