/* ==========================================================
   ZENITH OX v4.0 -- Chat History Sidebar
   Features: Search, Pin, Restore-on-load, Inline Rename
   ========================================================== */
const CHAT_HISTORY_CONFIG={
  listEndpoint:"/api/chats",
  createEndpoint:"/api/chats/create",
  updateEndpoint:"/api/chats",
  deleteEndpoint:"/api/chats",
  loadEndpoint:"/api/chats",
  searchEndpoint:"/api/chats/search",
  pinEndpoint:"/api/chats",
  renameEndpoint:"/api/chats",
  restoreEndpoint:"/api/chats",
  autoSaveDelay:1500
};

const ChatHistory=(()=>{
  let _id=null,_msgs=[],_mode="researcher",_timer=null,_allChats=[];

  function _title(msgs){
    const u=msgs.find(m=>m.role==="user");
    if(!u)return"New chat";
    const r=u.content.trim().replace(/\s+/g," ");
    return r.length>48?r.slice(0,48)+"…":r;
  }

  function _group(chats){
    const now=new Date(),today=new Date(now.getFullYear(),now.getMonth(),now.getDate()),
          g={"Today":[],"Yesterday":[],"Previous 7 Days":[],"Older":[]};
    chats.forEach(ch=>{
      const d=new Date(ch.updated_at),day=new Date(d.getFullYear(),d.getMonth(),d.getDate()),
            diff=Math.floor((today-day)/86400000);
      if(diff===0)g["Today"].push(ch);
      else if(diff===1)g["Yesterday"].push(ch);
      else if(diff<=7)g["Previous 7 Days"].push(ch);
      else g["Older"].push(ch);
    });
    return g;
  }

  function _icon(mode){
    const m={"researcher":"🔍","developer":"💻","story_writer":"📖","story writer":"📖","solve_it":"🧮","email_writer":"✉️","pptx_generator":"📊"};
    return m[(mode||"").toLowerCase()]||"💬";
  }

  function _esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}

  function _ago(iso){
    const d=Date.now()-new Date(iso).getTime(),m=Math.floor(d/60000);
    if(m<1)return"just now";if(m<60)return m+"m ago";
    const h=Math.floor(m/60);if(h<24)return h+"h ago";
    return Math.floor(h/24)+"d ago";
  }

  /* -- Render sidebar with pin/rename support -- */
  async function renderSidebar(filteredChats){
    const container=document.getElementById("zh-chat-list");if(!container)return;

    // If filteredChats passed (from search), use those; otherwise use _allChats
    let chats=filteredChats||_allChats;

    if(!filteredChats){
      container.innerHTML='<div class="zh-loading">Loading chats…</div>';
      try{
        const res=await fetch(CHAT_HISTORY_CONFIG.listEndpoint),data=await res.json();
        _allChats=(data.chats||[]).sort((a,b)=>new Date(b.updated_at)-new Date(a.updated_at));
        chats=_allChats;
      }catch(err){console.error("renderSidebar:",err);container.innerHTML='<div class="zh-error">Could not load chats.</div>';return;}
    }

    if(!chats.length){
      container.innerHTML='<div class="zh-empty"><span class="zh-empty-icon">💬</span><p>No saved chats yet.<br>Start a conversation!</p></div>';
      return;
    }

    const g=_group(chats);let html="";
    for(const[lbl,items]of Object.entries(g)){
      if(!items.length)continue;
      html+='<div class="zh-date-label">'+lbl+"</div>";
      items.forEach(ch=>{
        const active=ch.id===_id?" zh-active":"";
        const pinnedClass=ch.pinned?" pinned":"";
        html+='<div class="zh-chat-item'+active+'" data-id="'+ch.id+'" role="button" tabindex="0">'+
          '<span class="zh-chat-icon">'+_icon(ch.mode)+'</span>'+
          '<div class="zh-chat-body"><div class="zh-chat-title">'+_esc(ch.title||"Untitled")+'</div>'+
          '<div class="zh-chat-meta">'+_esc(ch.mode||"")+' · '+_ago(ch.updated_at)+(ch.pinned?' 📌':'')+'</div></div>'+
          '<button class="zh-pin-btn'+pinnedClass+'" data-id="'+ch.id+'" title="'+(ch.pinned?"Unpin":"Pin")+'" aria-label="'+(ch.pinned?"Unpin":"Pin")+'">'+
          '📌</button>'+
          '<button class="zh-rename-btn" data-id="'+ch.id+'" title="Rename" aria-label="Rename">'+
          '✏️</button>'+
          '<button class="zh-delete-btn" data-id="'+ch.id+'" title="Delete" aria-label="Delete">'+
          '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg></button></div>';
      });
    }
    container.innerHTML=html;

    // Click handlers
    container.querySelectorAll(".zh-chat-item").forEach(el=>{
      el.addEventListener("click",e=>{if(e.target.closest(".zh-delete-btn")||e.target.closest(".zh-pin-btn")||e.target.closest(".zh-rename-btn"))return;loadChat(el.dataset.id);});
      el.addEventListener("keydown",e=>{if(e.key==="Enter"){if(e.target.closest(".zh-delete-btn")||e.target.closest(".zh-pin-btn")||e.target.closest(".zh-rename-btn"))return;loadChat(el.dataset.id);}});
    });
    container.querySelectorAll(".zh-delete-btn").forEach(btn=>{
      btn.addEventListener("click",e=>{e.stopPropagation();deleteChat(btn.dataset.id);});
    });
    container.querySelectorAll(".zh-pin-btn").forEach(btn=>{
      btn.addEventListener("click",e=>{e.stopPropagation();togglePin(btn.dataset.id);});
    });
    container.querySelectorAll(".zh-rename-btn").forEach(btn=>{
      btn.addEventListener("click",e=>{e.stopPropagation();startRename(btn.dataset.id);});
    });
  }

  /* -- Start inline rename -- */
  function startRename(chatId){
    const container=document.getElementById("zh-chat-list");if(!container)return;
    const item=container.querySelector('.zh-chat-item[data-id="'+chatId+'"]');if(!item)return;
    const titleEl=item.querySelector(".zh-chat-title");if(!titleEl)return;
    const currentTitle=titleEl.textContent;

    const inp=document.createElement("input");inp.type="text";inp.className="zh-rename-input";
    inp.value=currentTitle;
    titleEl.innerHTML="";titleEl.appendChild(inp);inp.focus();inp.select();

    function save(){const v=inp.value.trim();if(v&&v!==currentTitle){dbRename(chatId,v);}else{titleEl.textContent=currentTitle;}}
    function cancel(){titleEl.textContent=currentTitle;}

    inp.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();save();}else if(e.key==="Escape"){cancel();}});
    inp.addEventListener("blur",save);
  }

  async function dbRename(chatId,newTitle){
    try{
      const r=await fetch(CHAT_HISTORY_CONFIG.renameEndpoint+"/"+chatId+"/rename",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:newTitle})
      });
      const data=await r.json();
      if(data.ok){renderSidebar();if(window.showToast)window.showToast("Chat renamed","success");}
      else if(window.showToast)window.showToast(data.error||"Rename failed","error");
    }catch(err){console.error("renameChat:",err);if(window.showToast)window.showToast("Rename error","error");}
  }

  /* -- Toggle pin -- */
  async function togglePin(chatId){
    try{
      const r=await fetch(CHAT_HISTORY_CONFIG.pinEndpoint+"/"+chatId+"/pin",{method:"POST"});
      const data=await r.json();
      if(data.ok){renderSidebar();if(window.showToast)window.showToast(data.pinned?"Chat pinned":"Chat unpinned","success");}
    }catch(err){console.error("togglePin:",err);}
  }

  /* -- Search -- */
  async function searchChats(query){
    if(!query||query.length<2){renderSidebar();return;}
    try{
      const r=await fetch(CHAT_HISTORY_CONFIG.searchEndpoint+"?q="+encodeURIComponent(query));
      const data=await r.json();
      if(data.ok){renderSidebar(data.chats||[]);}
      else renderSidebar([]);
    }catch(err){console.error("searchChats:",err);renderSidebar([]);}
  }

  /* -- Debounced search input handler -- */
  let searchTimer=null;
  function initSearch(){
    const searchInput=document.getElementById("chatSearch");
    if(!searchInput)return;
    searchInput.addEventListener("input",()=>{
      clearTimeout(searchTimer);
      const q=searchInput.value.trim();
      if(!q){renderSidebar();return;}
      searchTimer=setTimeout(()=>searchChats(q),300);
    });
  }

  function startNewChat(mode){
    _id=null;_msgs=[];_mode=mode||_mode;
    const box=document.getElementById("chat-box")||document.getElementById("chat-messages")||document.getElementById("chatBox")||document.querySelector(".chat-messages");
    if(box)box.innerHTML='<div class="message bot welcome">New chat started. How can I help?</div>';
    const inp=document.getElementById("user-input")||document.getElementById("userInput")||document.querySelector("textarea[name=\'message\']");
    if(inp)inp.value="";
    document.querySelectorAll(".zh-chat-item").forEach(el=>el.classList.remove("zh-active"));
    console.log("[ChatHistory] New chat. Mode:",_mode);
  }

  function appendMessage(role,content){
    _msgs.push({role,content});
    clearTimeout(_timer);_timer=setTimeout(_save,CHAT_HISTORY_CONFIG.autoSaveDelay);
  }

  async function _save(){
    if(_msgs.length<2)return;
    const body={title:_title(_msgs),mode:_mode,messages:_msgs};
    try{
      if(!_id){
        const r=await fetch(CHAT_HISTORY_CONFIG.createEndpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
        const d=await r.json();_id=d.chat_id;console.log("[ChatHistory] Created:",_id);
      }else{
        await fetch(CHAT_HISTORY_CONFIG.updateEndpoint+"/"+_id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      }
      renderSidebar();
    }catch(err){console.error("[ChatHistory] Save failed:",err);}
  }

  async function loadChat(chatId){
    try{
      const r=await fetch(CHAT_HISTORY_CONFIG.loadEndpoint+"/"+chatId),data=await r.json();
      _id=chatId;_msgs=data.messages||[];_mode=data.mode||_mode;
      const box=document.getElementById("chat-box")||document.getElementById("chat-messages")||document.getElementById("chatBox")||document.querySelector(".chat-messages");
      if(box){
        box.innerHTML="";
        _msgs.forEach(msg=>{
          if(typeof window.appendChatMessage==="function")window.appendChatMessage(msg.role,msg.content);
          else{const d=document.createElement("div");d.className="message "+(msg.role==="user"?"user":"bot");d.textContent=msg.content;box.appendChild(d);}
        });
        box.scrollTop=box.scrollHeight;
      }
      document.querySelectorAll(".zh-chat-item").forEach(el=>el.classList.toggle("zh-active",el.dataset.id===chatId));
      console.log("[ChatHistory] Loaded:",chatId);
    }catch(err){console.error("[ChatHistory] loadChat failed:",err);}
  }

  async function deleteChat(chatId){
    if(!confirm("Delete this chat?"))return;
    try{
      await fetch(CHAT_HISTORY_CONFIG.deleteEndpoint+"/"+chatId,{method:"DELETE"});
      if(_id===chatId)startNewChat();
      renderSidebar();
    }catch(err){console.error("[ChatHistory] deleteChat failed:",err);}
  }

  /* -- Restore-on-load: load most recent chat if none active -- */
  async function restoreOnLoad(){
    if(_id)return; // Already have an active chat
    try{
      const res=await fetch(CHAT_HISTORY_CONFIG.listEndpoint),data=await res.json();
      const chats=(data.chats||[]).sort((a,b)=>new Date(b.updated_at)-new Date(a.updated_at));
      if(chats.length>0){
        // Load the most recent chat automatically
        await loadChat(chats[0].id);
      }
    }catch(err){console.log("[ChatHistory] No previous chat to restore");}
  }

  function init(){
    if(window.ZENITH_MODE)_mode=window.ZENITH_MODE;
    renderSidebar();
    initSearch();
    document.addEventListener("click",e=>{if(e.target.closest("#zh-new-chat-btn"))startNewChat(_mode);});
    // Restore last chat after a short delay
    setTimeout(restoreOnLoad,800);
  }

  document.addEventListener("DOMContentLoaded",init);
  return{startNewChat,appendMessage,loadChat,deleteChat,renderSidebar,searchChats};
})();
