/* config.js - API address + global variables (state) */
const API_URL='https://college-hub-sn4f.vercel.app'; // after deploying the backend, replace with your live API address
const $=s=>document.querySelector(s);
let db=null,tok=sessionStorage.getItem('chtok'),view='dash',F={q:'',c:'',s:''};
let SAL=null,SM=new Date().toISOString().slice(0,7),ME=sessionStorage.getItem('chme')||'admin';
