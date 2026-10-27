/* auth.js - Login / Register / Change-password screens */
async function loginView(mode='in'){
  $('#side').style.display='none';
  $('#view').innerHTML='<div class="empty">Loading…</div>';
  let st={};try{st=await api('GET','/api/status')}catch(e){toast(e.message)}
  const reg=mode=='reg';
  $('#view').innerHTML=`<div class="card" style="max-width:400px;margin:8vh auto"><h1 style="font-size:28px">College Hub</h1><p style="color:var(--muted);margin:6px 0 16px">${reg?'Register your college or school. You will get your own private login and data.':'Sign in to manage your students, teachers, salaries and fees.'}</p>
  <form id="lf" class="grid" style="gap:12px">${reg?'<label>College / school name<input name="n" minlength="2" maxlength="80" required></label>':''}<label>Username<input name="u" autocomplete="username" minlength="${reg?3:1}" maxlength="40" required></label><label>Password${reg?' (at least 8 characters)':''}<input name="p" type="password" autocomplete="${reg?'new-password':'current-password'}" minlength="${reg?8:1}" required></label>${reg&&st.code_required?'<label>Signup code<input name="c" required></label>':''}<button class="btn">${reg?'Create account':'Sign in'}</button></form>
  <p style="margin-top:14px;text-align:center"><a href="#" id="sw" style="color:var(--muted)">${reg?'Already registered? Sign in':'New college or school? Register here'}</a></p></div>`;
  $('#sw').onclick=e=>{e.preventDefault();loginView(reg?'in':'reg')};
  $('#lf').onsubmit=async e=>{e.preventDefault();const d=new FormData(e.target);
    try{const r=reg?await api('POST','/api/register',{college:d.get('n'),username:d.get('u'),password:d.get('p'),code:d.get('c')||''}):await api('POST','/api/login',{username:d.get('u'),password:d.get('p')});
      tok=r.token;ME=r.username;sessionStorage.setItem('chtok',tok);sessionStorage.setItem('chme',ME);r.must_change?pwView(true):await start()}catch(x){toast(x.message)}};
}
function pwView(forced){
  $('#side').style.display='none';
  $('#view').innerHTML=`<div class="card" style="max-width:420px;margin:8vh auto"><h1 style="font-size:26px">${forced?'Set your own password':'Change password'}</h1><p style="color:var(--muted);margin:6px 0 16px">${forced?'Please choose your own username and password to continue.':'Update your admin username or password.'}</p>
  <form id="pf" class="grid" style="gap:12px"><label>Current password<input name="c" type="password" autocomplete="current-password" required></label><label>Username<input name="u" minlength="3" maxlength="40" required value="${esc(ME)}"></label><label>New password (at least 8 characters)<input name="p" type="password" minlength="8" autocomplete="new-password" required></label><label>Repeat new password<input name="r" type="password" minlength="8" autocomplete="new-password" required></label>
  <div class="acts">${forced?'<button type="button" class="btn ghost" data-act="out">Log out</button>':`<button type="button" class="btn ghost" data-v="${view}">Cancel</button>`}<button class="btn">Save password</button></div></form></div>`;
  $('#pf').onsubmit=async e=>{e.preventDefault();const d=new FormData(e.target);
    if(d.get('p')!=d.get('r'))return toast('The two new passwords do not match');
    try{const r=await api('POST','/api/change-password',{current:d.get('c'),username:d.get('u'),password:d.get('p')});tok=r.token;ME=r.username;sessionStorage.setItem('chtok',tok);sessionStorage.setItem('chme',ME);await start();toast('Password changed')}catch(x){toast(x.message)}};
}
