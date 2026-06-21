import re

#########################
# 1. Update dashboard_api.py
#########################
with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\backend\dashboard_api.py", "r", encoding="utf-8") as f:
    dashboard_api_content = f.read()

meals_code = """
        # Recupero i pasti di oggi per categoria
        from datetime import datetime, timezone
        from sqlalchemy import func
        from src.database.database import get_session
        from src.database.models import MealLog

        session = get_session()
        today_date = datetime.now(timezone.utc).date()
        meals_today_records = session.query(MealLog).filter(
            MealLog.user_id == user_id,
            func.date(MealLog.timestamp) == today_date
        ).all()
        session.close()

        meals_by_cat = {"Colazione": [], "Pranzo": [], "Cena": [], "Spuntino": []}
        for m in meals_today_records:
            cat = m.category if m.category in meals_by_cat else "Spuntino"
            meals_by_cat[cat].append({
                "id": m.id,
                "name": m.name,
                "calories": m.calories,
                "proteins": m.proteins,
                "carbs": m.carbohydrates,
                "fats": m.fats
            })
"""

# Inject meals code before return
dashboard_api_content = dashboard_api_content.replace(
    "return {", 
    meals_code + "\n        return {\n            \"meals\": meals_by_cat,"
)

with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\backend\dashboard_api.py", "w", encoding="utf-8") as f:
    f.write(dashboard_api_content)


#########################
# 2. Update dashboard.html
#########################
with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\dashboard.html", "r", encoding="utf-8") as f:
    dashboard_html = f.read()

MEALS_SECTION_HTML = """
<!-- Meals Breakdown Section -->
<section class="mt-lg">
    <h2 class="font-headline-md text-headline-md text-on-surface mb-md flex items-center gap-2">
        <span class="material-symbols-outlined text-primary-fixed">restaurant</span> I Tuoi Pasti
    </h2>
    <div id="mealsContainer" class="flex flex-col gap-sm">
        <!-- JS will populate accordions here -->
    </div>
</section>
"""

# Insert meals section before the Spacer for FAB
dashboard_html = dashboard_html.replace(
    "<!-- Spacer for FAB & Bottom Nav -->",
    MEALS_SECTION_HTML + "\n<!-- Spacer for FAB & Bottom Nav -->"
)

# Add JS logic to render the meals
JS_DASHBOARD = """
    function renderMeals(meals) {
        const container = document.getElementById('mealsContainer');
        container.innerHTML = '';
        const categories = ['Colazione', 'Pranzo', 'Cena', 'Spuntino'];
        
        categories.forEach(cat => {
            const catMeals = meals[cat] || [];
            let totalCals = 0, totalPro = 0, totalCarb = 0, totalFat = 0;
            catMeals.forEach(m => {
                totalCals += m.calories || 0;
                totalPro += m.proteins || 0;
                totalCarb += m.carbs || 0;
                totalFat += m.fats || 0;
            });
            
            const div = document.createElement('div');
            div.className = 'glass-panel rounded-xl overflow-hidden';
            
            // Header (Accordion Toggle)
            const header = document.createElement('div');
            header.className = 'p-4 flex justify-between items-center cursor-pointer hover:bg-white/5 transition-colors';
            header.innerHTML = `
                <div class="flex flex-col">
                    <span class="font-bold text-on-surface text-[18px]">${cat}</span>
                    <span class="text-sm text-on-surface-variant">${Math.round(totalCals)} kcal</span>
                </div>
                <div class="flex items-center gap-4">
                    <div class="hidden md:flex gap-4 text-xs text-on-surface-variant">
                        <span>PRO: <span class="text-on-surface">${Math.round(totalPro)}g</span></span>
                        <span>CARB: <span class="text-on-surface">${Math.round(totalCarb)}g</span></span>
                        <span>FAT: <span class="text-on-surface">${Math.round(totalFat)}g</span></span>
                    </div>
                    <span class="material-symbols-outlined transform transition-transform duration-300" id="icon-${cat}">expand_more</span>
                </div>
            `;
            
            // Content (List of foods)
            const content = document.createElement('div');
            content.id = `content-${cat}`;
            content.className = 'px-4 pb-4 hidden flex-col gap-2 border-t border-white/10 pt-3';
            
            if (catMeals.length === 0) {
                content.innerHTML = '<span class="text-sm text-on-surface-variant italic">Nessun alimento registrato</span>';
            } else {
                catMeals.forEach(m => {
                    content.innerHTML += `
                        <div class="flex justify-between items-center bg-surface-container-high/50 p-3 rounded-lg border border-white/5">
                            <span class="font-body-md text-on-surface text-sm max-w-[50%] truncate">${m.name}</span>
                            <div class="flex gap-3 text-xs text-on-surface-variant">
                                <span>${Math.round(m.calories)} kcal</span>
                                <span>P:${Math.round(m.proteins)}</span>
                                <span>C:${Math.round(m.carbs)}</span>
                                <span>F:${Math.round(m.fats)}</span>
                            </div>
                        </div>
                    `;
                });
            }
            
            header.onclick = () => {
                content.classList.toggle('hidden');
                content.classList.toggle('flex');
                document.getElementById(`icon-${cat}`).classList.toggle('rotate-180');
            };
            
            div.appendChild(header);
            div.appendChild(content);
            container.appendChild(div);
        });
    }
"""

dashboard_html = dashboard_html.replace("</script>", JS_DASHBOARD + "\n</script>")
dashboard_html = dashboard_html.replace(
    "animateRings(data.today, data.targets);",
    "animateRings(data.today, data.targets);\n                    if(data.meals) renderMeals(data.meals);"
)

with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\dashboard.html", "w", encoding="utf-8") as f:
    f.write(dashboard_html)


#########################
# 3. Update nutritionist.html
#########################
with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html", "r", encoding="utf-8") as f:
    nut_html = f.read()

SCANNER_MODAL_HTML = """
<!-- Scanner Modal -->
<div id="scannerModal" class="fixed inset-0 bg-background/90 backdrop-blur-sm z-[100] hidden flex items-center justify-center p-4">
    <div class="glass-panel w-full max-w-md rounded-2xl p-6 border border-tertiary-fixed/30 flex flex-col gap-4 relative">
        <button onclick="closeScannerModal()" class="absolute top-4 right-4 text-on-surface-variant hover:text-error"><span class="material-symbols-outlined">close</span></button>
        <h3 class="font-headline-md text-on-surface text-center mb-2 flex items-center justify-center gap-2"><span class="material-symbols-outlined text-tertiary-fixed">photo_camera</span> Analisi Pasto</h3>
        
        <div id="scannerForm">
            <div class="flex flex-col gap-1 mb-4">
                <label class="text-sm text-on-surface-variant">Categoria</label>
                <select id="mealCategory" class="w-full bg-surface-container-high border border-white/10 rounded-lg p-3 text-on-surface focus:outline-none focus:border-tertiary-fixed">
                    <option value="Colazione">Colazione</option>
                    <option value="Pranzo">Pranzo</option>
                    <option value="Cena">Cena</option>
                    <option value="Spuntino" selected>Spuntino</option>
                </select>
            </div>
            <div class="flex flex-col gap-1 mb-6">
                <label class="text-sm text-on-surface-variant">Grammatura (g)</label>
                <input type="number" id="mealWeight" value="100" class="w-full bg-surface-container-high border border-white/10 rounded-lg p-3 text-on-surface focus:outline-none focus:border-tertiary-fixed">
            </div>
            <button onclick="submitImage()" class="w-full bg-tertiary-fixed text-on-tertiary-fixed py-3 rounded-xl font-bold uppercase tracking-wider flex justify-center items-center gap-2 active:scale-95 transition-transform">
                <span class="material-symbols-outlined">analytics</span> Analizza Ora
            </button>
        </div>
        
        <div id="scannerLoading" class="hidden flex-col items-center justify-center py-6 gap-4">
            <span class="material-symbols-outlined animate-spin text-tertiary-fixed text-[48px]">progress_activity</span>
            <p class="text-on-surface text-center font-bold">Lumina sta analizzando il tuo pasto...</p>
            <p class="text-sm text-on-surface-variant text-center">Riconoscimento ingredienti e calcolo macro in corso</p>
        </div>
    </div>
</div>
"""

JS_NUTRITIONIST = """
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

nut_html = nut_html.replace("</body>", SCANNER_MODAL_HTML + "\n</body>")
nut_html = nut_html.replace("</script>", JS_NUTRITIONIST + "\n</script>")

# Fix appendBotMessage rendering for bold and markdown basic (optional but good)
MARKDOWN_REPLACE = """
    function appendBotMessage(text) {
        // Simple markdown for bold and newlines
        let formattedText = text.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
        formattedText = formattedText.replace(/\\n/g, '<br>');
        
        const container = document.getElementById('chatContainer') || document.getElementById('chatHistory');
        const botDiv = document.createElement('div');
        botDiv.className = "flex flex-col gap-1 w-[85%] md:w-2/3";
        botDiv.innerHTML = `
            <div class="glass-panel rounded-2xl rounded-tl-none p-4 text-on-surface font-body-md text-body-md relative overflow-hidden border border-tertiary-fixed/20 shadow-[0_4px_24px_-8px_rgba(0,246,246,0.15)]">
                ${formattedText}
            </div>
        `;
        container.appendChild(botDiv);
        container.scrollTop = container.scrollHeight;
    }
"""

nut_html = re.sub(r'function appendBotMessage\(text\) \{.*?\n    \}', MARKDOWN_REPLACE, nut_html, flags=re.DOTALL)

with open(r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html", "w", encoding="utf-8") as f:
    f.write(nut_html)

print("Features installed successfully.")
