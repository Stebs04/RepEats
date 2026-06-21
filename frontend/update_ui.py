import os

HEADER_HTML = """<!-- Standard TopAppBar -->
<header class="fixed top-0 w-full z-50 bg-background/70 backdrop-blur-md border-b border-white/10 shadow-sm flex justify-between items-center px-container-margin h-16 transition-all duration-300">
<div class="flex items-center gap-base cursor-pointer" onclick="window.location.href='dashboard.html'">
<img alt="RepEats Logo" class="h-8 w-8 rounded-full object-cover border border-primary-container/30 shadow-[0_0_10px_rgba(57,255,20,0.3)]" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB5JBYk8WthW7ev1bT3z8Cy2GFQsuz6f9wTkG2tfBMfIhPyUDM9KcCpfKCcaT_r_x-7zMexkfGclcgnFTeAPKasNrSwvLtnDr1v7qArTOZY239GPP11A4CY-urfgo4WbR0-3gEJbP8Wzi9PztiGEmbXfB0CUPp2rskclALSQx9acPybxmOxUQJGKbtsvBugOgJIbJkCkPr4HpBY0zoyzmPNgC22xHUUADyVPmfjL_aL1MbER8BWXzWIlpPVymD_gSYr53gj9dQ2A9sq"/>
<span class="font-display-xl-mobile text-display-xl-mobile font-black tracking-tighter text-primary-container hidden md:inline-block">RepEats</span>
</div>
<nav class="hidden md:flex gap-lg items-center">
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="dashboard.html">
<span class="material-symbols-outlined">dashboard</span> Home
</a>
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="nutritionist.html">
<span class="material-symbols-outlined">restaurant</span> Nutrition
</a>
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="fitness_coach.html">
<span class="material-symbols-outlined">fitness_center</span> Coach
</a>
<a class="text-on-surface-variant hover:text-primary-fixed transition-colors flex items-center gap-xs" href="user_profile.html">
<span class="material-symbols-outlined">person</span> Profile
</a>
</nav>
<div class="flex items-center gap-sm">
<button class="text-on-surface-variant hover:text-primary-fixed transition-colors active:scale-95 duration-100 p-2 rounded-full hover:bg-surface-container">
<span class="material-symbols-outlined">notifications</span>
</button>
<button class="text-on-surface-variant hover:text-primary-fixed transition-colors active:scale-95 duration-100 p-2 rounded-full hover:bg-surface-container cursor-pointer" onclick="window.location.href='user_profile.html'">
<span class="material-symbols-outlined">settings</span>
</button>
<img alt="User profile avatar" class="h-8 w-8 rounded-full border border-surface-variant object-cover ml-xs cursor-pointer" onclick="window.location.href='user_profile.html'" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB5kAAYmdLyOnNBt-APBd6mu56bs7uY3nqxfxpz1Ugtp3R2UBS5LmBsml2iK0LRAo-NNa9qV0Ona2PercJerC5UgzlKljyLEaxhbZVJWhv-voZfv-rmATye6sPNy1Ys7BhpKNs6ibvywH3gtOjedrrLiSSiE-N7xijRT8NBiaUno7-IhrFt0KXrO2dC2kpW8iZU493uJ7Reugib2CV8boGLyHvP-Cm0t-3Jg0g5a9w8Hezme6LSibT910KDQQVRG7H8F4B6xnaALXR_"/>
</div>
</header>"""

BOTTOM_NAV_HTML = """<!-- Standard BottomNavBar -->
<nav class="md:hidden fixed bottom-0 left-0 w-full rounded-t-xl z-50 bg-surface-container/80 backdrop-blur-xl border-t border-white/5 shadow-[0_-4px_20px_rgba(42,229,0,0.1)] flex justify-around items-center h-20 px-4 pb-4">
<a class="flex flex-col items-center justify-center text-on-surface-variant py-1 px-4 hover:bg-surface-bright/50 active:scale-90 transition-transform duration-200" href="dashboard.html">
<span class="material-symbols-outlined">dashboard</span>
<span class="font-label-sm text-label-sm mt-1">Home</span>
</a>
<a class="flex flex-col items-center justify-center text-on-surface-variant py-1 px-4 hover:bg-surface-bright/50 active:scale-90 transition-transform duration-200" href="nutritionist.html">
<span class="material-symbols-outlined">restaurant</span>
<span class="font-label-sm text-label-sm mt-1">Nutrition</span>
</a>
<a class="flex flex-col items-center justify-center text-on-surface-variant py-1 px-4 hover:bg-surface-bright/50 active:scale-90 transition-transform duration-200" href="fitness_coach.html">
<span class="material-symbols-outlined">fitness_center</span>
<span class="font-label-sm text-label-sm mt-1">Coach</span>
</a>
<a class="flex flex-col items-center justify-center text-on-surface-variant py-1 px-4 hover:bg-surface-bright/50 active:scale-90 transition-transform duration-200" href="user_profile.html">
<span class="material-symbols-outlined">person</span>
<span class="font-label-sm text-label-sm mt-1">Profile</span>
</a>
</nav>"""

files = [
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\dashboard.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\fitness_coach.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\nutritionist.html",
    r"c:\Users\DeaDS\Documents\Programming Project\RepEats\frontend\user_profile.html"
]

import re

for fp in files:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace header. We look for <header ...> ... </header>
    # Note: nutritionist.html has two headers! (mobile and desktop)
    # We will replace all <header>...</header> with just one header
    content = re.sub(r'<header.*?</header>', '', content, flags=re.DOTALL)
    # Insert new header right after <body...>
    content = re.sub(r'(<body[^>]*>)', r'\1\n' + HEADER_HTML, content, count=1)
    
    # Replace bottom nav. We look for <nav class="md:hidden.*?</nav>
    # Wait, some might just be <nav ... </nav>. Let's find <nav ... bottom-0 ... </nav>
    content = re.sub(r'<nav[^>]*bottom-0.*?</nav>', BOTTOM_NAV_HTML, content, flags=re.DOTALL)
    # Also in user_profile it's just <nav ... </nav>
    content = re.sub(r'<nav[^>]*md:hidden.*?</nav>', BOTTOM_NAV_HTML, content, flags=re.DOTALL)
    
    # Specific mockups to hide
    if "dashboard.html" in fp:
        # Hide Action Cards
        content = content.replace('<div class="grid grid-cols-1 lg:grid-cols-2 gap-md mb-xl">', '<div class="grid grid-cols-1 lg:grid-cols-2 gap-md mb-xl" id="actionCards" style="display:none;">')
    
    if "fitness_coach.html" in fp:
        content = content.replace('<section class="relative rounded-xl p-md overflow-hidden border border-white/10 bg-surface-container-high/60 backdrop-blur-md">', '<section class="relative rounded-xl p-md overflow-hidden border border-white/10 bg-surface-container-high/60 backdrop-blur-md" style="display:none;">')
        content = content.replace('<section class="flex flex-col gap-sm">', '<section class="flex flex-col gap-sm" style="display:none;">')

    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)

print("Done replacing headers and navs.")
