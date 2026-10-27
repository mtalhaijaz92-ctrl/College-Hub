/* app.js - Click / input events + app start (loaded LAST) */
document.addEventListener('click',async e=>{
  const t=e.target.closest('[data-v],[data-go],[data-open],[data-pay],[data-act],[data-edit],[data-close],[data-hist],[data-spay],[data-sedit]');if(!t)return;const d=t.dataset;
  if(d.v||d.go){view=d.v||d.go;F={q:'',c:'',s:d.go=='fees'?'pending':''};if(view=='sal'){try{await loadSal()}catch(x){return toast(x.message)}}render()}
  else if('open' in d)detail(d.open);
  else if('hist' in d)hist(d.hist);
  else if('sedit' in d)salForm(d.sedit);
  else if('spay' in d){const r=SAL.rows.find(x=>x.tid==d.spay);run(()=>api('PUT',`/api/salaries/${r.tid}/${SM}`,{amount:r.amount,paid:!r.paid,note:r.note||''}),r.paid?'Marked as pending':'Salary marked as paid',keep)}
  else if('pay' in d){const s=db.students.find(x=>x.regno==d.pay);run(()=>api('PUT','/api/students/'+s.regno,{...sv(s),paid:!s.paid}),s.paid?'Marked as pending':'Marked as paid',refreshList)}
  else if('edit' in d){$('#dlg').close();const[k,id]=d.edit.split(':');({s:stuForm,t:teaForm,j:subForm,c:editClass})[k](+id)}
  else if('close' in d)$('#dlg').close();
  else if(d.act)({add:()=>stuForm(),csv,out:logout,pw:()=>pwView(false),addt:()=>teaForm(),addj:()=>subForm(),addc:()=>editClass()})[d.act]();
});
document.addEventListener('input',e=>{if(e.target.id=='q'){F.q=e.target.value;refreshList()}});
document.addEventListener('change',e=>{if(e.target.id=='sm'&&e.target.value){SM=e.target.value;loadSal().then(render).catch(x=>toast(x.message))}if(e.target.id=='fc'){F.c=e.target.value;refreshList()}if(e.target.id=='fs'){F.s=e.target.value;refreshList()}});
$('#dlg').addEventListener('click',e=>{if(e.target.id=='dlg')e.target.close()});
start();
