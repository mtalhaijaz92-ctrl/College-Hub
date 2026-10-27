/* helpers.js - Small helper functions (format money, escape text, toast...) */
const FULL={FA:'Faculty of Arts',FSC:'Faculty of Science',ICOM:'Intermediate in Commerce',ICS:'Intermediate in Computer Science'};
const cls=id=>db.classes.find(c=>c.id==id)||{name:'?',subjects:[]};
const sub=id=>db.subjects.find(s=>s.id==id)||{name:'?'};
const tea=id=>db.teachers.find(t=>t.id==id)||{name:'?'};
const full=c=>FULL[c.name]||'';
const cap=g=>g?g[0].toUpperCase()+g.slice(1).toLowerCase():'Male';
const rs=n=>'Rs '+Number(n).toLocaleString('en-PK');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const COL=['#3a6ff7','#0f9d8a','#e4572e','#8a4fff','#f4a300','#d6336c'];
const av=n=>`<span class="av" style="background:${COL[n.charCodeAt(0)%COL.length]}">${esc(n[0])}</span>`;
const toast=m=>{const t=$('#toast');t.textContent=m;t.classList.add('show');clearTimeout(t._x);t._x=setTimeout(()=>t.classList.remove('show'),3200)};
const sv=s=>({name:s.name,email:s.email,gender:s.gender,phone:s.phone,age:s.age,cid:s.cid,fee:s.fee,paid:s.paid});
