import re

files = [
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\fitness_coach.html"
]

SIDEBAR_HTML = """
<!-- Chat Sidebar for History -->
<div id="chatSidebar" class="absolute top-0 right-0 w-64 h-full bg-surface-container-high/95 backdrop-blur-xl border-l border-white/5 p-4 z-50 translate-x-full transition-transform duration-300 overflow-y-auto hidden flex-col gap-2">
    <div class="flex justify-between items-center mb-4">
        <h3 class="font-headline-md text-on-surface text-[18px]">Vecchie Chat</h3>
        <button onclick="toggleSidebar()" class="text-on-surface-variant hover:text-error"><span class="material-symbols-outlined">close</span></button>
    </div>
    <button onclick="startNewChat()" class="w-full bg-primary-container/20 text-primary-container border border-primary-container/30 py-2 rounded-lg mb-2 text-sm flex items-center justify-center gap-2 hover:bg-primary-container/30 transition-colors">
        <span class="material-symbols-outlined text-[18px]">add</span> Nuova Chat
    </button>
    <div id="sessionList" class="flex flex-col gap-2">
        <!-- Sessions loaded here -->
    </div>
</div>
"""

JS_CODE = """
    // Sidebar logic
    function toggleSidebar() {
        const sidebar = document.getElementById('chatSidebar');
        if (sidebar.classList.contains('hidden')) {
            sidebar.classList.remove('hidden');
            // small delay to allow display:block to apply before animation
            setTimeout(() => { sidebar.classList.remove('translate-x-full'); }, 10);
            loadSessions();
        } else {
            sidebar.classList.add('translate-x-full');
            setTimeout(() => { sidebar.classList.add('hidden'); }, 300);
        }
    }

    async function loadSessions() {
        const list = document.getElementById('sessionList');
        list.innerHTML = '<span class="text-on-surface-variant text-sm">Caricamento...</span>';
        try {
            const res = await fetch(`/api/chat/sessions?user_id=${userId}`);
            if (res.ok) {
                const data = await res.json();
                list.innerHTML = '';
                if(data.sessions.length === 0) {
                    list.innerHTML = '<span class="text-on-surface-variant text-sm">Nessuna chat passata.</span>';
                    return;
                }
                data.sessions.reverse().forEach(s => {
                    const div = document.createElement('div');
                    div.className = 'glass-panel p-2 rounded-lg flex flex-col gap-1 border border-white/5 hover:border-primary-container/30 cursor-pointer group relative';
                    
                    const titleDiv = document.createElement('div');
                    titleDiv.className = 'flex justify-between items-center';
                    
                    const titleSpan = document.createElement('span');
                    titleSpan.className = 'text-sm text-on-surface truncate pr-6';
                    titleSpan.innerText = s.title;
                    titleSpan.onclick = () => loadChat(s.id);
                    
                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'absolute right-2 top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity';
                    
                    const renameBtn = document.createElement('button');
                    renameBtn.innerHTML = '<span class="material-symbols-outlined text-[14px] text-tertiary-container hover:text-tertiary-fixed">edit</span>';
                    renameBtn.onclick = (e) => { e.stopPropagation(); renameSession(s.id, s.title); };
                    
                    const delBtn = document.createElement('button');
                    delBtn.innerHTML = '<span class="material-symbols-outlined text-[14px] text-error hover:text-error-container">delete</span>';
                    delBtn.onclick = (e) => { e.stopPropagation(); deleteSession(s.id); };
                    
                    actionsDiv.appendChild(renameBtn);
                    actionsDiv.appendChild(delBtn);
                    
                    titleDiv.appendChild(titleSpan);
                    titleDiv.appendChild(actionsDiv);
                    div.appendChild(titleDiv);
                    
                    const dateSpan = document.createElement('span');
                    dateSpan.className = 'text-[10px] text-on-surface-variant opacity-50';
                    dateSpan.innerText = new Date(s.created_at).toLocaleString();
                    div.appendChild(dateSpan);
                    
                    list.appendChild(div);
                });
            }
        } catch(e) {
            console.error(e);
            list.innerHTML = '<span class="text-error text-sm">Errore.</span>';
        }
    }

    async function loadChat(id) {
        try {
            const res = await fetch(`/api/chat/session/${id}`);
            if (res.ok) {
                const data = await res.json();
                currentConversationId = id;
                const historyContainer = document.getElementById('chatContainer') || document.getElementById('chatHistory');
                historyContainer.innerHTML = '';
                data.history.forEach(m => {
                    if(m.role === 'user') appendUserMessage(m.content);
                    else appendBotMessage(m.content);
                });
                toggleSidebar();
            }
        } catch(e) {
            console.error(e);
        }
    }

    async function deleteSession(id) {
        if(!confirm("Vuoi davvero eliminare questa chat?")) return;
        try {
            const res = await fetch(`/api/chat/session/${id}`, { method: 'DELETE' });
            if(res.ok) {
                if(currentConversationId === id) startNewChat();
                loadSessions();
            }
        } catch(e) { console.error(e); }
    }

    async function renameSession(id, oldTitle) {
        const newTitle = prompt("Nuovo titolo:", oldTitle);
        if(!newTitle || newTitle.trim() === "") return;
        try {
            const res = await fetch(`/api/chat/session/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title: newTitle})
            });
            if(res.ok) loadSessions();
        } catch(e) { console.error(e); }
    }

    function startNewChat() {
        currentConversationId = null;
        const historyContainer = document.getElementById('chatContainer') || document.getElementById('chatHistory');
        historyContainer.innerHTML = '';
        if(!document.getElementById('chatSidebar').classList.contains('hidden')) {
            toggleSidebar();
        }
    }
"""

for fp in files:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()

    # Clear initial chat history in nutritionist
    if "nutritionist.html" in fp:
        content = re.sub(
            r'<div id="chatContainer" class="flex-1 overflow-y-auto p-4 flex flex-col gap-6 hide-scrollbar relative">.*?<div class="p-4 bg-background/50',
            '<div id="chatContainer" class="flex-1 overflow-y-auto p-4 flex flex-col gap-6 hide-scrollbar relative"></div>\n<div class="p-4 bg-background/50',
            content, flags=re.DOTALL
        )
        # Add history button to header
        content = content.replace(
            '<p class="font-label-sm text-label-sm text-on-surface-variant">AI Nutritionist</p>\n</div>\n</div>',
            '<p class="font-label-sm text-label-sm text-on-surface-variant">AI Nutritionist</p>\n</div>\n</div>\n<button onclick="toggleSidebar()" class="ml-auto text-on-surface-variant hover:text-primary-fixed"><span class="material-symbols-outlined">history</span></button>\n</div>'
        )

    # In fitness_coach, we need to add the history button
    if "fitness_coach.html" in fp:
        content = content.replace(
            '<section class="glass-panel rounded-xl p-md flex flex-col gap-sm relative overflow-hidden">',
            '<section class="glass-panel rounded-xl p-md flex flex-col gap-sm relative overflow-hidden">\n<div class="flex justify-between items-center"><span class="text-on-surface font-bold">Coach Chat</span><button onclick="toggleSidebar()" class="text-on-surface-variant hover:text-primary-fixed"><span class="material-symbols-outlined">history</span></button></div>'
        )
        
    # Inject Sidebar HTML before the end of the main or body
    if "chatSidebar" not in content:
        content = content.replace("</main>", SIDEBAR_HTML + "\n</main>")

    # Inject JS functions
    if "toggleSidebar()" not in content:
        content = content.replace("</script>", JS_CODE + "\n</script>")

    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)

print("Chat features added.")
