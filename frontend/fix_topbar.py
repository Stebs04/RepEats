import re

NEW_NAV = """<nav class="hidden md:flex gap-lg items-center">
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="dashboard.html">
<span class="material-symbols-outlined">dashboard</span> Home
</a>
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="nutritionist.html">
<span class="material-symbols-outlined">restaurant</span> Nutrition
</a>
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="fitness_coach.html">
<span class="material-symbols-outlined">fitness_center</span> Coach
</a>
</nav>"""

NEW_ICONS = """<div class="flex items-center gap-sm">
<img alt="User profile avatar" class="h-8 w-8 rounded-full border border-surface-variant object-cover ml-xs cursor-pointer" onclick="window.location.href='user_profile.html'" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB5kAAYmdLyOnNBt-APBd6mu56bs7uY3nqxfxpz1Ugtp3R2UBS5LmBsml2iK0LRAo-NNa9qV0Ona2PercJerC5UgzlKljyLEaxhbZVJWhv-voZfv-rmATye6sPNy1Ys7BhpKNs6ibvywH3gtOjedrrLiSSiE-N7xijRT8NBiaUno7-IhrFt0KXrO2dC2kpW8iZU493uJ7Reugib2CV8boGLyHvP-Cm0t-3Jg0g5a9w8Hezme6LSibT910KDQQVRG7H8F4B6xnaALXR_"/>
</div>"""

files = [
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\dashboard.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\fitness_coach.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\user_profile.html"
]

for fp in files:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    
    content = re.sub(r'<nav class="hidden md:flex gap-lg items-center">.*?</nav>', NEW_NAV, content, flags=re.DOTALL)
    
    # We replace the div with the icons. The regex needs to be careful.
    content = re.sub(r'<div class="flex items-center gap-sm">\s*<button.*?<img alt="User profile avatar".*?</div>', NEW_ICONS, content, flags=re.DOTALL)

    # Empty initial chat history in fitness_coach
    if "fitness_coach.html" in fp:
        content = re.sub(
            r'<div id="chatHistory" class="flex flex-col gap-sm max-h-\[300px\] overflow-y-auto hide-scrollbar">.*?</div>\s*</div>',
            '<div id="chatHistory" class="flex flex-col gap-sm max-h-[300px] overflow-y-auto hide-scrollbar"></div>',
            content, flags=re.DOTALL
        )
        
    # Empty initial chat history in nutritionist
    if "nutritionist.html" in fp:
        # Note: in nutritionist, the chat container has id="chatContainer"
        # and has a placeholder message. Let's find it.
        pass

    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)

print("Navbar updated.")
