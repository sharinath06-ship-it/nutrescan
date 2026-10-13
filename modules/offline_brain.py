"""
NutriScan NutriBot brains.

Two layers, used in this order:
  1. Ollama local AI  -> offline ChatGPT-style, runs on your laptop
  2. Offline answers  -> built-in health knowledge base, always works
"""
import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:0.5b"
REQUEST_TIMEOUT = 45


# ============================================================
# LAYER 1: OLLAMA (offline AI, runs on your laptop)
# ============================================================

def ollama_available():
    """Check if Ollama is running on this laptop."""
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        return False


def _pick_model():
    """Use the first installed model; fall back to default name."""
    try:
        req = urllib.request.Request(OLLAMA_URL + "/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        if models:
            name = models[0].get("name", DEFAULT_MODEL)
            # Prefer a small/fast model if several are installed
            for m in models:
                n = m.get("name", "")
                if "0.5b" in n or ":0.5" in n or "1b" in n:
                    return n
            return name
    except Exception:
        pass
    return DEFAULT_MODEL


def ask_ollama(question, context=""):
    """
    Ask the local offline AI (Ollama).
    Returns answer string, or raises Exception on failure.
    Short, quick answers are enforced (small token limit).
    """
    if not ollama_available():
        raise RuntimeError("Ollama is not running")

    prompt = question
    if context:
        prompt = (
            "You are NutriBot, a health and nutrition assistant for NutriScan. "
            "Answer briefly (max 120 words), practical and safe. "
            "Never diagnose or prescribe. Add a short consult-a-doctor note "
            "for medical conditions.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

    payload = json.dumps({
        "model": _pick_model(),
        "messages": [
            {"role": "system", "content": (
                "You are NutriBot, a friendly health and nutrition assistant. "
                "Give short, clear, practical answers in simple language. "
                "Use bullet points when helpful. Never diagnose diseases or "
                "prescribe medicines; recommend consulting a doctor for "
                "medical conditions."
            )},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 220,   # keeps answers short = fast
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    answer = (
        data.get("message", {}).get("content", "").strip()
    )
    if not answer:
        raise RuntimeError("Ollama returned an empty answer")
    return answer


# ============================================================
# LAYER 2: OFFLINE KNOWLEDGE BASE (always works, instant)
# ============================================================

# topic keywords -> pre-written health answer
HEALTH_TOPICS = {

    "trans fat": (
        "**Trans fat** is the worst type of fat for your heart.\n\n"
        "- It raises bad cholesterol (LDL) and lowers good cholesterol (HDL)\n"
        "- It increases the risk of heart disease and stroke\n"
        "- Avoid products listing *partially hydrogenated oil*\n"
        "- WHO recommends less than 1% of daily calories from trans fat\n\n"
        "⚠️ General information only — consult a doctor for medical advice."
    ),

    "sugar": (
        "**Sugar** in excess causes weight gain, diabetes and tooth decay.\n\n"
        "- WHO: keep added sugar under 25 g (6 teaspoons) per day\n"
        "- Watch for hidden names: sucrose, dextrose, corn syrup, HFCS\n"
        "- Choose fruits, nuts or jaggery (in limits) over sweets\n"
        "- Label words like 'no added sugar' can still mean high natural sugar\n\n"
        "⚠️ Diabetics should follow their doctor's diet plan."
    ),

    "diabetes": (
        "**For diabetes**, food choice is medicine:\n\n"
        "- Prefer low-GI foods: millets, oats, whole wheat, pulses\n"
        "- Avoid sugar, white rice spikes, juices, sweets, maida items\n"
        "- Eat small frequent meals; walk 15–20 min after eating\n"
        "- Control portions — even healthy food raises blood sugar\n"
        "- Check labels for sugar AND refined flour\n\n"
        "⚠️ This is general information. Follow your doctor's advice and "
        "take medicines on time."
    ),

    "blood pressure": (
        "**For high blood pressure (BP)**:\n\n"
        "- Cut salt: WHO limit is 5 g/day (about 1 teaspoon, all sources)\n"
        "- Avoid pickles, papad, chips, namkeen, processed & tinned food\n"
        "- Eat potassium-rich foods: banana, coconut water, spinach\n"
        "- Stay active, manage stress, limit alcohol\n"
        "- 'Low sodium' labels are better choices\n\n"
        "⚠️ Please follow your doctor's advice — do not stop BP medicine "
        "on your own."
    ),

    "heart": (
        "**Heart-healthy eating:**\n\n"
        "- Avoid trans fat, deep-fried food, excess salt and sugar\n"
        "- Prefer: nuts, seeds, oats, millets, fish/omega-3 (if you eat), "
        "fruits and vegetables\n"
        "- Use mustard/olive/groundnut oil in limits; ghee in moderation\n"
        "- Walk 30 min daily, don't smoke, keep weight in check\n\n"
        "⚠️ General information only — consult a cardiologist for personal "
        "advice."
    ),

    "cholesterol": (
        "**Managing cholesterol through food:**\n\n"
        "- Cut trans fat (baked/fried packaged food) completely\n"
        "- Soluble fibre helps: oats, barley, dal, fruits with skin\n"
        "- Nuts (4–5 daily) and groundnut/mustard oil are better fats\n"
        "- Avoid organ meat and excess egg yolk if LDL is high\n"
        "- Exercise 30 min/day raises good (HDL) cholesterol\n\n"
        "⚠️ Consult your doctor for your exact targets and medicines."
    ),

    "protein": (
        "**Protein** builds muscle, immunity and repairs the body.\n\n"
        "- Daily need: roughly 0.8–1 g per kg body weight\n"
        "- Indian vegetarian sources: dal, paneer, curd, soybean, chana, "
        "groundnuts, milk\n"
        "- Combine dal + rice or roti + curd for complete protein\n"
        "- Athletes, children and elderly need a little more\n\n"
        "⚠️ Kidney patients should ask their doctor before increasing "
        "protein."
    ),

    "weight": (
        "**For healthy weight loss:**\n\n"
        "- Calorie deficit + daily movement beats any special diet\n"
        "- Fill half the plate with vegetables, quarter protein, "
        "quarter carbs\n"
        "- Avoid sugary drinks, juice, chips, maida and fried food\n"
        "- Eat slowly; drink water before meals; sleep 7 hours\n"
        "- Lose 0.5 kg/week — faster is not healthier\n\n"
        "⚠️ Sudden weight change can signal a health problem — see a doctor."
    ),

    "maida": (
        "**Maida (refined flour)** is low in fibre and digests fast,\n"
        "spiking blood sugar.\n\n"
        "- Found in: bread, biscuits, noodles, pizza, pastries, bhatura\n"
        "- Better swaps: whole wheat atta, millet flour, oats\n"
        "- Occasional use is fine; daily heavy use is not\n\n"
        "⚠️ General information only."
    ),

    "palm oil": (
        "**Palm oil** is high in saturated fat.\n\n"
        "- Common in: biscuits, noodles, chips, vanaspati, packaged snacks\n"
        "- Regular large amounts may raise cholesterol\n"
        "- Occasional use is not a problem — check quantity you eat daily\n"
        "- Healthier oils: groundnut, mustard, olive, sunflower (in rotation)\n\n"
        "⚠️ General information only."
    ),

    "preservative": (
        "**Preservatives** keep packaged food safe but some deserve care:\n\n"
        "- Sodium benzoate / BHA / BHT: limits set by FSSAI, small amounts "
        "are tested safe\n"
        "- Sodium nitrite (in processed meat): limit intake\n"
        "- Sulphites (dried fruit, juice): avoid if asthma/sensitivity\n"
        "- Long preservative lists = highly processed food — eat less of it\n\n"
        "⚠️ If you notice allergies or reactions, consult a doctor."
    ),

    "vitamin": (
        "**Vitamins** you may miss in a busy Indian diet:\n\n"
        "- Vitamin D: sunlight 15 min, milk, eggs\n"
        "- B12: milk, curd, eggs (vegetarians are often low)\n"
        "- Iron: palak, dates, ragi, jaggery + vitamin C for absorption\n"
        "- Vitamin A: carrot, mango, sweet potato, green leafy veg\n\n"
        "⚠️ Do not take high-dose supplements without a doctor's advice."
    ),

    "immunity": (
        "**Building immunity through food:**\n\n"
        "- Daily: fruits, vegetables, dal, curd, nuts, seeds\n"
        "- Turmeric, ginger, garlic, tulsi are helpful additions\n"
        "- Protein + sleep + activity matter more than any one 'magic' food\n"
        "- Avoid excess sugar and junk — they reduce immunity\n\n"
        "⚠️ No single food prevents disease — consult a doctor if unwell."
    ),

    "water": (
        "**Hydration:**\n\n"
        "- Aim for 8–10 glasses (2–2.5 L) daily, more in summer/exercise\n"
        "- Drink on time rather than feeling thirsty\n"
        "- Coconut water, buttermilk, soup, fruit count toward fluids\n"
        "- Cut sugary drinks, cola and excess tea/coffee\n"
        "- Pale-yellow urine usually means good hydration\n\n"
        "⚠️ Kidney or heart patients should ask their doctor about fluid "
        "limits."
    ),

    "digestion": (
        "**For good digestion:**\n\n"
        "- Eat slowly and chew well; don't skip breakfast\n"
        "- Fibre: vegetables, dal with skin, oats, fruit (helps constipation)\n"
        "- Curd/lassi adds healthy bacteria; avoid excess spicy/oily food\n"
        "- Walk 10 min after meals; drink warm water in the morning\n\n"
        "⚠️ Persistent pain, acidity or bloating needs a doctor's check-up."
    ),

    "millets": (
        "**Millets are a great Indian superfood:**\n\n"
        "- Ragi: calcium + iron — good for children and elders\n"
        "- Jowar/bajra: fibre, keeps you full longer, better than rice for "
        "diabetics\n"
        "- Foxtail/kutki: light and easy to digest\n"
        "- Swap rice for millets 4–5 times a week\n\n"
        "⚠️ General information only."
    ),

    "oil": (
        "**Choosing cooking oil:**\n\n"
        "- No single oil is perfect — rotate groundnut, mustard, sunflower, "
        "olive\n"
        "- Avoid reusing fried oil (repeated heating creates harmful compounds)\n"
        "- Limit vanaspati/partially hydrogenated fat (trans fat)\n"
        "- Total oil: about 3–5 teaspoons per person per day is a good guide\n\n"
        "⚠️ General information only."
    ),

    "salt": (
        "**Salt/sodium:**\n\n"
        "- WHO limit: 5 g salt/day (about 1 level teaspoon, all sources)\n"
        "- Hidden salt: chips, namkeen, pickles, papad, sauces, biscuits\n"
        "- Read 'sodium' on labels — 600 mg sodium ≈ 1.5 g salt\n"
        "- Use lemon, herbs, spices and masalas for taste instead\n\n"
        "⚠️ BP patients must follow their doctor's salt limit."
    ),

    "ghee": (
        "**Ghee** in moderation is fine in an Indian kitchen:\n\n"
        "- 1–2 teaspoons daily is generally okay for most healthy adults\n"
        "- It provides energy and fat-soluble vitamins\n"
        "- Problem comes with large amounts + fried snacks together\n"
        "- For cholesterol issues, keep it minimal and ask your doctor\n\n"
        "⚠️ General information only."
    ),

    "junk": (
        "**Why to cut junk food:**\n\n"
        "- High in calories, salt, sugar and unhealthy fats — low in nutrition\n"
        "- Regular intake links to obesity, diabetes and heart disease\n"
        "- Swap: chips → roasted chana/makhana, cola → buttermilk/lemon water, "
        "biscuits → fruit/nuts\n"
        "- Once-a-week treat is fine; daily is harmful\n\n"
        "⚠️ General information only."
    ),

    "addictive": (
        "**'Addictive' claims about food** are marketing.\n\n"
        "- Sugar, salt and fat together do make food hard to stop eating\n"
        "- Best trick: don't keep junk at home — out of sight, out of mind\n"
        "- Read portion size on the label; share packs instead of eating "
        "alone\n\n"
        "⚠️ General information only."
    ),

    "exercise": (
        "**Activity guidelines:**\n\n"
        "- 150 min/week moderate activity (30 min, 5 days) — brisk walk counts\n"
        "- Plus 2 days of light strength work (squats, stairs, bands)\n"
        "- Walk after meals to control blood sugar\n"
        "- Sit less: stand/move every hour\n\n"
        "⚠️ Start slowly if you have a health condition — ask your doctor first."
    ),

    "doctor": (
        "**Please consult a qualified doctor** for personal medical advice.\n\n"
        "NutriBot only gives general health and nutrition information — "
        "it cannot examine you, diagnose conditions or prescribe medicines.\n\n"
        "Take your report/labels with you to the appointment; it helps the "
        "doctor advise better."
    ),
}

# ============================================================
# EXTRA HEALTH TOPICS (full health coverage)
# ============================================================

HEALTH_TOPICS.update({

    "anemia": (
        "**Anemia (low blood / iron deficiency):**\n\n"
        "- Iron-rich foods: palak, methi, ragi, dates, jaggery, beetroot, "
        "dal, groundnuts\n"
        "- Eat with vitamin C (lemon, amla, tomato) — iron absorbs better\n"
        "- Tea/coffee with meals blocks iron — drink 1 hr apart\n"
        "- Causes: heavy periods, low intake, worms, pregnancy\n\n"
        "⚠️ Get Hb tested and follow your doctor's advice on iron tablets."
    ),

    "thyroid": (
        "**Thyroid and food:**\n\n"
        "- Take thyroid tablet empty stomach, wait 30–45 min before eating\n"
        "- Iodine: use iodised salt; seafood/nuts if you eat them\n"
        "- Avoid excess raw cabbage, cauliflower, broccoli if advised\n"
        "- Fibre + exercise help with weight gain common in hypothyroid\n\n"
        "⚠️ Follow your doctor's dose and test schedule — food does not "
        "replace medicine."
    ),

    "kidney": (
        "**Kidney-friendly eating:**\n\n"
        "- Follow your nephrologist's protein/fluid/potassium limits — "
        "they differ per patient\n"
        "- Reduce salt; avoid packaged food and soda\n"
        "- If potassium is high: limit banana, coconut water, orange, potato, "
        "tomato\n"
        "- Never replace prescribed medicine with home remedies\n\n"
        "⚠️ Kidney diet must be personalised — ask your doctor/dietitian."
    ),

    "liver": (
        "**Liver care through lifestyle:**\n\n"
        "- No alcohol (or strict limits) — the single biggest factor\n"
        "- Avoid unnecessary painkillers/supplements — many stress the liver\n"
        "- Cut fried food, sugar-sweetened drinks; keep weight in check\n"
        "- Coffee, veggies, dal, fruits and whole grains are liver-friendly\n\n"
        "⚠️ Fatty liver is reversible with lifestyle — confirm with your doctor."
    ),

    "bone": (
        "**Strong bones:**\n\n"
        "- Calcium: milk, curd, ragi, bajra, til, green leafy veg\n"
        "- Vitamin D: sunlight 15 min + milk (helps calcium absorb)\n"
        "- Weight-bearing walks and light exercise strengthen bones\n"
        "- Cut excess cola/salt — they leach calcium\n\n"
        "⚠️ If you have fractures or severe pain, see a doctor."
    ),

    "joint": (
        "**Joint pain & stiffness:**\n\n"
        "- Keep a healthy weight — every extra kg stresses knees\n"
        "- Gentle daily movement: walking, cycling, stretching\n"
        "- Anti-inflammatory foods: turmeric, ginger, omega-3, vegetables\n"
        "- Reduce deep-fried and refined-oil junk food\n\n"
        "⚠️ Persistent swelling/locking of joints needs a doctor's check."
    ),

    "pregnancy": (
        "**During pregnancy, food safety matters:**\n\n"
        "- Eat fresh, home-cooked food; avoid raw papaya, unpasteurised milk, "
        "high-mercury fish\n"
        "- Iron + folic acid tablet as prescribed; include dal, palak, nuts\n"
        "- Small frequent meals; control gestational sugar — walk daily\n"
        "- Limit caffeine; avoid alcohol and smoking completely\n\n"
        "⚠️ Follow your gynaecologist's advice and supplements."
    ),

    "child": (
        "**Kids' nutrition:**\n\n"
        "- Daily: milk/curd, dal or egg, seasonal fruit, vegetables, roti/rice\n"
        "- Limit chips, noodles, biscuits, cold drinks — they kill appetite\n"
        "- No packaged juice — whole fruit instead\n"
        "- Involve kids in cooking; never force-feed\n\n"
        "⚠️ For growth concerns, consult your paediatrician."
    ),

    "elderly": (
        "**For older adults:**\n\n"
        "- Protein at every meal (dal, curd, egg, paneer) prevents muscle loss\n"
        "- Soft foods if chewing is hard; small frequent meals\n"
        "- Calcium + vitamin D + daily walk for bones\n"
        "- Drink water regularly — thirst reduces with age\n\n"
        "⚠️ Medicines and diet interact — inform your doctor of all foods "
        "you take regularly."
    ),

    "muscle": (
        "**Building muscle:**\n\n"
        "- Protein: 1.2–1.6 g per kg body weight for active people\n"
        "- Indian options: paneer, soya, dal, eggs (if you eat), milk, curd\n"
        "- Train 3–4 days/week; protein without training won't build muscle\n"
        "- Sleep 7–8 h — muscle grows during rest\n\n"
        "⚠️ Supplements are optional; food first. Ask a trainer/doctor "
        "before using any supplement."
    ),

    "energy": (
        "**Feeling tired all the time?** Common food reasons:\n\n"
        "- Skip breakfast / long gaps → eat small regular meals\n"
        "- Low iron or B12 (very common in vegetarians) — get tested\n"
        "- Not drinking enough water\n"
        "- Too much sugar → energy crash after sweets\n"
        "- Poor sleep and no activity also cause fatigue\n\n"
        "⚠️ Constant tiredness can be anaemia, thyroid or diabetes — "
        "please see a doctor."
    ),

    "breakfast": (
        "**A good Indian breakfast:**\n\n"
        "- Best: poha/upma with veg, dosa/idli with sambar, oats, "
        "dal chilla, eggs (if you eat)\n"
        "- Add milk/curd and a fruit\n"
        "- Avoid: maida biscuits, vada-puri daily, tea with lots of sugar\n"
        "- Breakfast should be filling — it reduces evening junk cravings\n\n"
        "⚠️ General information only."
    ),

    "skin": (
        "**Skin & food:**\n\n"
        "- Water + fruits + vegetables help skin stay healthy\n"
        "- Excess sugar and fried food can worsen acne\n"
        "- Nuts, seeds and dal provide zinc/protein for repair\n"
        "- Oil pulls/wonder creams don't fix a bad diet\n\n"
        "⚠️ Persistent acne, rashes need a dermatologist."
    ),

    "hair": (
        "**Hair fall & diet:**\n\n"
        "- Protein (dal, milk, curd, egg) + iron (palak, dates, ragi)\n"
        "- B12 and vitamin D deficiency is a common hidden cause — test it\n"
        "- Crash diets cause hair fall — lose weight slowly\n"
        "- Drink enough water; manage stress and sleep\n\n"
        "⚠️ Sudden heavy hair fall should be checked by a doctor."
    ),

    "lactose": (
        "**Lactose intolerance:**\n\n"
        "- Curd, paneer and buttermilk are usually better tolerated than "
        "plain milk\n"
        "- Try small milk amounts with meals, not empty stomach\n"
        "- Calcium alternatives: ragi, til, green veg, fortified soy milk\n"
        "- Lactose-free milk is available\n\n"
        "⚠️ Confirm with a doctor before removing milk completely."
    ),

    "gluten": (
        "**Gluten (wheat protein):**\n\n"
        "- Only people with coeliac disease/named allergy must avoid it "
        "completely\n"
        "- For others, whole wheat roti is healthy fibre\n"
        "- Gluten-free packaged foods are often high in sugar/fat — read labels\n"
        "- Naturally gluten-free: rice, dal, millets, potato, fruits\n\n"
        "⚠️ Do not self-diagnose — test before cutting gluten out."
    ),

    "acidity": (
        "**Acidity / heartburn relief:**\n\n"
        "- Eat smaller meals; don't lie down right after eating\n"
        "- Limit: spicy food, coffee, cola, fried snacks, late-night meals\n"
        "- Buttermilk, soaked jeera water, cold milk can soothe\n"
        "- Keep a food diary to find your personal triggers\n\n"
        "⚠️ Pain lasting weeks, black stools or vomiting → see a doctor."
    ),

    "safety": (
        "**Food safety basics:**\n\n"
        "- Wash hands and veg before cooking; keep raw and cooked separate\n"
        "- Refrigerate cooked food within 2 hours; reheat till piping hot\n"
        "- Check expiry/best-before before eating packaged food\n"
        "- Don't eat swollen cans, torn packets or off-smelling food\n"
        "- Drink clean/boiled water\n\n"
        "⚠️ Food poisoning with fever/vomiting needs medical care."
    ),

    "expiry": (
        "**Expiry dates explained:**\n\n"
        "- 'Best before' = quality drops after that date (still safe briefly)\n"
        "- 'Use by' = safety date — do not eat after it\n"
        "- FSSAI India allows small grace periods, but when unsure, throw it out\n"
        "- Once opened, consume within the label's stated time\n\n"
        "⚠️ When in doubt, don't risk it."
    ),

    "stale oil": (
        "**Reused / stale frying oil:**\n\n"
        "- Reheating oil repeatedly creates harmful compounds and trans fat\n"
        "- Don't reuse more than once; never if it smokes, foams or smells odd\n"
        "- Home fried food once in a while is fine; street food daily is risky\n\n"
        "⚠️ General information only."
    ),

    "vegan": (
        "**Vegetarian/vegan nutrition watch-outs:**\n\n"
        "- B12: milk/curd — vegans need fortified food or tablets\n"
        "- Iron + calcium: ragi, palak, dates, jaggery, dal\n"
        "- Protein combo: dal + rice, roti + curd, soya, paneer\n"
        "- Omega-3: walnuts, flaxseed (alsi), mustard oil\n\n"
        "⚠️ Long-term vegan diets need planned supplements — ask a "
        "dietitian."
    ),

    "detox": (
        "**'Detox' drinks and diets:**\n\n"
        "- Your liver and kidneys already detox your body — no drink resets them\n"
        "- Most detox plans are just calorie restriction; you regain the weight\n"
        "- Better everyday habits: water, vegetables, fruits, sleep, walking\n"
        "- Avoid products promising miracle cures\n\n"
        "⚠️ Don't spend money on unproven detox products."
    ),

    "supplement": (
        "**Supplements:**\n\n"
        "- Food first — supplements fill a gap, they don't replace meals\n"
        "- Only take what you lack (doctor-confirmed deficiency)\n"
        "- High-dose vitamin A/D/iron can harm — more is not better\n"
        "- Protein powder is optional; dal/paneer/milk do the same job\n\n"
        "⚠️ Show any supplement to your doctor, especially with medicines."
    ),
})


# ============================================================
# INGREDIENT HEALTH FACTS (every ingredient explained)
# ============================================================

INGREDIENT_FACTS = {

    # --- Fats & oils ---
    "palm oil": "Palm oil is high in saturated fat. Common in biscuits, "
                "noodles and chips. Occasional use is fine; don't eat "
                "these daily. Healthier rotation: groundnut, mustard, "
                "sunflower, olive oil.",
    "vanaspati": "Vanaspati/hydrogenated fat can contain trans fat — the "
                 "worst fat for the heart. Avoid regular use; check for "
                 "'partially hydrogenated' on the label.",
    "hydrogenated oil": "Hydrogenated oil may contain trans fat which raises "
                        "bad cholesterol. Choose products without it.",
    "trans fat": "Trans fat raises heart disease risk. WHO says keep it "
                 "near zero. Avoid 'partially hydrogenated oil' entirely.",
    "ghee": "Ghee in 1–2 teaspoons daily is generally fine for healthy "
            "adults. It adds taste and fat-soluble vitamins. In large "
            "amounts with fried food it adds saturated fat and calories.",
    "butter": "Butter is high in saturated fat. A little on roti is fine; "
              "don't use it as a spread daily if your cholesterol is high.",
    "coconut oil": "Coconut oil is mostly saturated fat. Fine in moderate "
                   "amounts for cooking; not the best for high-cholesterol "
                   "people.",
    "olive oil": "Olive oil (especially extra virgin) is rich in healthy "
                 "fats — good for salads and light cooking. It has a low "
                 "smoke point; don't deep-fry with it repeatedly.",
    "soyabean oil": "Soybean oil is fine in moderation — rotate oils rather "
                    "than using one all year.",
    "sunflower oil": "Sunflower oil is light and suitable for everyday "
                     "cooking; rotate with groundnut/mustard oil for a "
                     "balance of fats.",
    "groundnut oil": "Groundnut oil is a good Indian cooking oil with a "
                     "decent fat balance. Avoid if you have a peanut "
                     "allergy.",
    "mustard oil": "Mustard oil is traditional and flavourful; use in "
                   "moderation. Check it is 'refined' labelled for regular "
                   "cooking.",

    # --- Sugars & sweeteners ---
    "sugar": "Sugar gives quick energy but too much causes weight gain, "
             "tooth decay and diabetes risk. WHO: under 6 teaspoons/day. "
             "Watch for syrups and 'sugars' on labels too.",
    "high fructose corn syrup": "HFCS is liquid sugar used in soft drinks "
                                "and biscuits — same problems as sugar, "
                                "easy to overconsume. Avoid in drinks.",
    "corn syrup": "Corn syrup is added sugar in liquid form — contributes "
                  "to hidden sugar intake. Check 'sugars' in the nutrition "
                  "panel.",
    "dextrose": "Dextrose is a simple sugar (glucose) — counts as added "
                "sugar. Diabetics should be careful with it.",
    "fructose": "Fructose occurs in fruit (fine) but added fructose in "
                "packaged food is free sugar — limit it.",
    "glucose": "Glucose is fast-acting sugar. Useful for instant energy "
               "(like in ORS during illness), but added glucose in "
               "everyday snacks adds empty calories.",
    "honey": "Honey is still sugar — same calories and effect on blood "
             "sugar. Slightly better than refined sugar in small amounts. "
             "Never give honey to babies under 1 year.",
    "jaggery": "Jaggery (gur) has a little iron and is better than refined "
               "sugar in small amounts — but it is still sugar for "
               "diabetics. 1 teaspoon/day is a reasonable limit.",
    "aspartame": "Aspartame is a low-calorie sweetener approved by food "
                 "safety authorities for general use. People with the rare "
                 "condition PKU must avoid it.",
    "sucralose": "Sucralose is a zero-calorie sweetener considered safe in "
                 "approved amounts; does not raise blood sugar.",
    "stevia": "Stevia is a plant-based zero-calorie sweetener — a better "
              "option than sugar for tea, though processed 'stevia blends' "
              "may still contain sugar.",
    "saccharin": "Saccharin is an old artificial sweetener, approved as "
                 "safe in set limits; best used in moderation.",
    "artificial sweetener": "Artificial sweeteners help cut sugar and "
                            "calories. Approved ones are safe within daily "
                            "limits — don't overdo 'sugar-free' products.",

    # --- Flours & starches ---
    "maida": "Maida is refined wheat flour — low fibre, spikes blood "
             "sugar, found in bread, biscuits, noodles, pizza. Use whole "
             "wheat atta or millet flour instead for daily eating.",
    "refined flour": "Refined flour (maida) digests fast and lacks fibre. "
                     "Occasional is fine — daily use contributes to weight "
                     "gain and sugar spikes.",
    "wheat flour": "Whole wheat flour (atta) retains fibre and is a good "
                   "everyday choice. Check that 'wheat flour' isn't really "
                   "maida in disguise.",
    "corn starch": "Corn starch is a thickener with mostly empty "
                   "carbohydrate — fine in small amounts in sauces and "
                   "custards.",
    "rice flour": "Rice flour is gluten-free and fine in moderation; often "
                  "used in batters and snacks.",

    # --- Preservatives & additives ---
    "sodium benzoate": "Sodium benzoate (E211) is a preservative safe "
                       "within FSSAI limits — it prevents mould in drinks "
                       "and sauces. Very high intake with vitamin C in "
                       "poor storage is best avoided; choose fresh when "
                       "possible.",
    "benzoic acid": "Benzoic acid is a preservative used in pickles and "
                    "drinks — safe within legal limits. Cut back on "
                    "packaged drinks regardless.",
    "potassium sorbate": "Potassium sorbate preserves cheese, baked goods "
                         "and drinks — considered safe within limits.",
    "sorbic acid": "Sorbic acid is a mild preservative against mould and "
                   "yeast — safe within approved limits.",
    "sodium nitrite": "Sodium nitrite preserves processed meat (ham, "
                      "salami, nuggets) and gives pink colour. Frequent "
                      "high intake is linked with health concerns — keep "
                      "processed meat occasional.",
    "sodium nitrate": "Sodium nitrate is used in processed meats; limit "
                      "these foods rather than worry about one serving.",
    "bha": "BHA (E320) is an antioxidant preservative allowed within "
           "limits. Reducing packaged snack intake reduces your exposure.",
    "bht": "BHT (E321) is an antioxidant preservative used in oils and "
           "cereals — approved within set limits.",
    "tbhq": "TBHQ keeps oils and fried snacks from going rancid — safe "
            "within limits, but it means the product is highly processed.",
    "meta bi sulfite": "Sulphites preserve dried fruit and wine; some "
                       "asthma sufferers are sensitive to them.",
    "sulphur dioxide": "Sulphur dioxide preserves dried fruit and juice — "
                       "safe for most; sensitive people/asthmatics should "
                       "be cautious.",
    "polyphosphate": "Polyphosphates keep meat juicy and prevent ice "
                     "crystals — safe within limits.",
    "silicon dioxide": "Silicon dioxide (E551) is an anti-caking powder in "
                       "spices — tiny amounts, no known problem.",
    "titanium dioxide": "Titanium dioxide (E171) is a whitening colour; "
                        "some countries have restricted it — products "
                        "using it are better eaten occasionally.",
    "xanthan gum": "Xanthan gum is a fibre-based thickener — safe, and "
                   "even adds a little soluble fibre.",
    "guar gum": "Guar gum is a natural fibre thickener — safe; can help "
                "with fullness and cholesterol in useful amounts.",
    "lecithin": "Lecithin (E322, often soy) is an emulsifier considered "
                "safe — it keeps chocolate and spreads smooth.",
    "carrageenan": "Carrageenan is a seaweed thickener in milks and "
                   "desserts — approved as safe; some prefer to limit it.",
    "sodium bicarbonate": "Sodium bicarbonate (baking soda) is safe — it "
                          "makes cakes and idlis rise. Uses little sodium "
                          "in the final product.",

    # --- Colours & flavours ---
    "tartrazine": "Tartrazine (E102) is a yellow colour approved within "
                  "limits; a small number of children may be sensitive to "
                  "it — natural colours are a better choice for kids.",
    "sunset yellow": "Sunset yellow (E110) is an orange colour allowed "
                     "within limits; better to choose products with "
                     "natural colours.",
    "allura red": "Allura red (E129) is a red colour approved within "
                  "limits — common in candies; keep such sweets occasional.",
    "ponceau": "Ponceau 4R is a red colour used in sweets/drinks — "
               "approved within limits, best limited for children.",
    "carmoisine": "Carmoisine is a red synthetic colour in jellies and "
                  "sweets — approved within limits; occasional use only.",
    "artificial colour": "Artificial colours are approved within set "
                         "limits, but products heavy in them are usually "
                         "low-nutrition sweets/drinks — restrict them, "
                         "especially for children.",
    "artificial flavour": "Artificial flavours make food taste stronger "
                          "without real ingredients — safe in limits, but "
                          "they signal a highly processed product.",
    "vanilla": "Vanilla flavouring is safe and commonly used in baking.",
    "caffeine": "Caffeine in tea/coffee is fine for most adults (up to "
                "about 3–4 cups/day). It can disturb sleep, raise heart "
                "rate in excess, and should be limited in pregnancy. "
                "Energy drinks are not for children.",

    # --- Proteins & dairy ---
    "casein": "Casein is milk protein — nutritious. It's also used as an "
              "additive; safe, but vegans avoid it.",
    "whey": "Whey is milk protein left after curdling — good quality "
            "protein used in supplements. Safe; whole food sources are "
            "cheaper.",
    "lactose": "Lactose is milk sugar. Intolerant people get bloating — "
               "curd/paneer are usually tolerated better than plain milk.",
    "milk solids": "Milk solids are dried milk — they add protein and "
                   "calcium. Fine for most; check quantity in sweet drinks.",
    "soy": "Soy protein is a good plant protein with all essential amino "
           "acids. Normal amounts in food are fine; avoid soybean oil "
           "allergy concerns if allergic.",
    "soy protein": "Soy protein isolate is a complete plant protein — "
                   "useful for vegetarians; safe in normal amounts.",
    "egg": "Eggs are an excellent protein source with vitamins. One a day "
           "is fine for most healthy people; those with heart disease "
           "should follow their doctor's advice on yolk.",
    "gelatin": "Gelatin is animal protein (bones/skin) — not vegetarian. "
               "Nutritionally it is a partial protein.",
    "peanut": "Peanuts are cheap protein and good fats — a handful a day "
              "is healthy. They can cause severe allergy in some people; "
              "check labels if allergic.",
    "groundnut": "Groundnuts provide protein, fibre and good fats — great "
                 "snack. Roasted unsalted is best.",

    # --- Common food substances ---
    "salt": "Salt provides sodium your body needs, but excess raises blood "
            "pressure. WHO: under 5 g/day including all packaged food. "
            "Read 'sodium' on labels (600 mg sodium ≈ 1.5 g salt).",
    "msg": "MSG (monosodium glutamate, E621) enhances savoury taste. "
           "Approved as safe within limits; a small group feels "
           "headaches after large amounts — sensitive people can avoid it.",
    "sodium": "Sodium comes mostly from salt and additives. High sodium "
              "means BP risk — compare products and pick the lower one.",
    "citric acid": "Citric acid (E330) is a safe natural acid that adds "
                   "tanginess and preserves vitamin C — no concern in "
                   "normal amounts.",
    "ascorbic acid": "Ascorbic acid is vitamin C — used to keep food "
                     "fresh and prevent browning. It's beneficial.",
    "acetic acid": "Acetic acid (vinegar) is safe and used for pickling "
                   "and flavour.",
    "lactic acid": "Lactic acid is safe — produced naturally in curd and "
                   "used to preserve and flavour foods.",
    "caffeine": "Caffeine in tea/coffee is fine in moderation (3–4 cups/day "
                "for adults). Avoid in children and limit in pregnancy. "
                "Energy drinks can contain very high amounts.",
    "fibre": "Fibre (from whole grains, dal with skin, vegetables, fruit) "
             "improves digestion, controls sugar and cholesterol. Most "
             "Indians don't get enough — aim for vegetables at every meal.",
    "omega": "Omega-3 fats (walnuts, flaxseed/alsi, mustard oil, fish) "
             "support heart and brain health. Include a source daily.",
    "protein": "Protein builds and repairs the body. Include a source at "
               "every meal: dal, curd, paneer, milk, soya, egg. Roughly "
               "0.8–1 g per kg body weight daily.",
    "vitamin c": "Vitamin C (amla, lemon, orange, tomato, capsicum) "
                 "boosts immunity and helps absorb iron from dal and "
                 "palak.",
    "iron": "Iron prevents anaemia — sources: palak, dates, ragi, "
            "jaggery, dal. Take with vitamin C; avoid tea at meals.",
    "calcium": "Calcium for bones: milk, curd, ragi, til, green veg. "
               "Pair with sunlight/vitamin D for absorption.",
    "preservative": "Preservatives keep packaged food from spoiling — "
                    "safe within FSSAI limits. Long lists of them mean "
                    "highly processed food; eat such items less often.",
    "emulsifier": "Emulsifiers keep oil and water mixed (in chocolate, "
                  "spreads). Approved for use; they also mark a product "
                  "as processed.",
    "stabiliser": "Stabilisers keep textures uniform — approved in set "
                  "limits and not a health concern in normal amounts.",
    "thickener": "Thickeners give body to sauces and drinks — generally "
                 "safe; natural ones (xanthan, guar) add a little fibre.",
    "antioxidant": "Antioxidant additives (BHA, BHT, TBHQ) stop oils "
                   "going stale — safe within limits.",
    "raising agent": "Raising agents (baking powder/soda) make baked "
                     "goods rise — safe.",
    "flour": "Refined flour (maida) is low in fibre — prefer whole wheat "
             "or millet flour for daily rotis.",
    "oats": "Oats are a high-fibre whole grain — good for cholesterol and "
            "keeping full. Choose plain oats, not instant flavoured ones "
            "loaded with sugar.",
    "millet": "Millets (ragi, jowar, bajra) are fibre-rich, low-GI "
              "superfoods — better than rice for diabetics and great for "
              "everyone.",
    "ragi": "Ragi (finger millet) is rich in calcium and iron — excellent "
            "for children, elders and diabetics.",
    "paneer": "Paneer gives protein and calcium for vegetarians — about "
              "25–30 g per meal is a good portion.",
    "curd": "Curd has protein, calcium and gut-friendly bacteria — a bowl "
            "daily aids digestion and immunity.",
    "pickles": "Pickles are very high in salt and oil — use a teaspoon "
               "with meals, not a bowl. BP patients should be careful.",
    "papad": "Papad is high in salt; one with a meal is fine, more adds "
             "up quickly.",
    "chips": "Chips are fried, salty and high in calorie with few "
             "nutrients — swap for roasted chana or makhana.",
    "biscuit": "Most biscuits are maida + sugar + oil — they look small "
               "but add up. Check 'per serving' numbers; 2 biscuits can "
               "equal 2 teaspoons of sugar.",
    "noodle": "Instant noodles are maida with high salt and palm oil and "
              "little nutrition. Make them occasional; add vegetables and "
              "an egg/paneer if you do.",
    "cold drink": "Cold drinks are liquid sugar — one glass can have 6–8 "
                  "teaspoons. Switch to buttermilk, lemon water or plain "
                  "water.",
    "juice": "Packaged juice lacks the fibre of whole fruit and has "
             "added sugar — eat the fruit instead.",
    "jam": "Jam is mostly sugar with a little fruit — a thin layer "
           "occasionally, not thick daily spreads.",
    "chocolate": "Dark chocolate (70%+) in small amounts can be fine; "
                 "milk/white chocolate is mostly sugar and fat.",
    "ice cream": "Ice cream adds sugar, fat and calories — a small scoop "
                 "occasionally is fine.",
    "bread": "Check bread labels: 'whole wheat bread' is better than "
             "white bread (maida). Some breads have added sugar too.",
    "corn flakes": "Plain corn flakes are okay but many are sugar-coated "
                   "— read the 'sugars' line before buying.",
    "energy drink": "Energy drinks are high caffeine + sugar — not for "
                    "children or daily use.",
    "soft drink": "Soft drinks offer only sugar and no nutrition — the "
                  "easiest thing to cut for your health.",
}


# Greeting / small-talk replies (offline)
SMALL_TALK = {
    "hi": "Hello! 👋 I'm NutriBot. Ask me anything about health, nutrition "
          "or food ingredients.",
    "hello": "Hi there! 👋 Ask me about ingredients, nutrition, healthy "
             "alternatives or your scan grade.",
    "hey": "Hey! 👋 How can I help with your food and health questions?",
    "thanks": "You're welcome! 😊 Stay healthy — ask me anything anytime.",
    "thank you": "You're welcome! 😊 Stay healthy — ask me anything anytime.",
    "bye": "Goodbye! 👋 Take care of your health.",
    "goodbye": "Goodbye! 👋 Take care of your health.",
}


# E-numbers printed on labels -> ingredient name
E_NUMBERS = {
    "e102": "tartrazine", "e110": "sunset yellow", "e122": "carmoisine",
    "e124": "ponceau", "e129": "allura red", "e171": "titanium dioxide",
    "e211": "sodium benzoate", "e220": "sulphur dioxide",
    "e223": "meta bi sulfite", "e250": "sodium nitrite",
    "e251": "sodium nitrate", "e300": "ascorbic acid", "e330": "citric acid",
    "e322": "lecithin", "e320": "bha", "e321": "bht", "e319": "tbhq",
    "e412": "guar gum", "e415": "xanthan gum", "e407": "carrageenan",
    "e415": "xanthan gum", "e451": "polyphosphate", "e500": "sodium bicarbonate",
    "e551": "silicon dioxide", "e621": "msg", "e951": "aspartame",
    "e954": "saccharin", "e955": "sucralose", "e960": "stevia",
}

# One searchable knowledge base: ingredient facts + full health topics
# (health topic wins when both cover the same word - answers are richer)
KNOWLEDGE_BASE = dict(INGREDIENT_FACTS)
KNOWLEDGE_BASE.update(HEALTH_TOPICS)


def offline_answer(question, grade="", matched=None, keywords=None):
    """
    Instant rule-based answer from the built-in health knowledge base.
    Covers all health topics AND ingredient health facts.
    Returns an answer string, or None if no topic matches.
    """
    q = (question or "").strip().lower()
    if not q:
        return None

    # Small talk
    for key, reply in SMALL_TALK.items():
        if q in (key, key + "!") or q == key:
            return reply

    # Medical red-flag words -> always remind to see a doctor
    red_flags = [
        "diagnose", "medicine", "tablet", "dose", "prescription",
        "cancer", "chest pain", "breathing", "fainting",
    ]

    matched_names = []
    if matched:
        matched_names = [
            str(m.get("ingredient", "")).strip().lower()
            for m in matched
            if m.get("ingredient")
        ]

    answer = None
    heading = ""

    # ------------------------------------------------
    # 1) E-number on the label (e.g. "E322", "e 621")
    # ------------------------------------------------
    import re
    e_match = re.search(r"\be\s?(\d{3,4})\b", q)
    if e_match:
        ecode = "e" + e_match.group(1)
        name = E_NUMBERS.get(ecode)
        if name and name in INGREDIENT_FACTS:
            answer = INGREDIENT_FACTS[name]
            heading = f"**{ecode.upper()} = {name}**\n\n"

    # ------------------------------------------------
    # 2) Ingredient / topic named in the question
    # ------------------------------------------------
    if answer is None:
        best_key, best_len = None, 0
        for key in KNOWLEDGE_BASE:
            if key in q and len(key) > best_len:
                best_key, best_len = key, len(key)
        if best_key:
            answer = KNOWLEDGE_BASE[best_key]

    # ------------------------------------------------
    # 3) Ingredient inside the user's scanned product
    # ------------------------------------------------
    if answer is None:
        for name in matched_names:
            if name in INGREDIENT_FACTS:
                answer = INGREDIENT_FACTS[name]
                heading = f"**In your product: {name}**\n\n"
                break

    # ------------------------------------------------
    # 4) General food question
    # ------------------------------------------------
    if answer is None and any(
        pat in q for pat in [
            "is this healthy", "is it healthy", "good for health",
            "safe", "harmful", "side effect", "benefit", "can i eat",
        ]
    ):
        names = ", ".join(n for n in matched_names[:6] if n)
        answer = (
            "**General view:** check how much of the product you eat — "
            "even good ingredients in large daily amounts can add up "
            "(salt, sugar, fat). Look at the nutrition panel per 100 g, "
            "choose products with shorter ingredient lists, and keep "
            "packaged food as part of a diet rich in fruit, vegetables "
            "and dal."
        )
        if names:
            answer += f"\n\nIngredients found in your product: {names}."
        answer += (
            "\n\nAsk me about any specific ingredient for its health effect."
        )

    # ------------------------------------------------
    # 5) Yes/no question about a scanned ingredient
    # ------------------------------------------------
    if answer is None and matched_names and any(
        w in q for w in ["should i", "avoid", "eat this", "buy this",
                         "healthy", "harmful", "safe"]
    ):
        fact_key = next(
            (n for n in matched_names if n in INGREDIENT_FACTS), None
        )
        if fact_key:
            answer = INGREDIENT_FACTS[fact_key]
            heading = f"**In your product: {fact_key}**\n\n"

    if answer:
        if grade:
            answer += f"\n\n**Your scan:** this product got grade **{grade}**."
        if keywords:
            answer += "\n⚠️ Your product contains: " + ", ".join(keywords[:6]) + "."
        if any(flag in q for flag in red_flags):
            answer += (
                "\n\n⚠️ **This is general information only. "
                "Please consult a qualified doctor for diagnosis and "
                "treatment.**"
            )
        return heading + answer

    return None
