/* api.js - Talking to the backend (fetch), reload data, logout, start */
async function api(m,p,b){
  let r;
  try{r=await fetch(API_URL+p,{method:m,headers:{'Content-Type':'application/json',...(tok?{Authorization:'Bearer '+tok}:{})},body:b?JSON.stringify(b):undefined})}
  catch(e){throw Error('Cannot reach the server. Check API_URL and that the backend is running.')}
  const j=await r.json().catch(()=>({}));
  if(r.status==401&&p!='/api/login'){logout();throw Error('Session expired. Please sign in again.')}
  if(!r.ok){const er=Error(typeof j.detail=='string'?j.detail:'Some values are invalid. Please check the form.');er.status=r.status;throw er}
  return j;
}
const loadSal=async()=>{SAL={month:SM,rows:await api('GET','/api/salaries/'+SM)}};
const reload=async()=>{db=await api('GET','/api/data');if(view=='sal')await loadSal()};
const keep=()=>{const y=scrollY;render();scrollTo(0,y)};
async function run(fn,msg,after=render){try{await fn();await reload();after();toast(msg)}catch(e){toast(e.message)}}
function logout(){tok=null;db=null;sessionStorage.removeItem('chtok');render()}
async function start(){
  if(!tok)return render();
  try{await reload();const bn=document.querySelector('.brand');if(bn)bn.innerHTML='<i>🎓</i>'+esc(db.college||'College Hub');render()}catch(e){if(!tok)return;if(e.status==403)return pwView(true);$('#side').style.display='none';$('#view').innerHTML=`<div class="empty">${esc(e.message)}<br><button class="btn" style="margin-top:12px" onclick="start()">Try again</button></div>`}
}
