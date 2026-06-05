/* ==========================================================
   ZENITH OX v4.0 -- Chat UI
   Features: Typewriter, Multi-file, Voice, Dark Mode, Export,
   Regenerate, Edit, Charts, Memory Sidebar
   ========================================================== */
(() => {
  const chatBox     = document.getElementById("chat-box");
  const form        = document.getElementById("chatForm");
  const input       = document.getElementById("user-input");
  const sendBtn     = document.getElementById("sendBtn");
  const clearBtn    = document.getElementById("clearBtn");
  const logoutBtn   = document.getElementById("logoutBtn");
  const micBtn      = document.getElementById("micBtn");
  const darkModeBtn = document.getElementById("darkModeBtn");
  const exportBtn   = document.getElementById("exportBtn");
  const exportDropdown = document.getElementById("exportDropdown");
  const regenerateBtn  = document.getElementById("regenerateBtn");
  const fileInput   = document.getElementById("fileInput");
  const fileBtn     = document.getElementById("fileBtn");
  const filePreview = document.getElementById("file-preview");
  const fileCount   = document.getElementById("fileCount");
  const moonIcon    = document.getElementById("moonIcon");
  const sunIcon     = document.getElementById("sunIcon");
  const hljsTheme   = document.getElementById("hljs-theme");
  const toastContainer = document.getElementById("toastContainer");

  /* -- marked.js config -- */
  const renderer = new marked.Renderer();
  const FILE_RE  = new RegExp("^(?:#|//|<!--|/\\*)\\s*File:\\s*(.+?)(?:\\s*-->|\\s*\\*/)?\\s*$", "i");

  renderer.code = function({ text, lang }) {
    const code=text||"", language=lang||"plaintext";
    let filename=null, cleanCode=code;
    const lines=code.split("\n");
    if(lines.length>0){const m=lines[0].trim().match(FILE_RE);if(m){filename=m[1].trim();cleanCode=lines.slice(1).join("\n").trim();}}
    let hl;
    try{hl=hljs.getLanguage(language)?hljs.highlight(cleanCode,{language}).value:hljs.highlightAuto(cleanCode).value;}
    catch(e){hl=cleanCode.replace(/</g,"&lt;").replace(/>/g,"&gt;");}
    const label=filename?"<strong>"+filename+"</strong>":language;
    return'<div class="code-block-wrapper"><div class="code-header"><span class="code-lang">'+label+
      '</span><button class="copy-btn" onclick="copyCode(this)" data-code="'+
      btoa(unescape(encodeURIComponent(cleanCode)))+'">Copy</button></div>'+
      '<pre><code class="hljs language-'+language+'">'+hl+'</code></pre></div>';
  };
  marked.setOptions({renderer,breaks:true,gfm:true});

  window.copyCode=function(btn){
    const code=decodeURIComponent(escape(atob(btn.dataset.code)));
    navigator.clipboard.writeText(code).then(()=>{btn.textContent="Copied!";setTimeout(()=>{btn.textContent="Copy";},2000);});
  };

  /* -- textarea auto-resize -- */
  input.addEventListener("input",()=>{input.style.height="auto";input.style.height=Math.min(input.scrollHeight,150)+"px";});
  input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();form.dispatchEvent(new Event("submit"));}});

  /* -- Multi-file upload -- */
  let pendingFiles=[];
  fileBtn.addEventListener("click",()=>fileInput.click());
  fileInput.addEventListener("change",()=>{
    const files=Array.from(fileInput.files);
    if(!files.length)return;
    pendingFiles=files;
    renderFilePreview();
  });

  function renderFilePreview(){
    if(!pendingFiles.length){filePreview.classList.add("hidden");fileCount.textContent="";return;}
    filePreview.classList.remove("hidden");
    filePreview.innerHTML=pendingFiles.map((f,i)=>
      '<span class="file-tag">📎 '+esc(f.name)+' ('+(f.size/1024).toFixed(1)+' KB)'+
      '<button type="button" data-index="'+i+'" title="Remove">&times;</button></span>'
    ).join("");
    fileCount.textContent=pendingFiles.length+" file"+(pendingFiles.length>1?"s":"")+" selected";
    filePreview.querySelectorAll("button").forEach(btn=>{
      btn.addEventListener("click",()=>{
        const idx=parseInt(btn.dataset.index);
        pendingFiles.splice(idx,1);
        renderFilePreview();
      });
    });
  }

  /* -- helpers -- */
  function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}

  function addMessage(text,cls){
    const d=document.createElement("div");d.className="message "+(cls||"bot");
    if(cls&&cls.includes("user"))d.textContent=text;
    else d.innerHTML=text;
    chatBox.appendChild(d);chatBox.scrollTop=chatBox.scrollHeight;return d;
  }

  function addFileIndicator(filename){
    const d=document.createElement("div");d.className="message user file-indicator";
    d.innerHTML='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-3px"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg> '+esc(filename);
    chatBox.appendChild(d);chatBox.scrollTop=chatBox.scrollHeight;
  }

  function addTyping(){
    const d=document.createElement("div");d.className="message bot";
    d.innerHTML='<span class="typing"><span></span><span></span><span></span></span>';
    chatBox.appendChild(d);chatBox.scrollTop=chatBox.scrollHeight;return d;
  }

  function renderMath(el){
    if(window.renderMathInElement)renderMathInElement(el,{delimiters:[{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false},{left:"\\(",right:"\\)",display:false},{left:"\\[",right:"\\]",display:true}],throwOnError:false});
  }

  function addCopyBtn(wrapper,txt){
    const btn=document.createElement("button");btn.className="msg-copy-btn";btn.title="Copy response";
    btn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
    btn.addEventListener("click",()=>{
      navigator.clipboard.writeText(txt).then(()=>{
        btn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>';
        setTimeout(()=>{btn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';},2000);
      });
    });
    wrapper.appendChild(btn);
  }

  /* -- Message action buttons (regenerate, edit) -- */
  function addMsgActions(wrapper, userText, botText){
    const actions=document.createElement("div");actions.className="msg-actions";

    // Regenerate button
    const regenBtn=document.createElement("button");regenBtn.className="msg-action-btn";
    regenBtn.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg> Regenerate';
    regenBtn.addEventListener("click",()=>{doRegenerate();});
    actions.appendChild(regenBtn);

    // Edit button
    const editBtn=document.createElement("button");editBtn.className="msg-action-btn";
    editBtn.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit';
    editBtn.addEventListener("click",()=>{enableEdit(wrapper,userText||botText);});
    actions.appendChild(editBtn);

    wrapper.appendChild(actions);
  }

  function enableEdit(wrapper, currentText){
    const content=wrapper.querySelector(".md-content");
    if(!content)return;
    const ta=document.createElement("textarea");ta.className="edit-textarea";
    ta.value=currentText;content.innerHTML="";content.appendChild(ta);
    const btnRow=document.createElement("div");btnRow.className="edit-actions";
    const saveBtn=document.createElement("button");saveBtn.className="edit-save-btn";saveBtn.textContent="Save";
    const cancelBtn=document.createElement("button");cancelBtn.className="edit-cancel-btn";cancelBtn.textContent="Cancel";
    btnRow.appendChild(saveBtn);btnRow.appendChild(cancelBtn);content.appendChild(btnRow);
    ta.focus();
    saveBtn.addEventListener("click",()=>{
      const newText=ta.value.trim();
      content.innerHTML=marked.parse(newText);renderMath(content);
      addCopyBtn(wrapper,newText);
    });
    cancelBtn.addEventListener("click",()=>{
      content.innerHTML=marked.parse(currentText);renderMath(content);
      addCopyBtn(wrapper,currentText);
    });
  }

  /* -- TYPEWRITER animation -- */
  function typewriterRender(txt,dlUrl,dlName){
    const wrapper=document.createElement("div");wrapper.className="message bot";
    const content=document.createElement("div");content.className="md-content";
    wrapper.appendChild(content);chatBox.appendChild(wrapper);chatBox.scrollTop=chatBox.scrollHeight;
    const words=txt.split(" ");let i=0;const buf=[];
    const tick=setInterval(()=>{
      if(i>=words.length){
        clearInterval(tick);
        content.innerHTML=marked.parse(txt);renderMath(content);
        if(dlUrl){const a=document.createElement("a");a.href=dlUrl;a.download=dlName||"download";a.className="download-btn";a.textContent="📥 Download "+(dlName||"file");wrapper.appendChild(a);}
        addCopyBtn(wrapper,txt);addMsgActions(wrapper,null,txt);chatBox.scrollTop=chatBox.scrollHeight;return;
      }
      const batch=Math.min(4,words.length-i);
      for(let b=0;b<batch;b++)buf.push(words[i+b]);
      i+=batch;content.textContent=buf.join(" ");chatBox.scrollTop=chatBox.scrollHeight;
    },22);
  }

  /* -- Static render for history load -- */
  function renderBotMessage(txt,dlUrl,dlName){
    const wrapper=document.createElement("div");wrapper.className="message bot";
    const content=document.createElement("div");content.className="md-content";
    content.innerHTML=marked.parse(txt);renderMath(content);wrapper.appendChild(content);
    if(dlUrl){const a=document.createElement("a");a.href=dlUrl;a.download=dlName||"download";a.className="download-btn";a.textContent="📥 Download "+(dlName||"file");wrapper.appendChild(a);}
    addCopyBtn(wrapper,txt);addMsgActions(wrapper,null,txt);chatBox.appendChild(wrapper);chatBox.scrollTop=chatBox.scrollHeight;
  }

  /* -- Global appendChatMessage -- */
  window.appendChatMessage=function(role,content){
    if(role==="user"){
      if(content.startsWith("[Uploaded:")){
        const fm=content.match(/\[Uploaded: (.+?)\]\s*(.*)/);
        if(fm){addFileIndicator(fm[1]);if(fm[2])addMessage(fm[2],"user");}else addMessage(content,"user");
      }else addMessage(content,"user");
    }else renderBotMessage(content);
  };

  /* -- Load history on page load -- */
  async function loadHistory(){
    try{
      const r=await fetch("/history"),data=await r.json();
      if(data.ok&&data.messages&&data.messages.length>0){
        const welcome=chatBox.querySelector(".welcome");if(welcome)welcome.remove();
        for(const msg of data.messages)window.appendChatMessage(msg.role,msg.content);
      }
    }catch(e){}
  }
  loadHistory();

  /* -- Send message -- */
  async function sendMessage(message){
    if(pendingFiles.length)pendingFiles.forEach(f=>addFileIndicator(f.name));
    if(message)addMessage(message,"user");
    const typingEl=addTyping();sendBtn.disabled=true;
    try{
      let r;
      if(pendingFiles.length){
        const fd=new FormData();
        pendingFiles.forEach(f=>fd.append("files",f));
        fd.append("message",message||"Please analyze these files");
        r=await fetch("/chat",{method:"POST",body:fd});
        pendingFiles=[];fileInput.value="";renderFilePreview();
      }else{
        r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})});
      }
      const data=await r.json();typingEl.remove();
      if(!data.ok){addMessage("⚠ "+(data.error||"Unknown error"),"bot error");return;}
      typewriterRender(data.response,data.download_url,data.download_name);
      if(typeof ChatHistory!=="undefined"){
        if(message)ChatHistory.appendMessage("user",message);
        ChatHistory.appendMessage("assistant",data.response);
      }
      window.dispatchEvent(new Event("zenith:message-sent"));
    }catch(err){typingEl.remove();addMessage("⚠ Connection error: "+err.message,"bot error");}
    finally{sendBtn.disabled=false;input.focus();}
  }

  form.addEventListener("submit",e=>{
    e.preventDefault();const msg=input.value.trim();
    if(!msg&&!pendingFiles.length)return;
    input.value="";input.style.height="auto";sendMessage(msg);
  });

  clearBtn&&clearBtn.addEventListener("click",async()=>{
    if(!confirm("Clear all chat memory for this mode?"))return;
    try{
      const r=await fetch("/clear",{method:"POST"}),data=await r.json();
      if(data.ok){
        chatBox.innerHTML="";addMessage("Memory cleared. Starting fresh.","bot welcome");
        if(typeof ChatHistory!=="undefined")ChatHistory.startNewChat(window.ZENITH_MODE);
      }
    }catch(err){addMessage("⚠ Could not clear: "+err.message,"bot error");}
  });

  logoutBtn&&logoutBtn.addEventListener("click",()=>{window.location.href="/logout";});

  /* -- Regenerate -- */
  async function doRegenerate(){
    const typingEl=addTyping();if(regenerateBtn)regenerateBtn.disabled=true;
    try{
      const r=await fetch("/regenerate",{method:"POST"});
      const data=await r.json();typingEl.remove();
      if(!data.ok){addMessage("⚠ "+(data.error||"Regeneration failed"),"bot error");return;}
      typewriterRender(data.response);
      if(typeof ChatHistory!=="undefined")ChatHistory.appendMessage("assistant",data.response);
    }catch(err){typingEl.remove();addMessage("⚠ Regeneration error: "+err.message,"bot error");}
    finally{if(regenerateBtn)regenerateBtn.disabled=false;}
  }
  regenerateBtn&&regenerateBtn.addEventListener("click",doRegenerate);

  /* -- Dark mode toggle -- */
  const THEME_KEY="zenith_dark_mode";
  function loadTheme(){
    const saved=localStorage.getItem(THEME_KEY);
    const prefersDark=window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark=saved!==null?saved==="true":prefersDark;
    setTheme(isDark);
  }
  function setTheme(isDark){
    document.documentElement.setAttribute("data-theme",isDark?"dark":"light");
    if(hljsTheme)hljsTheme.href=isDark
      ?"https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css"
      :"https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
    if(moonIcon&&sunIcon){moonIcon.style.display=isDark?"none":"block";sunIcon.style.display=isDark?"block":"none";}
    localStorage.setItem(THEME_KEY,isDark?"true":"false");
  }
  darkModeBtn&&darkModeBtn.addEventListener("click",()=>{
    const current=document.documentElement.getAttribute("data-theme")==="dark";
    setTheme(!current);
  });
  loadTheme();

  /* -- Voice input (Web Speech API) -- */
  let recognition=null;
  if("webkitSpeechRecognition" in window||"SpeechRecognition" in window){
    const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    recognition=new SpeechRecognition();
    recognition.continuous=false;
    recognition.interimResults=false;
    recognition.lang="en-US";

    recognition.onresult=(e)=>{
      const transcript=e.results[0][0].transcript;
      input.value=(input.value?input.value+" ":"")+transcript;
      input.style.height="auto";input.style.height=Math.min(input.scrollHeight,150)+"px";
      micBtn.classList.remove("voice-recording","active");
      showToast("Voice captured","info");
    };
    recognition.onerror=(e)=>{
      micBtn.classList.remove("voice-recording","active");
      showToast("Voice error: "+e.error,"error");
    };
    recognition.onend=()=>{micBtn.classList.remove("voice-recording","active");};

    micBtn.addEventListener("click",()=>{
      if(micBtn.classList.contains("voice-recording")){recognition.stop();return;}
      micBtn.classList.add("voice-recording","active");
      try{recognition.start();}catch(e){showToast("Could not start voice input","error");micBtn.classList.remove("voice-recording","active");}
    });
  }else{
    micBtn.style.display="none";
  }

  /* -- Export chat -- */
  exportBtn&&exportBtn.addEventListener("click",(e)=>{
    e.stopPropagation();
    exportDropdown.classList.toggle("show");
  });
  document.addEventListener("click",()=>{exportDropdown.classList.remove("show");});
  exportDropdown&&exportDropdown.querySelectorAll("button").forEach(btn=>{
    btn.addEventListener("click",async()=>{
      const fmt=btn.dataset.format;
      const messages=collectMessages();
      if(!messages.length){showToast("No messages to export","error");return;}
      try{
        const r=await fetch("/export-chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({format:fmt,mode:window.ZENITH_MODE,messages})});
        const data=await r.json();
        if(data.ok){window.location.href=data.url;showToast("Chat exported!","success");}
        else showToast(data.error||"Export failed","error");
      }catch(err){showToast("Export error: "+err.message,"error");}
    });
  });

  function collectMessages(){
    const msgs=[];
    chatBox.querySelectorAll(".message").forEach(m=>{
      if(m.classList.contains("welcome")||m.classList.contains("error")||m.classList.contains("file-indicator"))return;
      const isUser=m.classList.contains("user");
      const content=m.querySelector(".md-content");
      const text=content?content.textContent:m.textContent;
      msgs.push({role:isUser?"user":"assistant",content:text.trim()});
    });
    return msgs;
  }

  /* -- Toast notifications -- */
  function showToast(message,type="info"){
    const toast=document.createElement("div");toast.className="toast "+type;toast.textContent=message;
    toastContainer.appendChild(toast);
    setTimeout(()=>{toast.remove();},3000);
  }
  window.showToast=showToast;

  /* -- Code project upload -- */
  const codeInput=document.getElementById("codeInput");
  const uploadCodeBtn=document.getElementById("uploadCodeBtn");
  uploadCodeBtn&&uploadCodeBtn.addEventListener("click",()=>codeInput&&codeInput.click());
  codeInput&&codeInput.addEventListener("change",async()=>{
    const file=codeInput.files[0];if(!file)return;
    const fd=new FormData();fd.append("file",file);fd.append("message","Analyze and improve this code project");
    addFileIndicator(file.name);const typingEl=addTyping();
    try{
      const r=await fetch("/upload-code",{method:"POST",body:fd});
      const data=await r.json();typingEl.remove();
      if(!data.ok){addMessage("⚠ "+(data.error||"Upload failed"),"bot error");return;}
      typewriterRender(data.response,data.download_url,data.download_name);
    }catch(err){typingEl.remove();addMessage("⚠ Upload error: "+err.message,"bot error");}
    codeInput.value="";
  });

  input.focus();
})();

/* ==========================================================
   MEMORY SIDEBAR
   ========================================================== */
(()=>{
  const sidebar=document.getElementById("memorySidebar");
  const overlay=document.getElementById("sidebarOverlay");
  const memoryBtn=document.getElementById("memoryBtn");
  const closeBtn=document.getElementById("sidebarClose");
  const body=document.getElementById("sidebarBody");
  const emptyMsg=document.getElementById("sidebarEmpty");
  const AI_MODES={researcher:{name:"Researcher",emoji:"🔍"},developer:{name:"Developer",emoji:"💻"},story_writer:{name:"Story Writer",emoji:"📖"},solve_it:{name:"Solve It",emoji:"🧮"},email_writer:{name:"Email Writer",emoji:"✉️"},pptx_generator:{name:"Slides",emoji:"📊"}};
  let loaded=false;

  function open(){sidebar.classList.add("open");overlay.classList.add("active");document.body.classList.add("sidebar-open");if(!loaded){load();loaded=true;}}
  function close(){sidebar.classList.remove("open");overlay.classList.remove("active");document.body.classList.remove("sidebar-open");}

  if(memoryBtn)memoryBtn.addEventListener("click",open);
  if(closeBtn)closeBtn.addEventListener("click",close);
  if(overlay)overlay.addEventListener("click",close);

  async function load(){
    try{
      const res=await fetch("/memory-sidebar"),data=await res.json();
      if(!data.ok)return;
      const modes=data.modes||{};let total=0;
      Object.values(modes).forEach(a=>{total+=a.length;});
      if(total===0){emptyMsg&&(emptyMsg.style.display="block");return;}
      if(emptyMsg)emptyMsg.style.display="none";
      Object.entries(modes).forEach(([key,exchanges])=>{
        if(!exchanges||!exchanges.length)return;
        const meta=AI_MODES[key]||{name:key,emoji:"🤖"};
        const sec=document.createElement("div");sec.className="sidebar-mode-section";
        const lbl=document.createElement("div");lbl.className="sidebar-mode-label";
        lbl.innerHTML="<span>"+meta.emoji+"</span> "+meta.name;sec.appendChild(lbl);
        exchanges.forEach(ex=>{
          const item=document.createElement("div");item.className="sidebar-chat-item";
          item.innerHTML="<div class=\"sidebar-chat-user\">👤 "+esc(ex.user)+"</div>"+(ex.assistant?"<div class=\"sidebar-chat-bot\">🤖 "+esc(ex.assistant)+(ex.assistant.length>=160?"…":"")+"</div>":"");
          sec.appendChild(item);
        });
        body.appendChild(sec);
      });
    }catch(e){console.warn("Memory sidebar:",e);}
  }

  function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}

  window.addEventListener("zenith:message-sent",()=>{
    loaded=false;
    if(sidebar.classList.contains("open")){body.innerHTML="";if(emptyMsg){emptyMsg.style.display="block";body.appendChild(emptyMsg);}load();loaded=true;}
  });
})();

/* ==========================================================
   MOBILE SIDEBAR TOGGLE
   ========================================================== */
(()=>{
  const sidebar=document.getElementById("zh-sidebar");
  const backdrop=document.getElementById("zh-backdrop");
  const toggle=document.getElementById("zh-sidebar-toggle");
  if(!sidebar||!toggle)return;
  function openSidebar(){sidebar.classList.add("zh-open");toggle.setAttribute("aria-expanded","true");backdrop.style.display="block";}
  function closeSidebar(){sidebar.classList.remove("zh-open");toggle.setAttribute("aria-expanded","false");backdrop.style.display="none";}
  toggle.addEventListener("click",()=>sidebar.classList.contains("zh-open")?closeSidebar():openSidebar());
  backdrop.addEventListener("click",closeSidebar);
})();
