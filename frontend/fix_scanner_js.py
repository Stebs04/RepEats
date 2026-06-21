import re

with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html", "r", encoding="utf-8") as f:
    html = f.read()

# The JS we mistakenly injected in the head
mistake_js = """
    let selectedImageFile = null;

    document.getElementById('scannerBtn').addEventListener('click', () => {
        document.getElementById('imageInput').click();
    });

    document.getElementById('imageInput').addEventListener('change', (e) => {
        if(e.target.files && e.target.files.length > 0) {
            selectedImageFile = e.target.files[0];
            document.getElementById('scannerModal').classList.remove('hidden');
            document.getElementById('scannerForm').classList.remove('hidden');
            document.getElementById('scannerLoading').classList.add('hidden');
        }
    });

    function closeScannerModal() {
        document.getElementById('scannerModal').classList.add('hidden');
        document.getElementById('imageInput').value = '';
        selectedImageFile = null;
    }

    async function submitImage() {
        if(!selectedImageFile) return;
        
        const cat = document.getElementById('mealCategory').value;
        const weight = document.getElementById('mealWeight').value;
        
        document.getElementById('scannerForm').classList.add('hidden');
        document.getElementById('scannerLoading').classList.remove('hidden');
        document.getElementById('scannerLoading').classList.add('flex');
        
        const formData = new FormData();
        formData.append('file', selectedImageFile);
        formData.append('user_id', userId);
        formData.append('grammatura', weight);
        formData.append('categoria', cat);
        
        try {
            const res = await fetch('/api/chat/vision', {
                method: 'POST',
                body: formData
            });
            
            if(res.ok) {
                const data = await res.json();
                closeScannerModal();
                
                // Construct a message from Lumina
                const meal = data.data;
                let msg = `Ho analizzato il tuo pasto (${cat}): **${meal.name}**.\\n\\n`;
                msg += `🔥 Calorie: **${Math.round(meal.calories)} kcal**\\n`;
                msg += `🥩 Proteine: **${Math.round(meal.proteins)}g**\\n`;
                msg += `🍞 Carboidrati: **${Math.round(meal.carbohydrates)}g**\\n`;
                msg += `🥑 Grassi: **${Math.round(meal.fats)}g**\\n\\n`;
                msg += `L'ho salvato automaticamente nei tuoi macros di oggi! 💪`;
                
                appendBotMessage(msg);
                
                // If there's an active conversation, we could technically save this message,
                // but just showing it is enough to acknowledge it.
            } else {
                alert("Errore durante l'analisi.");
                closeScannerModal();
            }
        } catch(e) {
            console.error(e);
            alert("Errore di rete.");
            closeScannerModal();
        }
    }
"""

# Remove the mistake from the head. We can just use string replacement if it matches exactly.
# Wait, let's just find `    let selectedImageFile = null;` up to `    }`
if mistake_js in html:
    html = html.replace(mistake_js, "")
else:
    # Use regex if exact string match fails due to line endings
    html = re.sub(r'let selectedImageFile = null;.*?async function submitImage\(\) \{.*?\} catch\(e\) \{.*?\}\s*\}', '', html, flags=re.DOTALL)

# Now inject it correctly at the bottom, just before </body>
correct_injection = """
<script>
    let selectedImageFile = null;

    document.getElementById('scannerBtn').addEventListener('click', () => {
        document.getElementById('imageInput').click();
    });

    document.getElementById('imageInput').addEventListener('change', (e) => {
        if(e.target.files && e.target.files.length > 0) {
            selectedImageFile = e.target.files[0];
            document.getElementById('scannerModal').classList.remove('hidden');
            document.getElementById('scannerForm').classList.remove('hidden');
            document.getElementById('scannerLoading').classList.add('hidden');
        }
    });

    function closeScannerModal() {
        document.getElementById('scannerModal').classList.add('hidden');
        document.getElementById('imageInput').value = '';
        selectedImageFile = null;
    }

    async function submitImage() {
        if(!selectedImageFile) return;
        
        const cat = document.getElementById('mealCategory').value;
        const weight = document.getElementById('mealWeight').value;
        
        document.getElementById('scannerForm').classList.add('hidden');
        document.getElementById('scannerLoading').classList.remove('hidden');
        document.getElementById('scannerLoading').classList.add('flex');
        
        const formData = new FormData();
        formData.append('file', selectedImageFile);
        formData.append('user_id', userId);
        formData.append('grammatura', weight);
        formData.append('categoria', cat);
        
        try {
            const res = await fetch('/api/chat/vision', {
                method: 'POST',
                body: formData
            });
            
            if(res.ok) {
                const data = await res.json();
                closeScannerModal();
                
                const meal = data.data;
                let msg = `Ho analizzato il tuo pasto (${cat}): **${meal.name}**.\\n\\n`;
                msg += `🔥 Calorie: **${Math.round(meal.calories)} kcal**\\n`;
                msg += `🥩 Proteine: **${Math.round(meal.proteins)}g**\\n`;
                msg += `🍞 Carboidrati: **${Math.round(meal.carbohydrates)}g**\\n`;
                msg += `🥑 Grassi: **${Math.round(meal.fats)}g**\\n\\n`;
                msg += `L'ho salvato automaticamente nei tuoi macros di oggi! 💪`;
                
                appendBotMessage(msg);
            } else {
                alert("Errore durante l'analisi.");
                closeScannerModal();
            }
        } catch(e) {
            console.error(e);
            alert("Errore di rete.");
            closeScannerModal();
        }
    }
</script>
</body>
"""

html = html.replace("</body>", correct_injection)

with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Fixed nutritionist.html")
