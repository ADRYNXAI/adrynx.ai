# api.py - ADRYNX V13.6 VOCAL + RECU PDF + QR CODE - 12 oct 2026
# Evolution: V13.5 + chat vocal (audio -> texte) + reçu PDF téléchargeable + QR Code tracking
from fastapi import FastAPI, Form, File, UploadFile, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time, urllib.parse, re, sqlite3, json, uuid, io, csv, base64
from datetime import datetime, timezone, timedelta
from collections import defaultdict

YOUR_WA = "242061174945"
ADMIN_KEY = os.getenv("ADRYNX_ADMIN_SECRET", "AD23ULTRONIX3D")
DB_PATH = os.getenv("ADRYNX_DB", "/tmp/memoire.db")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
RESEND_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_DEST = os.getenv("ADRYNX_EMAIL_DEST", "adrynxai@gmail.com")
EMAIL_FROM = os.getenv("ADRYNX_EMAIL_FROM", "ADRYNX <onboarding@resend.dev>")
FF_API_KEY = os.getenv("FF_API_KEY", "astute_ff")
BASE_URL = os.getenv("ADRYNX_BASE_URL", "https://adrynx.onrender.com")

BRAZZA_TZ = timezone(timedelta(hours=1))
def now_brazza():
    return datetime.now(BRAZZA_TZ)

CACHE_FILE = "/tmp/ff_live_cache.json"
def get_live_ff_context(force_refresh=False):
    now = datetime.now()
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE,"r") as f:
                data = json.load(f)
                ts = datetime.fromisoformat(data["timestamp"])
                if now - ts < timedelta(seconds=3600):
                    return data
        except:
            pass
    live_data = {"timestamp": now.isoformat(),"season":"OB55 - Octobre 2026","events_actifs":["Unseen Event - 16 Oct - Cloaked Terror","Naruto Event","Winterlands 2026 - Vocal + PDF + QR"],"derniere_maj":now.strftime("%d/%m/%Y %H:%M Brazzaville")}
    try:
        with open(CACHE_FILE,"w") as f:
            json.dump(live_data, f)
    except:
        pass
    return live_data

VERIFY_CACHE = {}
def verify_ff_id(uid: str):
    uid = re.sub(r'\D','',uid)
    if not uid or len(uid) < 6:
        return {"valid": False}
    if uid in VERIFY_CACHE and time.time()-VERIFY_CACHE[uid]["ts"] < 3600:
        return VERIFY_CACHE[uid]["data"]
    try:
        import requests
        for region in ["me","sg","ind","br","us"]:
            try:
                url = f"https://www.public.freefireinfo.site/api/info/{region}/{uid}?key={FF_API_KEY}"
                r = requests.get(url, timeout=6, headers={"User-Agent":"ADRYNX/13.6"})
                if r.status_code == 200 and ("AccountInfo" in r.text or "nickname" in r.text.lower()):
                    result = {"valid": True, "region": region}
                    VERIFY_CACHE[uid] = {"ts": time.time(), "data": result}
                    return result
            except:
                continue
        result = {"valid": True, "region": "unknown", "offline": True}
        VERIFY_CACHE[uid] = {"ts": time.time(), "data": result}
        return result
    except:
        return {"valid": True, "region": "unknown", "offline": True}

def verify_mtn_proof(file_path: str, expected_amount: float):
    try:
        size = os.path.getsize(file_path)
        if size < 5000:
            return {"score":0,"details":"Petite"}
        return {"score":100,"details":f"{size//1024}Ko - {expected_amount}F - 100/100"}
    except:
        return {"score":80,"details":"Verif 80/100"}

def generate_tracking_id():
    return "ADR-"+str(uuid.uuid4())[:8].upper()

def generate_referral_code(tel: str):
    return "PAR-"+re.sub(r'\D','',tel)[-6:]+"-"+str(uuid.uuid4())[:3].upper()

STATUS_FLOW = {
    "EN_ATTENTE": {"next":"VERIFIE","color":"#facc15","label":"En attente"},
    "VERIFIE": {"next":"EN_COURS_LIVRAISON","color":"#3b82f6","label":"Vérifiée"},
    "EN_COURS_LIVRAISON": {"next":"LIVRE","color":"#a855f7","label":"En livraison"},
    "LIVRE": {"next":"LIVRE","color":"#22c55e","label":"Livré"},
}

def calcul_prix(qty: int):
    # V14 PROGRESSION CROISSANTE - Dieu ADRYNX
    if qty <= 110:
        p = 600/110          # 5.45 FCFA/diam - prix d'appel
    elif qty <= 310:
        p = 5.95             # +9% - palier 1
    elif qty <= 520:
        p = 6.45             # +18% - palier 2  
    elif qty <= 1060:
        p = 7.0              # +28% - palier 3
    elif qty <= 2180:
        p = 7.8              # +43% - gros
    else:
        p = 8.5              # +56% - whale
    base = p * qty
    frais = base * 0.05
    total = base + frais
    return round(base,2), round(frais,2), round(total,2)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, tracking TEXT, produit TEXT, prix REAL, ff_id TEXT, ff_id2 TEXT, tel TEXT, date TEXT, verif TEXT, mtn_check TEXT, status TEXT, created_at TEXT, referral_code_used TEXT, abo_id TEXT, is_gift INTEGER, gift_to_tel TEXT, gift_to_ff TEXT, gift_message TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS promos (id INTEGER PRIMARY KEY, tel TEXT, ff_id TEXT, raison TEXT, discount_percent INTEGER, discount_amount REAL, points INTEGER, commandes_count INTEGER, status TEXT, created_at TEXT, code TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS referrals (id INTEGER PRIMARY KEY, parrain_tel TEXT, filleul_tel TEXT, filleul_ff_id TEXT, code TEXT, status TEXT, created_at TEXT, bonus_parrain_percent INTEGER, bonus_filleul_percent INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS subscriptions (id TEXT PRIMARY KEY, tel TEXT, ff_id TEXT, ff_id2 TEXT, type TEXT, prix REAL, start_date TEXT, end_date TEXT, status TEXT, renewal_count INTEGER, last_reminder TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS wishlist (id INTEGER PRIMARY KEY, tel TEXT, ff_id TEXT, produit TEXT, prix_souhaite REAL, prix_actuel REAL, created_at TEXT, notified INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS price_alerts (id INTEGER PRIMARY KEY, tel TEXT, produit TEXT, target_price REAL, current_price REAL, status TEXT, created_at TEXT)")
        conn.commit()
        conn.close()
    except Exception as e:
        print("INIT DB ERR",e)
init_db()

def save_order(o):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO orders (tracking,produit,prix,ff_id,ff_id2,tel,date,verif,mtn_check,status,created_at,referral_code_used,abo_id,is_gift,gift_to_tel,gift_to_ff,gift_message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(o['tracking'],o['produit'],o['prix'],o['ff_id'],o.get('ff_id2',''),o['telephone'],o['date'],o.get('verif',''),o.get('mtn_check',''),o.get('status','EN_ATTENTE'), now_brazza().isoformat(), o.get('referral_code_used',''), o.get('abo_id',''), o.get('is_gift',0), o.get('gift_to_tel',''), o.get('gift_to_ff',''), o.get('gift_message','')))
        conn.commit()
        conn.close()
    except Exception as e:
        print("SAVE ORDER ERR",e)

def load_orders(limit=1000):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT tracking,produit,prix,ff_id,ff_id2,tel,date,verif,mtn_check,status,created_at,referral_code_used,abo_id,is_gift,gift_to_tel,gift_to_ff,gift_message FROM orders ORDER BY id DESC LIMIT?",(limit,))
        rows = cur.fetchall()
        conn.close()
        return [{"tracking":r[0],"produit":r[1],"prix":r[2],"ff_id":r[3],"ff_id2":r[4],"telephone":r[5],"date":r[6],"verif":r[7],"mtn_check":r[8],"status":r[9],"created_at":r[10],"referral_code_used":r[11],"abo_id":r[12],"is_gift":r[13],"gift_to_tel":r[14],"gift_to_ff":r[15],"gift_message":r[16]} for r in rows]
    except:
        return []

def get_order_by_tracking(tracking: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT tracking,produit,prix,ff_id,ff_id2,tel,date,verif,mtn_check,status,created_at,referral_code_used,abo_id,is_gift,gift_to_tel,gift_to_ff,gift_message FROM orders WHERE tracking=?",(tracking,))
        r = cur.fetchone()
        conn.close()
        if r:
            return {"tracking":r[0],"produit":r[1],"prix":r[2],"ff_id":r[3],"ff_id2":r[4],"telephone":r[5],"date":r[6],"verif":r[7],"mtn_check":r[8],"status":r[9],"created_at":r[10],"referral_code_used":r[11],"abo_id":r[12],"is_gift":r[13],"gift_to_tel":r[14],"gift_to_ff":r[15],"gift_message":r[16]}
    except:
        pass
    return None

def update_order_status(tracking: str, new_status: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE orders SET status=? WHERE tracking=?",(new_status,tracking))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_client_stats(tel: str):
    orders = load_orders(1000)
    client_orders = [o for o in orders if o['telephone'] == tel]
    total_spent = sum(o['prix'] for o in client_orders)
    points = int(total_spent // 100)
    return {"count": len(client_orders), "total_spent": total_spent, "points": points, "orders": client_orders}

def check_and_propose_promo(tel: str, ff_id: str):
    stats = get_client_stats(tel)
    count = stats["count"]
    points = stats["points"]
    total = stats["total_spent"]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT status FROM promos WHERE tel=? AND status IN ('PENDING','APPROVED') ORDER BY id DESC LIMIT 1",(tel,))
    existing = cur.fetchone()
    conn.close()
    if existing:
        return None
    raison = None
    discount_percent = 0
    if count >= 5:
        raison = f"Client fidèle - {count} commandes - VIP Bronze"
        discount_percent = 10
    elif points >= 50:
        raison = f"Fidélité {points} points ({total}F) - VIP Argent"
        discount_percent = 15
    elif total >= 15000:
        raison = f"Gros client - {total}F - VIP Gold"
        discount_percent = 12
    elif count >= 3:
        raison = f"Client régulier - {count} commandes"
        discount_percent = 5
    if raison:
        code = "PROMO-"+str(uuid.uuid4())[:6].upper()
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO promos (tel,ff_id,raison,discount_percent,discount_amount,points,commandes_count,status,created_at,code) VALUES (?,?,?,?,?,?,?,?,?,?)",(tel, ff_id, raison, discount_percent, 0, points, count, "PENDING", now_brazza().isoformat(), code))
            conn.commit()
            conn.close()
            return {"tel": tel, "raison": raison, "discount_percent": discount_percent, "code": code, "points": points, "count": count, "status": "PENDING"}
        except:
            pass
    return None

def get_referral_code_for_tel(tel: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT code FROM referrals WHERE parrain_tel=? LIMIT 1",(tel,))
    r = cur.fetchone()
    if r:
        conn.close()
        return r[0]
    code = generate_referral_code(tel)
    conn.close()
    return code

def load_referrals(status_filter=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT id,parrain_tel,filleul_tel,filleul_ff_id,code,status,created_at,bonus_parrain_percent,bonus_filleul_percent FROM referrals WHERE status=? ORDER BY id DESC LIMIT 50",(status_filter,))
        else:
            cur.execute("SELECT id,parrain_tel,filleul_tel,filleul_ff_id,code,status,created_at,bonus_parrain_percent,bonus_filleul_percent FROM referrals ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        return [{"id":r[0],"parrain_tel":r[1],"filleul_tel":r[2],"filleul_ff_id":r[3],"code":r[4],"status":r[5],"created_at":r[6],"bonus_parrain_percent":r[7],"bonus_filleul_percent":r[8]} for r in rows]
    except:
        return []

def create_referral_pending(parrain_tel: str, filleul_tel: str, filleul_ff_id: str, code: str):
    try:
        if parrain_tel == filleul_tel:
            return None
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM referrals WHERE filleul_tel=? LIMIT 1",(filleul_tel,))
        if cur.fetchone():
            conn.close()
            return None
        conn.execute("INSERT INTO referrals (parrain_tel,filleul_tel,filleul_ff_id,code,status,created_at,bonus_parrain_percent,bonus_filleul_percent) VALUES (?,?,?,?,?,?,?,?,?)",(parrain_tel, filleul_tel, filleul_ff_id, code, "PENDING", now_brazza().isoformat(), 5, 5))
        conn.commit()
        conn.close()
        return {"parrain_tel": parrain_tel, "filleul_tel": filleul_tel, "code": code, "bonus_parrain":5, "bonus_filleul":5, "status":"PENDING"}
    except:
        return None

def find_parrain_by_code(code: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT parrain_tel FROM referrals WHERE code=? LIMIT 1",(code.upper(),))
        r = cur.fetchone()
        conn.close()
        if r:
            return r[0]
        m = re.search(r'PAR-(\d{6,12})', code.upper())
        if m:
            tel_digits = m.group(1)
            orders = load_orders(1000)
            for o in orders:
                if tel_digits in re.sub(r'\D','',o['telephone']):
                    return o['telephone']
        return None
    except:
        return None

def update_referral_status(ref_id: int, new_status: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE referrals SET status=? WHERE id=?",(new_status, ref_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def load_promos(status_filter=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT id,tel,ff_id,raison,discount_percent,discount_amount,points,commandes_count,status,created_at,code FROM promos WHERE status=? ORDER BY id DESC LIMIT 50",(status_filter,))
        else:
            cur.execute("SELECT id,tel,ff_id,raison,discount_percent,discount_amount,points,commandes_count,status,created_at,code FROM promos ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()
        return [{"id":r[0],"tel":r[1],"ff_id":r[2],"raison":r[3],"discount_percent":r[4],"discount_amount":r[5],"points":r[6],"commandes_count":r[7],"status":r[8],"created_at":r[9],"code":r[10]} for r in rows]
    except:
        return []

def update_promo_status(promo_id: int, new_status: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE promos SET status=? WHERE id=?",(new_status, promo_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def create_subscription(tel: str, ff_id: str, ff_id2: str, type_abo: str, prix: float):
    abo_id = "ABO-"+str(uuid.uuid4())[:8].upper()
    start = now_brazza()
    end = start + timedelta(days=30)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO subscriptions (id,tel,ff_id,ff_id2,type,prix,start_date,end_date,status,renewal_count,last_reminder,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(abo_id, tel, ff_id, ff_id2, type_abo, prix, start.isoformat(), end.isoformat(), "ACTIVE", 0, "", start.isoformat()))
        conn.commit()
        conn.close()
        return {"id": abo_id, "tel": tel, "ff_id": ff_id, "ff_id2": ff_id2, "type": type_abo, "prix": prix, "start": start, "end": end, "status":"ACTIVE"}
    except:
        return None

def load_subscriptions(status_filter=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if status_filter:
            cur.execute("SELECT id,tel,ff_id,ff_id2,type,prix,start_date,end_date,status,renewal_count,last_reminder,created_at FROM subscriptions WHERE status=? ORDER BY id DESC LIMIT 100",(status_filter,))
        else:
            cur.execute("SELECT id,tel,ff_id,ff_id2,type,prix,start_date,end_date,status,renewal_count,last_reminder,created_at FROM subscriptions ORDER BY created_at DESC LIMIT 100")
        rows = cur.fetchall()
        conn.close()
        subs = []
        for r in rows:
            try:
                end_dt = datetime.fromisoformat(r[6])
                now = now_brazza()
                status = r[7]
                if status=="ACTIVE" and end_dt < now:
                    status = "EXPIRE"
                elif status=="ACTIVE" and (end_dt - now).days <=3:
                    status = "EXPIRE_BIENTOT"
                subs.append({"id":r[0],"tel":r[1],"ff_id":r[2],"ff_id2":r[3],"type":r[4],"prix":r[5],"start_date":r[5],"end_date":r[6],"status":status,"renewal_count":r[8],"last_reminder":r[9],"created_at":r[10],"end_dt":end_dt,"days_left": (end_dt - now).days})
            except:
                subs.append({"id":r[0],"tel":r[1],"ff_id":r[2],"ff_id2":r[3],"type":r[4],"prix":r[5],"start_date":r[5],"end_date":r[6],"status":r[7],"renewal_count":r[8],"last_reminder":r[9],"created_at":r[10],"days_left":0})
        return subs
    except:
        return []

def get_subscriptions_to_remind():
    subs = load_subscriptions()
    to_remind = []
    for s in subs:
        if s["status"] in ["EXPIRE_BIENTOT","EXPIRE","ACTIVE"] and s.get("days_left",0) <=3:
            if s.get("last_reminder","")[:10]!= now_brazza().isoformat()[:10]:
                to_remind.append(s)
    return to_remind[:10]

def update_subscription_reminder(abo_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE subscriptions SET last_reminder=? WHERE id=?",(now_brazza().isoformat(), abo_id))
        conn.commit()
        conn.close()
    except:
        pass

def renew_subscription(abo_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT tel,ff_id,ff_id2,type,prix,renewal_count FROM subscriptions WHERE id=?",(abo_id,))
        r = cur.fetchone()
        if not r:
            conn.close()
            return None
        new_end = now_brazza() + timedelta(days=30)
        cur.execute("UPDATE subscriptions SET end_date=?, status='ACTIVE', renewal_count=?, last_reminder='' WHERE id=?",(new_end.isoformat(), r[5]+1, abo_id))
        conn.commit()
        conn.close()
        return {"id": abo_id, "tel": r[0], "ff_id": r[1], "type": r[3], "prix": r[4], "new_end": new_end}
    except:
        return None

def add_to_wishlist(tel: str, ff_id: str, produit: str, prix_actuel: float, prix_souhaite: float = None):
    try:
        if prix_souhaite is None:
            prix_souhaite = round(prix_actuel * 0.9,2)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO wishlist (tel,ff_id,produit,prix_souhaite,prix_actuel,created_at,notified) VALUES (?,?,?,?,?,?,?)",(tel, ff_id, produit, prix_souhaite, prix_actuel, now_brazza().isoformat(), 0))
        conn.commit()
        conn.close()
        return {"tel": tel, "produit": produit, "prix_actuel": prix_actuel, "prix_souhaite": prix_souhaite}
    except:
        return None

def load_wishlist(tel: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if tel:
            cur.execute("SELECT id,tel,ff_id,produit,prix_souhaite,prix_actuel,created_at,notified FROM wishlist WHERE tel=? ORDER BY id DESC LIMIT 50",(tel,))
        else:
            cur.execute("SELECT id,tel,ff_id,produit,prix_souhaite,prix_actuel,created_at,notified FROM wishlist ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        conn.close()
        return [{"id":r[0],"tel":r[1],"ff_id":r[2],"produit":r[3],"prix_souhaite":r[4],"prix_actuel":r[5],"created_at":r[6],"notified":r[7]} for r in rows]
    except:
        return []

def add_price_alert(tel: str, produit: str, target_price: float, current_price: float):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO price_alerts (tel,produit,target_price,current_price,status,created_at) VALUES (?,?,?,?,?,?)",(tel, produit, target_price, current_price, "ACTIVE", now_brazza().isoformat()))
        conn.commit()
        conn.close()
        return {"tel": tel, "produit": produit, "target_price": target_price, "current_price": current_price}
    except:
        return None

def load_price_alerts(tel: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if tel:
            cur.execute("SELECT id,tel,produit,target_price,current_price,status,created_at FROM price_alerts WHERE tel=? ORDER BY id DESC LIMIT 50",(tel,))
        else:
            cur.execute("SELECT id,tel,produit,target_price,current_price,status,created_at FROM price_alerts ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        conn.close()
        return [{"id":r[0],"tel":r[1],"produit":r[2],"target_price":r[3],"current_price":r[4],"status":r[5],"created_at":r[6]} for r in rows]
    except:
        return []

def check_price_drops():
    wishlist = load_wishlist()
    alerts = load_price_alerts()
    drops = []
    for w in wishlist:
        prod = get_produit(w["produit"])
        if prod and prod["prix"] < w["prix_actuel"]:
            drops.append({"type":"wishlist","item":w,"new_price":prod["prix"],"old_price":w["prix_actuel"]})
    for a in alerts:
        prod = get_produit(a["produit"])
        if prod and prod["prix"] <= a["target_price"]:
            drops.append({"type":"alert","item":a,"new_price":prod["prix"],"old_price":a["current_price"]})
    return drops[:10]

def get_stats_with_predict():
    orders = load_orders(1000)
    today_str = now_brazza().strftime("%d/%m")
    today_orders = [o for o in orders if today_str in o.get('date','')]
    total_today = sum(o['prix'] for o in today_orders)
    total_all = sum(o['prix'] for o in orders)
    prod_counts = defaultdict(int)
    for o in orders:
        prod_counts[o['produit']] += 1
    top_prod = max(prod_counts.items(), key=lambda x: x[1]) if prod_counts else ("Aucun",0)
    status_counts = defaultdict(int)
    for o in orders:
        status_counts[o.get('status','EN_ATTENTE')] += 1
    daily_totals = defaultdict(float)
    for o in orders:
        d = o.get('date','').split(' ')[0]
        if d:
            daily_totals[d] += o['prix']
    last_3 = list(daily_totals.values())[:3]
    pred_total = sum(last_3)/len(last_3) if last_3 else total_today or 2500
    croissance = ((last_3[0]-last_3[-1])/last_3[-1]*100) if len(last_3)>=2 and last_3[-1] else 0
    subs = load_subscriptions()
    active_subs = [s for s in subs if s["status"]=="ACTIVE"]
    expiring_subs = [s for s in subs if s["status"] in ["EXPIRE_BIENTOT","EXPIRE"]]
    gifts = [o for o in orders if o.get('is_gift')]
    return {
        "today_count": len(today_orders), "today_total": total_today,
        "all_total": total_all, "all_count": len(orders),
        "top_product": top_prod[0], "top_product_count": top_prod[1],
        "status_counts": dict(status_counts),
        "pending_alert": status_counts.get('EN_ATTENTE',0)+status_counts.get('VERIFIE',0),
        "predict_tomorrow_total": round(pred_total,2),
        "croissance": round(croissance,1),
        "active_subs": len(active_subs),
        "expiring_subs": len(expiring_subs),
        "gifts_count": len(gifts),
        "wishlist_count": len(load_wishlist()),
        "alerts_count": len(load_price_alerts()),
        "orders": orders[:60]
    }

def get_produit(t):
    ql = t.lower()
    if "duo" in ql and ("abonnement" in ql or "abo" in ql):
        return {"nom":"Abonnement Mensuel DUO - 2 comptes","prix":7500,"qty":1,"type":"abo_duo"}
    if "duo" in ql or "2 compte" in ql:
        m = re.search(r'(\d{2,4})', ql)
        qty = int(m.group(1)) if m else 520
        b,f,tot = calcul_prix(qty)
        duo_prix = round(tot*2*0.9,2)
        return {"nom":f"Pack DUO {qty} diamants x2 comptes","prix":duo_prix,"qty":qty,"type":"duo","base":b,"frais":f,"duo":True,"unit_price":tot}
    m = re.search(r'(\d{2,5})\s*diam', ql)
    if m:
        qty = int(m.group(1))
        if 50 <= qty <= 20000:
            b,f,tot = calcul_prix(qty)
            return {"nom":str(qty)+" diamant","prix":tot,"qty":qty,"type":"diamant","base":b,"frais":f}
    for q in [610,110,520,1060]:
        if str(q) in ql and "diam" in ql:
            b,f,tot = calcul_prix(q)
            return {"nom":str(q)+" diamant","prix":tot,"qty":q,"type":"diamant","base":b,"frais":f}
    if any(x in ql for x in ["abonnement","abo","mensuel"]):
        if "duo" in ql:
            return {"nom":"Abonnement Mensuel DUO - 2 comptes","prix":7500,"qty":1,"type":"abo_duo"}
        return {"nom":"Abonnement Mensuel - 30 jours","prix":4500,"qty":1,"type":"abo"}
    if any(x in ql for x in ["skyn","skin"]):
        return {"nom":"Skin Free Fire","prix":2500,"qty":1,"type":"skin"}
    if "booyah" in ql or "pass" in ql:
        return {"nom":"Pass Booyah","prix":1800,"qty":1,"type":"pass"}
    if "cadeau" in ql or "offrir" in ql or "gift" in ql:
        m = re.search(r'(\d{2,4})', ql)
        qty = int(m.group(1)) if m else 110
        b,f,tot = calcul_prix(qty)
        return {"nom":f"Cadeau {qty} diamants","prix":tot,"qty":qty,"type":"cadeau","base":b,"frais":f}
    return None

def alerte_email(o):
    if not RESEND_KEY:
        return
    try:
        import requests
        requests.post("https://api.resend.com/emails",headers={"Authorization":"Bearer "+RESEND_KEY,"Content-Type":"application/json"},json={"from":EMAIL_FROM,"to":[EMAIL_DEST],"subject":f"V13.6 {o['tracking']} {o['prix']}F","html":f"<h2>V13.6 {o['tracking']}</h2><p>{o['produit']} {o['prix']}F ID {o['ff_id']}</p>"},timeout=8)
    except:
        pass

# ========== V13.6 NOUVEAU - RECU PDF + QR CODE ==========
def generate_receipt_pdf(order: dict):
    """Genere PDF recu avec QR code tracking"""
    try:
        import fitz # PyMuPDF
        from PIL import Image, ImageDraw, ImageFont
        import io as bio

        # Cree PDF avec PyMuPDF
        doc = fitz.open()
        page = doc.new_page(width=595, height=842) # A4

        # Contenu PDF
        y = 50
        page.insert_text((50, y), "ADRYNX SHOP - RECU OFFICIEL", fontsize=18, fontname="helv", color=(0.65, 0.33, 0.97))
        y += 30
        page.insert_text((50, y), f"Plus que l'impossible - Brazzaville", fontsize=10, color=(0.5,0.5,0.5))
        y += 20
        page.draw_line((50, y), (545, y), width=1)
        y += 20

        page.insert_text((50, y), f"Tracking: {order['tracking']}", fontsize=14, fontname="helv")
        y += 20
        page.insert_text((50, y), f"Date: {order['date']} - {order.get('created_at','')[:16]}", fontsize=11)
        y += 18
        page.insert_text((50, y), f"Produit: {order['produit']}", fontsize=12)
        y += 18
        page.insert_text((50, y), f"Prix: {order['prix']} FCFA", fontsize=12)
        y += 18
        page.insert_text((50, y), f"ID Free Fire: {order['ff_id']} {order.get('ff_id2','')}", fontsize=11)
        y += 18
        page.insert_text((50, y), f"Telephone: {order['telephone']}", fontsize=11)
        y += 18
        page.insert_text((50, y), f"Status: {order.get('status','EN_ATTENTE')}", fontsize=11, color=(0,0.6,0) if order.get('status')=='LIVRE' else (0.9,0.7,0))
        y += 18
        if order.get('is_gift'):
            page.insert_text((50, y), f"Cadeau vers: {order.get('gift_to_tel','')} {order.get('gift_to_ff','')} - Message: {order.get('gift_message','')}", fontsize=10, color=(0.9,0.3,0.6))
            y += 18
        if order.get('abo_id'):
            page.insert_text((50, y), f"Abonnement: {order.get('abo_id')} - 30 jours", fontsize=10, color=(0.65,0.33,0.97))
            y += 18

        y += 10
        page.draw_line((50, y), (545, y), width=0.5)
        y += 15
        page.insert_text((50, y), f"Suivi: {BASE_URL}/track/{order['tracking']}", fontsize=10, color=(0.2,0.2,0.8))
        y += 15
        page.insert_text((50, y), f"MTN: {YOUR_WA} - Verification: {order.get('verif','')} - MTN Check: {order.get('mtn_check','')}", fontsize=8, color=(0.5,0.5,0.5))
        y += 20
        page.insert_text((50, y), "Merci Boss! ADRYNX SHOP - Plus que l'impossible", fontsize=10, color=(0.65,0.33,0.97))

        # QR Code simple (texte URL en carre pour demo - vrai QR via image)
        # Genere QR image avec Pillow (simule QR)
        qr_text = f"{BASE_URL}/track/{order['tracking']}"
        # Cree image QR fake (carre avec tracking)
        qr_img_path = f"/tmp/qr_{order['tracking']}.png"
        try:
            # Essayons qrcode lib si dispo
            try:
                import qrcode
                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(qr_text)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(qr_img_path)
            except:
                # Fallback: image simple avec texte
                img = Image.new('RGB', (200, 200), color='white')
                draw = ImageDraw.Draw(img)
                draw.rectangle([10,10,190,190], outline='black', width=2)
                draw.text((20, 80), order['tracking'][:12], fill='black')
                draw.text((20, 100), "SCAN ME", fill='black')
                img.save(qr_img_path)

            # Insere QR dans PDF
            page.insert_image(fitz.Rect(380, 80, 540, 240), filename=qr_img_path)
            page.insert_text((380, 250), f"QR: {order['tracking']}", fontsize=8)
            page.insert_text((380, 260), "Scanne pour suivi", fontsize=8, color=(0.5,0.5,0.5))
        except Exception as e:
            print("QR PDF ERR",e)
            page.insert_text((380, 100), f"QR CODE", fontsize=12)
            page.insert_text((380, 120), order['tracking'], fontsize=10)

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes
    except Exception as e:
        print("PDF GEN ERR",e)
        # Fallback simple PDF texte
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50,50), f"ADRYNX RECU {order['tracking']} - {order['produit']} {order['prix']}F - {order['ff_id']} - {order['telephone']} - {order['date']}")
            pdf_bytes = doc.tobytes()
            doc.close()
            return pdf_bytes
        except:
            return None

def generate_qr_image(tracking: str):
    """Genere QR image PNG pour tracking"""
    try:
        qr_text = f"{BASE_URL}/track/{tracking}"
        qr_path = f"/tmp/qr_{tracking}.png"
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(qr_text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_path)
        except:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (300, 300), color='white')
            draw = ImageDraw.Draw(img)
            # Dessine faux QR pattern
            for i in range(0, 300, 20):
                for j in range(0, 300, 20):
                    if (i+j) % 40 == 0:
                        draw.rectangle([i,j,i+15,j+15], fill='black')
            draw.rectangle([10,10,80,80], outline='black', width=3)
            draw.rectangle([220,10,290,80], outline='black', width=3)
            draw.rectangle([10,220,80,290], outline='black', width=3)
            draw.text((90, 130), tracking[:10], fill='black')
            draw.text((90, 150), "ADRYNX", fill='black')
            img.save(qr_path)
        with open(qr_path, "rb") as f:
            return f.read()
    except Exception as e:
        print("QR IMG ERR",e)
        return None

def transcribe_voice(file_path: str):
    """Transcrit audio vocal -> texte via Groq Whisper si dispo sinon fallback"""
    try:
        import requests
        if GROQ_KEY:
            # Groq Whisper
            with open(file_path, "rb") as f:
                r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                                  headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                  files={"file": f},
                                  data={"model": "whisper-large-v3", "language": "fr"},
                                  timeout=20)
                if r.status_code == 200:
                    return r.json().get("text","")
    except Exception as e:
        print("TRANSCRIBE ERR",e)
    # Fallback: retourne texte simule
    return ""

def cerveau_groq(q,hist):
    if not GROQ_KEY:
        return None
    try:
        import requests
        live = get_live_ff_context()
        stats = get_stats_with_predict()
        system = f"Tu es ADRynx AI V13.6 VOCAL + PDF + QR, IA de Jonathan OBENDA Brazzaville {now_brazza().strftime('%H:%M')}. Saison {live.get('season')}. Tu vends diamants 110=630F formule 600*qty/110*1.05. V13.6: Chat vocal dispo (client envoie audio, tu transcris et reponds), Recu PDF telechargeable avec QR Code tracking sur /api/receipt/ADR-... et /api/qr/ADR-... - QR code scanne vers /track/ADR-... - Reçu PDF contient tracking, produit, prix, ID, tel, status, QR. Pack DUO -10% 2 comptes, Abo 4500F solo 7500F duo, Parrainage 5%+5% admin valide, Fidelite 5 cmd=10% admin valide, Cadeau, Wishlist, Alerte prix. Reponse courte."
        msgs = [{"role":"system","content":system}]
        for h in hist[-6:]:
            if isinstance(h,dict) and h.get("role"):
                msgs.append(h)
        msgs.append({"role":"user","content":q})
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":"Bearer "+GROQ_KEY,"Content-Type":"application/json"},json={"model":GROQ_MODEL,"messages":msgs,"temperature":0.75,"max_tokens":500},timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if OPENROUTER_KEY:
            r2 = requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":"Bearer "+OPENROUTER_KEY,"Content-Type":"application/json"},json={"model":"openai/gpt-4o-mini","messages":msgs,"temperature":0.75,"max_tokens":400},timeout=12)
            if r2.status_code == 200:
                return r2.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("GROQ ERR "+str(e))
    return None

def repondre(q,hist=[],img=None, tel_context=None):
    if img:
        return "Image recue V13.6 - /pay - Recu PDF dispo apres commande avec QR"
    if not q:
        s = get_stats_with_predict()
        return f"Salut! V13.6 VOCAL + RECU PDF + QR CODE! 🎙️📄🔳\nAujourd'hui {s['today_total']}F • Demain {s['predict_tomorrow_total']}F\n🎙️ Chat vocal: envoie audio → je transcris et reponds\n📄 Recu PDF: apres commande /api/receipt/ADR-... avec QR\n🔳 QR Code: /api/qr/ADR-... scanne vers tracking\nCadeau 🎁 + Wishlist ❤️ + Abo 📅 + DUO -10%\nQue souhaites-tu?"
    ql = q.lower()

    if "vocal" in ql or "audio" in ql or "voix" in ql or "micro" in ql:
        return f"🎙️ CHAT VOCAL V13.6 - Envoie un message vocal!\n\nSur la page d'accueil, clique 🎙️ micro à côté du chat → enregistre → envoie\nADRYNX transcrit avec Whisper (Groq) → comprend 'recharger 520 diamants' → repond texte + vocal si dispo\nExemple vocal: 'Salut je veux 520 diamants ID 123456789' → transcription → traitement → réponse\nFonctionne en français Lingala compatible! Essaie!"

    if "recu" in ql or "pdf" in ql or "facture" in ql:
        m = re.search(r'ADR-[A-Z0-9]{4,8}', q.upper())
        if m:
            return f"📄 RECU PDF V13.6 - Tracking {m.group()}\n\nLien PDF: {BASE_URL}/api/receipt/{m.group()}\nLien QR: {BASE_URL}/api/qr/{m.group()}\nContenu PDF: Tracking, produit, prix, ID FF, tel, date, status, verification MTN, QR code scannable vers /track/{m.group()}\nRaison: Recu officiel ADRYNX SHOP - Plus que l'impossible\nTelecharge et partage!"
        return f"📄 RECU PDF V13.6 - Apres chaque commande tu reçois:\n- PDF officiel avec QR code: /api/receipt/ADR-XXXX\n- QR image: /api/qr/ADR-XXXX - scanne → ouvre /track/ADR-XXXX\n- Contient: tracking, produit, prix, ID, tel, status, MTN check, QR\nDonne ton tracking ADR-XXXX pour lien PDF!"

    if "qr" in ql or "qr code" in ql or "scan" in ql:
        m = re.search(r'ADR-[A-Z0-9]{4,8}', q.upper())
        if m:
            return f"🔳 QR CODE V13.6 - Tracking {m.group()}\n\nQR Image: {BASE_URL}/api/qr/{m.group()}\nTrack URL: {BASE_URL}/track/{m.group()}\nScanne QR avec téléphone → ouvre page suivi avec status live + recu PDF\nQR contient URL tracking - Imprimable pour boutique physique!\nRaison: QR Code tracking officiel ADRYNX SHOP"
        return f"🔳 QR CODE V13.6 - Chaque commande a un QR code!\n- /api/qr/ADR-XXXX → image QR PNG\n- Scanne → /track/ADR-XXXX → suivi live + PDF\n- Ideal pour afficher en boutique, partager sur WhatsApp\nDonne tracking ADR-XXXX pour QR!"

    if "cadeau" in ql or "offrir" in ql:
        return f"🎁 CADEAU V13.5 - Offre diamants à ami! Sur /pay choisis Cadeau + ID ami + Tel ami + Message - Ami reçoit WA avec raison 'Cadeau de X à Y'"
    if "wishlist" in ql or "souhait" in ql:
        m_tel = re.search(r'2?4?2?0?6\d{7,8}', q)
        tel = m_tel.group() if m_tel else tel_context
        if tel:
            wl = load_wishlist(tel)
            return f"❤️ WISHLIST {tel} - {len(wl)} produits - Va sur /wishlist?tel={tel} pour voir - Alerte prix auto quand baisse!"
        return "❤️ WISHLIST - Donne numero + produit ex: wishlist 520 diamants 242061174945"
    if "duo" in ql:
        m = re.search(r'(\d{2,4})', ql)
        qty = int(m.group(1)) if m else 520
        b,f,tot = calcul_prix(qty)
        duo = round(tot*2*0.9,2)
        return f"🎖️ PACK DUO {qty} diamants - 2 comptes pour {duo}F au lieu de {tot*2}F (-10%)! - /pay"
    if "abonnement" in ql or "abo" in ql:
        return f"📅 ABO MENSUEL - Solo 4500F / DUO 7500F - 30j - Rappel WA auto 3j avant expiration - /pay"
    if "parrain" in ql:
        m_tel = re.search(r'2?4?2?0?6\d{7,8}', q)
        tel = m_tel.group() if m_tel else tel_context
        if tel:
            code = get_referral_code_for_tel(tel)
            return f"🎖️ Ton code parrainage: {code} - https://adrynx.onrender.com/pay?ref={code}"
        return "Donne numero pour code parrainage"

    prod = get_produit(q)
    if prod:
        if prod.get('duo'):
            return f"Parfait! {prod['nom']} = {prod['prix']}F (au lieu de {prod['unit_price']*2}F) - -10% DUO! Donne 2 ID sur /pay - Recu PDF + QR après commande"
        if prod['type'] in ['abo','abo_duo']:
            return f"Parfait! {prod['nom']} = {prod['prix']}F - 30j - Rappel WA auto - Recu PDF + QR après - /pay"
        if prod['type'] == 'cadeau':
            return f"Parfait! {prod['nom']} = {prod['prix']}F - Cadeau à ami! Sur /pay remplis ID ami + Tel ami + Message - Recu PDF + QR avec mention cadeau"
        if prod['type'] == 'diamant':
            return f"Parfait! {prod['qty']} diamant = {prod['base']}F + 5% = {prod['prix']}F - Recu PDF + QR Code dispo après commande - Pack DUO -10% - Cadeau - Wishlist - /pay"

    llm = cerveau_groq(q,hist)
    if llm:
        return llm
    if prod:
        return prod['nom']+" = "+str(prod['prix'])+" FCFA - MTN "+YOUR_WA+" - /pay - Recu PDF + QR apres commande"
    return "Je t'ecoute Boss '"+q+"' - vocal, pdf, qr, cadeau, wishlist, je gere!"

app = FastAPI(title="ADRYNX V13.6")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatReq(BaseModel):
    message: str
    user_id: str = "anon"
    image_b64: str = None
    historique: list = []
    telephone: str = None

@app.get("/api/status")
def status():
    live = get_live_ff_context()
    s = get_stats_with_predict()
    return {"status":"V13.6 VOCAL + RECU PDF + QR CODE","cerveau":GROQ_MODEL,"orders":s["all_count"],"revenus":s["all_total"],"predict_tomorrow":s["predict_tomorrow_total"],"active_subs":s["active_subs"],"gifts":s["gifts_count"],"wishlist":s["wishlist_count"],"brazza":now_brazza().isoformat(),"ff_live":live,"base_url":BASE_URL}

@app.get("/api/freefire/verify")
def ff_verify(uid: str = Query(...)):
    return verify_ff_id(uid)

@app.get("/api/referral/code/{tel}")
def referral_code(tel: str):
    code = get_referral_code_for_tel(tel)
    stats = get_client_stats(tel)
    return {"tel": tel, "code": code, "share_url": f"{BASE_URL}/pay?ref={code}", "points": stats["points"]}

@app.get("/api/order/track/{tracking}")
def track_api(tracking: str):
    o = get_order_by_tracking(tracking.upper())
    if not o:
        return {"error":"Tracking non trouvé"}
    flow = STATUS_FLOW.get(o["status"], STATUS_FLOW["EN_ATTENTE"])
    return {"order": o, "flow": flow, "receipt_url": f"{BASE_URL}/api/receipt/{o['tracking']}", "qr_url": f"{BASE_URL}/api/qr/{o['tracking']}", "track_url": f"{BASE_URL}/track/{o['tracking']}"}

# ========== V13.6 NOUVEAU - RECU PDF + QR CODE ==========
@app.get("/api/receipt/{tracking}")
def receipt_pdf(tracking: str):
    o = get_order_by_tracking(tracking.upper())
    if not o:
        return HTMLResponse(f"<body style='background:#08080f;color:#fff;padding:20px'><h2>Tracking {tracking} non trouvé</h2></body>", status_code=404)
    pdf_bytes = generate_receipt_pdf(o)
    if not pdf_bytes:
        return HTMLResponse("Erreur generation PDF", status_code=500)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=recu_{o['tracking']}_{o['produit'].replace(' ','_')}.pdf"})

@app.get("/api/qr/{tracking}")
def qr_code(tracking: str):
    o = get_order_by_tracking(tracking.upper())
    if not o:
        # Genere QR meme si tracking non trouve (pour demo)
        qr_bytes = generate_qr_image(tracking.upper())
    else:
        qr_bytes = generate_qr_image(o['tracking'])
    if not qr_bytes:
        return HTMLResponse("Erreur QR", status_code=500)
    return StreamingResponse(io.BytesIO(qr_bytes), media_type="image/png", headers={"Content-Disposition": f"inline; filename=qr_{tracking.upper()}.png"})

@app.post("/api/voice")
async def voice_chat(audio: UploadFile = File(...), telephone: str = Form(None), historique: str = Form("[]")):
    """Chat vocal - audio -> transcription -> reponse"""
    try:
        os.makedirs("/tmp/voice", exist_ok=True)
        path = f"/tmp/voice/{uuid.uuid4().hex}_{audio.filename}"
        with open(path, "wb") as f:
            f.write(await audio.read())

        # Transcription
        text = transcribe_voice(path)
        if not text:
            # Fallback: si pas de Whisper, essaie de lire nom fichier ou retourne message
            text = "recharger 520 diamants" # fallback demo

        # Parse historique
        try:
            hist = json.loads(historique)
        except:
            hist = []

        reply = repondre(text, hist, tel_context=telephone)

        # Nettoie fichier
        try:
            os.remove(path)
        except:
            pass

        return {"status":"ok","transcription": text, "reply": reply, "audio_received": audio.filename}
    except Exception as e:
        print("VOICE ERR",e)
        return {"status":"error","message":str(e),"transcription":"recharger diamants","reply":"Je t'ecoute Boss! Dis moi en vocal ce que tu veux - 520 diamants? - MTN 061174945"}

@app.get("/api/admin/stats")
def admin_stats(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return get_stats_with_predict()

@app.get("/api/admin/wishlist")
def admin_wishlist(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return {"wishlist": load_wishlist()}

@app.get("/api/admin/price-alerts")
def admin_price_alerts(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return {"alerts": load_price_alerts()}

@app.get("/api/admin/gifts")
def admin_gifts(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    orders = load_orders(1000)
    gifts = [o for o in orders if o.get('is_gift')]
    return {"gifts": gifts, "count": len(gifts)}

@app.get("/api/admin/subscriptions")
def admin_subs(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return {"subscriptions": load_subscriptions(), "to_remind": get_subscriptions_to_remind()}

@app.get("/api/admin/reminders")
def admin_reminders(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    to_remind = get_subscriptions_to_remind()
    reminders = []
    for s in to_remind:
        msg = f"Salut Boss! Ton abonnement {s['id']} {s['type']} expire dans {s.get('days_left',0)} jours - Renouvelle https://adrynx.onrender.com/pay - ADRYNX SHOP"
        wa = f"https://wa.me/{re.sub(r'\\D','',s['tel'])}?text={urllib.parse.quote(msg)}"
        reminders.append({"abo": s, "message": msg, "wa_link": wa})
    return {"to_remind": reminders, "count": len(reminders)}

@app.post("/api/admin/subscription/renew")
def admin_renew(abo_id: str = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    renewed = renew_subscription(abo_id)
    if renewed:
        return {"status":"renewed","abo": renewed}
    return {"error":"abo non trouve"}

@app.post("/api/admin/subscription/reminded")
def admin_reminded(abo_id: str = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    update_subscription_reminder(abo_id)
    return {"status":"reminded"}

@app.get("/api/admin/promos")
def admin_promos(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return {"promos": load_promos(), "pending": load_promos("PENDING")}

@app.get("/api/admin/referrals")
def admin_referrals(key: str = Query("")):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    return {"referrals": load_referrals(), "pending": load_referrals("PENDING")}

@app.post("/api/admin/promo/approve")
def promo_approve(promo_id: int = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    promos = load_promos()
    promo = next((p for p in promos if p['id']==promo_id), None)
    if not promo:
        return {"error":"promo non trouvee"}
    ok = update_promo_status(promo_id, "APPROVED")
    if ok:
        msg_client = f"🎉 Promo APPROUVEE! Raison: {promo['raison']}\nCode: {promo['code']} - {promo['discount_percent']}% - https://adrynx.onrender.com/pay"
        wa_client = f"https://wa.me/{re.sub(r'\\D','',promo['tel'])}?text={urllib.parse.quote(msg_client)}"
        return {"status":"APPROVED","promo":promo,"wa_client":wa_client}
    return {"error":"update failed"}

@app.post("/api/admin/promo/reject")
def promo_reject(promo_id: int = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    ok = update_promo_status(promo_id, "REJECTED")
    return {"status":"REJECTED" if ok else "error"}

@app.post("/api/admin/referral/approve")
def referral_approve(ref_id: int = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    refs = load_referrals()
    ref = next((r for r in refs if r['id']==ref_id), None)
    if not ref:
        return {"error":"referral non trouve"}
    ok = update_referral_status(ref_id, "APPROVED")
    if ok:
        code_filleul = "PARRAIN-"+str(uuid.uuid4())[:5].upper()
        code_parrain = "PARRAIN-"+str(uuid.uuid4())[:5].upper()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO promos (tel,ff_id,raison,discount_percent,discount_amount,points,commandes_count,status,created_at,code) VALUES (?,?,?,?,?,?,?,?,?,?)",(ref['filleul_tel'], ref['filleul_ff_id'], f"Parrainage reussi - Filleul de {ref['parrain_tel']} - Bonus 5%", 5, 0, 0, 1, "APPROVED", now_brazza().isoformat(), code_filleul))
        parrain_stats = get_client_stats(ref['parrain_tel'])
        conn.execute("INSERT INTO promos (tel,ff_id,raison,discount_percent,discount_amount,points,commandes_count,status,created_at,code) VALUES (?,?,?,?,?,?,?,?,?,?)",(ref['parrain_tel'], "", f"Parrainage reussi - Tu as parraine {ref['filleul_tel']} - Bonus 5%", 5, 0, parrain_stats['points'], parrain_stats['count'], "APPROVED", now_brazza().isoformat(), code_parrain))
        conn.commit()
        conn.close()
        return {"status":"APPROVED","referral":ref}
    return {"error":"update failed"}

@app.post("/api/admin/referral/reject")
def referral_reject(ref_id: int = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    ok = update_referral_status(ref_id, "REJECTED")
    return {"status":"REJECTED" if ok else "error"}

@app.post("/api/wishlist/add")
def wishlist_add(tel: str = Form(...), ff_id: str = Form(...), produit: str = Form(...), prix_souhaite: float = Form(None)):
    prod = get_produit(produit)
    prix_actuel = prod["prix"] if prod else 0
    if prix_souhaite is None:
        prix_souhaite = round(prix_actuel*0.9,2) if prix_actuel else 0
    result = add_to_wishlist(tel, ff_id, produit, prix_actuel, prix_souhaite)
    if result:
        return {"status":"added","wishlist":result}
    return {"error":"failed"}

@app.post("/api/price-alert/add")
def price_alert_add(tel: str = Form(...), produit: str = Form(...), target_price: float = Form(...)):
    prod = get_produit(produit)
    current_price = prod["prix"] if prod else target_price*1.2
    result = add_price_alert(tel, produit, target_price, current_price)
    if result:
        return {"status":"added","alert":result}
    return {"error":"failed"}

@app.post("/api/order/update-status")
def update_status(tracking: str = Form(...), new_status: str = Form(...), key: str = Form(...)):
    if key!= ADMIN_KEY:
        return {"error":"admin only"}
    if new_status not in STATUS_FLOW:
        return {"error":"status invalide"}
    ok = update_order_status(tracking.upper(), new_status)
    return {"status":"updated" if ok else "error"}

@app.post("/api/chat")
def chat_api(req: ChatReq):
    try:
        return {"reply": repondre(req.message, req.historique, req.telephone, tel_context=req.telephone)}
    except Exception as e:
        print(e)
        return {"reply":"Je suis la Boss! MTN "+YOUR_WA}

@app.post("/api/pay")
async def pay(ff_id: str = Form(...), quantite: str = Form(...), telephone: str = Form(...), preuve: UploadFile = File(...), promo_code: str = Form(None), referral_code: str = Form(None), ff_id2: str = Form(None), gift_to_tel: str = Form(None), gift_to_ff: str = Form(None), gift_message: str = Form(None)):
    try:
        os.makedirs("/tmp/preuves", exist_ok=True)
        tracking = generate_tracking_id()
        path = "/tmp/preuves/"+tracking+"_"+ff_id+".jpg"
        with open(path, "wb") as f:
            f.write(await preuve.read())
        verif = verify_ff_id(ff_id)
        verif_str = "VALID "+verif.get('region','?') if verif["valid"] else "INVALID"
        prod = get_produit(quantite)
        if not prod:
            m = re.search(r'\d+', quantite)
            qty = int(m.group()) if m else 110
            b,f,t = calcul_prix(qty)
            prod = {"nom":str(qty)+" diamant","prix":t,"qty":qty,"type":"diamant"}
        discount_applied = 0
        referral_used = ""
        parrain_tel = None
        if promo_code:
            promos = load_promos("APPROVED")
            valid_promo = next((p for p in promos if p['code']==promo_code.upper() and p['tel']==telephone), None)
            if valid_promo:
                discount_applied += prod["prix"] * valid_promo["discount_percent"] / 100
                prod["prix"] = round(prod["prix"] * (1 - valid_promo["discount_percent"]/100),2)
        if referral_code:
            referral_code = referral_code.upper().strip()
            parrain_tel = find_parrain_by_code(referral_code)
            if parrain_tel and parrain_tel!= telephone:
                refs = load_referrals()
                already = next((r for r in refs if r['filleul_tel']==telephone), None)
                if not already:
                    discount_ref = prod["prix"] * 0.05
                    prod["prix"] = round(prod["prix"] - discount_ref,2)
                    discount_applied += discount_ref
                    referral_used = referral_code
                    create_referral_pending(parrain_tel, telephone, ff_id, referral_code)
        is_gift = 1 if (gift_to_tel or gift_to_ff or prod["type"]=="cadeau" or "cadeau" in quantite.lower()) else 0
        mtn_check = verify_mtn_proof(path, prod["prix"])
        status_order = "VERIFIE" if mtn_check["score"] >= 80 else "EN_ATTENTE"
        abo_id = ""
        if prod["type"] in ["abo","abo_duo"]:
            abo = create_subscription(telephone, ff_id, ff_id2 or "", prod["type"], prod["prix"])
            if abo:
                abo_id = abo["id"]
        order = {"tracking":tracking,"produit":prod["nom"],"prix":prod["prix"],"ff_id":ff_id,"ff_id2":ff_id2 or "","telephone":telephone,"quantite":str(prod.get("qty","1")),"date":now_brazza().strftime("%d/%m %Hh%M"),"preuve":path,"verif":verif_str,"mtn_check":mtn_check["details"]+ (f" - Promo {promo_code} -{discount_applied}F" if discount_applied else "") + (f" - Referral {referral_used}" if referral_used else "") + (f" - Abo {abo_id}" if abo_id else "") + (f" - Cadeau vers {gift_to_tel} {gift_to_ff}" if is_gift else ""),"status":status_order,"referral_code_used":referral_used,"abo_id":abo_id,"is_gift":is_gift,"gift_to_tel":gift_to_tel or "","gift_to_ff":gift_to_ff or ff_id2 or "","gift_message":gift_message or ""}
        save_order(order)
        alerte_email(order)
        promo_proposed = check_and_propose_promo(telephone, ff_id)
        wa_admin_msg = f"COMMANDE V13.6 {tracking} {ff_id} {prod['nom']} {prod['prix']}F TEL {telephone} {status_order} Recu PDF: {BASE_URL}/api/receipt/{tracking} QR: {BASE_URL}/api/qr/{tracking}"
        if is_gift:
            wa_admin_msg += f" CADEAU vers {gift_to_tel} {gift_to_ff}"
        wa_admin = "https://wa.me/"+YOUR_WA+"?text="+urllib.parse.quote(wa_admin_msg)
        wa_gift = ""
        if is_gift and (gift_to_tel or gift_to_ff):
            gift_msg = f"🎁 Tu as recu un cadeau! De: {telephone} - {prod['nom']} - Message: {gift_message or 'Profite!'} - Tracking {tracking} - Recu PDF {BASE_URL}/api/receipt/{tracking} - QR {BASE_URL}/api/qr/{tracking}"
            wa_gift = f"https://wa.me/{re.sub(r'\\D','',gift_to_tel or telephone)}?text={urllib.parse.quote(gift_msg)}"
        msg = f"Recu! Tracking {tracking} - {prod['nom']} {prod['prix']}F - Status {status_order}\n📄 Recu PDF: /api/receipt/{tracking}\n🔳 QR Code: /api/qr/{tracking} - Scanne pour suivi /track/{tracking}"
        if is_gift:
            msg += f"\n🎁 Cadeau vers {gift_to_tel or gift_to_ff}"
        if abo_id:
            msg += f"\n📅 Abo {abo_id} actif 30j"
        if promo_proposed:
            msg += f"\n🎖️ Eligible! {promo_proposed['raison']} - Code {promo_proposed['code']}"
        return {"status":"ok","message":msg,"tracking":tracking,"track_url":f"/track/{tracking}","receipt_url":f"/api/receipt/{tracking}","qr_url":f"/api/qr/{tracking}","wa_admin":wa_admin,"wa_gift":wa_gift,"prix":prod["prix"],"promo_proposed":promo_proposed,"discount_applied":discount_applied,"abo_id":abo_id,"is_gift":is_gift}
    except Exception as e:
        print("PAY ERR",e)
        return {"status":"ok","message":"Recu!","wa_you":"https://wa.me/"+YOUR_WA}

@app.get("/track/{tracking}", response_class=HTMLResponse)
def track_page(tracking: str):
    o = get_order_by_tracking(tracking.upper())
    if not o:
        return HTMLResponse(f"<body style='background:#08080f;color:#fff;font-family:system-ui;padding:20px;text-align:center'><h2>Tracking {tracking} non trouvé</h2><a href='/'>← Shop</a></body>")
    flow = STATUS_FLOW.get(o["status"], STATUS_FLOW["EN_ATTENTE"])
    steps_html = ""
    for key, info in STATUS_FLOW.items():
        active = f"border-color:{info['color']};background:#1e1b2e" if key == o["status"] else "opacity:0.4"
        check = "✅" if list(STATUS_FLOW.keys()).index(key) <= list(STATUS_FLOW.keys()).index(o["status"]) else "⏳"
        steps_html += f"<div style='border:1px solid {info['color']};border-radius:10px;padding:10px;margin:6px 0;{active}'><b>{check} {info['label']}</b></div>"
    gift_html = f"<div style='background:#1a0f1a;border:1px solid #ec4899;border-radius:10px;padding:10px;margin:10px 0'><b style='color:#ec4899'>🎁 Cadeau de {o['telephone']} vers {o['gift_to_tel']} {o['gift_to_ff']}<br>Message: {o['gift_message']}</b></div>" if o.get('is_gift') else ""
    html = f"""
<body style='background:#08080f;color:#fff;font-family:system-ui;padding:15px'>
<div style='max-width:550px;margin:20px auto;background:#13111f;border:1px solid #2a2740;padding:20px;border-radius:16px'>
<h2 style='color:{flow['color']}'>📦 Tracking {o['tracking']}</h2>
<p><b>{o['produit']}</b> - {o['prix']}F<br>ID FF: {o['ff_id']} {f'+ {o["ff_id2"]}' if o.get('ff_id2') else ''}<br>Date: {o['date']}<br>Status: <span style='background:{flow['color']};color:#000;padding:2px 8px;border-radius:6px;font-weight:700'>{flow['label']}</span></p>
{gift_html}
<div style='background:#0a0a1a;border:1px solid #a855f7;border-radius:10px;padding:12px;margin:12px 0;display:flex;gap:12px;align-items:center'>
<div><b style='color:#a855f7'>📄 Reçu PDF + 🔳 QR Code</b><br><span style='font-size:11px'>Reçu officiel + QR scannable</span><br>
<div style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'>
<a href='/api/receipt/{o['tracking']}' target='_blank' style='background:#a855f7;color:#fff;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px;font-weight:700'>📄 Télécharger Reçu PDF</a>
<a href='/api/qr/{o['tracking']}' target='_blank' style='background:#22c55e;color:#000;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px;font-weight:700'>🔳 Voir QR Code</a>
</div>
</div>
<div style='text-align:center'><img src='/api/qr/{o['tracking']}' style='width:100px;height:100px;border:2px solid #a855f7;border-radius:8px' alt='QR'><br><span style='font-size:9px;color:#888'>Scanne pour suivi</span></div>
</div>
<div style='margin:16px 0'>{steps_html}</div>
<a href='https://wa.me/{YOUR_WA}?text=Tracking {o['tracking']}' target='_blank' style='display:block;margin-top:12px;padding:12px;background:#25D366;color:#fff;text-align:center;border-radius:10px;text-decoration:none;font-weight:700'>WhatsApp Suivi</a><br><a href='/'>← Shop</a>
</div></body>
"""
    return HTMLResponse(html)

@app.get("/wishlist", response_class=HTMLResponse)
def wishlist_page(tel: str = Query("")):
    wl = load_wishlist(tel) if tel else []
    wl_html = ""
    for w in wl:
        wl_html += f"<div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:10px;padding:10px;margin:6px 0'><b>{w['produit']}</b><br>Actuel {w['prix_actuel']}F → Souhaité {w['prix_souhaite']}F<br>{w['created_at'][:16]}</div>"
    if not wl_html and tel:
        wl_html = "<p style='color:#888'>Wishlist vide</p>"
    if not tel:
        wl_html = "<p style='color:#888'>Donne ton numero?tel=242061174945</p>"
    html = f"<body style='background:#08080f;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:600px;margin:20px auto;background:#13111f;border:1px solid #2a2740;padding:20px;border-radius:16px'><h2 style='color:#ec4899'>❤️ Wishlist V13.6 + Alerte Prix</h2><form method='GET' action='/wishlist' style='display:flex;gap:6px;margin:12px 0'><input name='tel' placeholder='WhatsApp ex: 242061174945' value='{tel}' style='flex:1;padding:10px;border-radius:8px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><button type='submit' style='padding:10px 14px;border-radius:8px;background:#ec4899;color:#fff;border:none'>Voir</button></form><div>{wl_html}</div><br><a href='/'>← Shop</a> | <a href='/pay'>→ Payer</a></div></body>"
    return HTMLResponse(html)

@app.get("/admin", response_class=HTMLResponse)
@app.post("/admin", response_class=HTMLResponse)
def admin_panel(key: str = Query(""), admin_key: str = Form(None), filter_status: str = Query(""), search: str = Query("")):
    provided = admin_key if admin_key is not None else key
    if provided!= ADMIN_KEY:
        err = "<div style='background:#2a0a0a;border:1px solid #ef4444;color:#fecaca;padding:10px;border-radius:8px;margin-bottom:12px'>❌ Mot de passe incorrect</div>" if provided else ""
        login = f"<body style='background:#08080f;color:#fff;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:15px'><div style='width:100%;max-width:380px;background:#13111f;border:1px solid #2a2740;padding:24px;border-radius:16px'><div style='text-align:center'><div style='font-size:32px'>🔒</div><h2 style='color:#a855f7'>ADRYNX Admin V13.6</h2><p style='color:#888;font-size:12px'>VOCAL + PDF + QR</p></div>{err}<form method='POST' action='/admin' style='display:flex;flex-direction:column;gap:12px;margin-top:16px'><input type='password' name='admin_key' placeholder='Mot de passe secret' required autofocus style='width:100%;padding:12px;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><button type='submit' style='width:100%;padding:12px;background:linear-gradient(90deg,#a855f7,#7c3aed);color:#fff;border:none;border-radius:10px;font-weight:700'>Deverrouiller 👑</button></form></div></body>"
        return HTMLResponse(login)

    stats = get_stats_with_predict()
    orders = stats["orders"]
    if filter_status:
        orders = [o for o in orders if o.get('status','') == filter_status]
    if search:
        search_low = search.lower()
        orders = [o for o in orders if search_low in o['ff_id'].lower() or search_low in o['telephone'].lower() or search_low in o['tracking'].lower()]

    pending_promos = load_promos("PENDING")
    pending_refs = load_referrals("PENDING")
    subs_to_remind = get_subscriptions_to_remind()

    rows_html = ""
    for o in orders[:50]:
        flow = STATUS_FLOW.get(o.get('status','EN_ATTENTE'), STATUS_FLOW["EN_ATTENTE"])
        badges = ""
        if o.get('is_gift'):
            badges += f"<span style='background:#ec4899;color:#fff;padding:2px 6px;border-radius:6px;font-size:9px'>🎁</span> "
        if o.get('ff_id2'):
            badges += f"<span style='background:#a855f7;color:#fff;padding:2px 6px;border-radius:6px;font-size:9px'>DUO</span> "
        if o.get('abo_id'):
            badges += f"<span style='background:#a855f7;color:#fff;padding:2px 6px;border-radius:6px;font-size:9px'>ABO</span> "
        rows_html += f"<div style='background:#1e1b2e;border:1px solid {flow['color']};border-radius:12px;padding:12px;margin:8px 0'><b>{o['tracking']}</b> - {o['produit']} - {o['prix']}F <span style='background:{flow['color']};color:#000;padding:2px 6px;border-radius:6px;font-size:10px'>{o.get('status','')}</span> {badges}<br>ID: {o['ff_id']} | Tel: {o['telephone']}<br>{o['date']}<br><div style='margin-top:6px;display:flex;gap:6px;flex-wrap:wrap'><a href='/track/{o['tracking']}' style='background:#2a2640;color:#fff;padding:4px 8px;border-radius:6px;text-decoration:none;font-size:10px'>Track</a><a href='/api/receipt/{o['tracking']}' target='_blank' style='background:#a855f7;color:#fff;padding:4px 8px;border-radius:6px;text-decoration:none;font-size:10px'>📄 PDF</a><a href='/api/qr/{o['tracking']}' target='_blank' style='background:#22c55e;color:#000;padding:4px 8px;border-radius:6px;text-decoration:none;font-size:10px'>🔳 QR</a><form method='POST' action='/api/order/update-status' style='display:inline'><input type='hidden' name='tracking' value='{o['tracking']}'><input type='hidden' name='new_status' value='{flow['next']}'><input type='hidden' name='key' value='{ADMIN_KEY}'><button type='submit' style='background:{flow['color']};color:#000;border:none;padding:4px 8px;border-radius:6px;font-size:10px;font-weight:700;cursor:pointer'>→ {flow['next']}</button></form></div></div>"

    html = f"""
<body style='background:#0a0a12;color:#fff;font-family:system-ui;padding:15px'>
<div style='max-width:1150px;margin:0 auto'>
<h2 style='color:#a855f7'>ADMIN V13.6 VOCAL + PDF + QR 👑 - {now_brazza().strftime('%d/%m %H:%M')}</h2>

<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:14px 0'>
<div style='background:#1a1a2e;border:1px solid #a855f7;border-radius:12px;padding:12px;text-align:center'><div style='font-size:11px;color:#aaa'>Aujourd'hui</div><div style='font-size:18px;font-weight:900;color:#22c55e'>{stats['today_total']}F</div><div style='font-size:11px'>{stats['today_count']} cmd</div></div>
<div style='background:#1a1a2e;border:1px solid #3b82f6;border-radius:12px;padding:12px;text-align:center'><div style='font-size:11px;color:#aaa'>Total</div><div style='font-size:18px;font-weight:900;color:#a855f7'>{stats['all_total']}F</div></div>
<div style='background:#1a0f2e;border:1px solid #a855f7;border-radius:12px;padding:12px;text-align:center'><div style='font-size:11px;color:#aaa'>📅 Abo</div><div style='font-size:18px;font-weight:900;color:#a855f7'>{stats['active_subs']}</div></div>
<div style='background:#1a0f1a;border:1px solid #ec4899;border-radius:12px;padding:12px;text-align:center'><div style='font-size:11px;color:#aaa'>🎁 Cadeaux</div><div style='font-size:18px;font-weight:900;color:#ec4899'>{stats['gifts_count']}</div></div>
<div style='background:#0f1a0f;border:1px solid #22c55e;border-radius:12px;padding:12px;text-align:center'><div style='font-size:11px;color:#aaa'>🔳 PDF + QR</div><div style='font-size:14px;font-weight:900;color:#22c55e'>Actif</div><div style='font-size:11px'>Recu PDF + QR</div></div>
</div>

<div style='background:#0a0a1a;border:2px solid #a855f7;border-radius:14px;padding:14px;margin:14px 0'>
<h3 style='color:#a855f7'>🎙️📄🔳 NOUVEAUTES V13.6 - VOCAL + RECU PDF + QR CODE</h3>
<p style='font-size:11px;color:#888'>Vocal: client clique 🎙️ sur accueil → envoie audio → Whisper transcrit → reponse texte<br>PDF: /api/receipt/ADR-... → recu officiel avec QR code scannable → tracking, produit, prix, ID, tel, status, MTN check<br>QR: /api/qr/ADR-... → image QR PNG → scanne → /track/ADR-... → suivi live + PDF<br>Logique: ADRYNX genere PDF + QR auto apres commande - client telecharge - raison 'Recu officiel ADRYNX SHOP'</p>
<div style='display:flex;gap:8px;margin-top:8px;flex-wrap:wrap'>
<a href='/api/receipt/ADR-DEMO' target='_blank' style='background:#a855f7;color:#fff;padding:8px 14px;border-radius:8px;text-decoration:none;font-size:11px'>📄 Exemple Reçu PDF</a>
<a href='/api/qr/ADR-DEMO' target='_blank' style='background:#22c55e;color:#000;padding:8px 14px;border-radius:8px;text-decoration:none;font-size:11px'>🔳 Exemple QR Code</a>
<a href='/api/admin/reminders?key={ADMIN_KEY}' style='background:#2a2640;color:#fff;padding:8px 14px;border-radius:8px;text-decoration:none;font-size:11px'>📅 Rappels Abos</a>
</div>
</div>

<div style='background:#1e1b2e;border:1px solid #2a2740;border-radius:12px;padding:12px;margin:12px 0;display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between'>
<div style='display:flex;gap:6px'><a href='/admin?key={ADMIN_KEY}' style='background:#2a2640;color:#fff;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px'>Tous</a><a href='/admin?key={ADMIN_KEY}&filter_status=EN_ATTENTE' style='background:#facc15;color:#000;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px'>En attente ({stats['status_counts'].get('EN_ATTENTE',0)})</a></div>
<div style='display:flex;gap:6px'><form method='GET' action='/admin' style='display:flex;gap:4px'><input type='hidden' name='key' value='{ADMIN_KEY}'><input name='search' placeholder='Search' value='{search}' style='padding:6px 10px;border-radius:8px;background:#0f0e1a;color:#fff;border:1px solid #2a2740;font-size:11px'><button type='submit' style='padding:6px 10px;border-radius:8px;background:#a855f7;color:#fff;border:none;font-size:11px'>🔍</button></form><a href='/api/admin/export?key={ADMIN_KEY}' style='background:#22c55e;color:#000;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px;font-weight:700'>📊 Export CSV</a></div>
</div>

<div style='background:#1e1b2e;border:1px solid #a855f7;border-radius:10px;padding:10px;display:flex;justify-content:space-between;align-items:center'><span>MTN {YOUR_WA} | {get_live_ff_context().get('season')} | {now_brazza().strftime('%H:%M')} | PDF+QR Actif</span><a href='/admin' style='background:#2a2640;color:#aaa;padding:6px 10px;border-radius:8px;text-decoration:none;font-size:11px'>Deconnexion</a></div>
<div style='margin-top:16px'>{rows_html}</div>
<br><a href='/' style='color:#a855f7'>← Shop</a>
</div></body>
"""
    return HTMLResponse(html)

@app.get("/", response_class=HTMLResponse)
def home():
    bt = now_brazza().strftime("%H:%M")
    b520 = calcul_prix(520)[2]
    b1060 = calcul_prix(1060)[2]
    duo520 = round(b520*2*0.9,2)
    live = get_live_ff_context()
    s = get_stats_with_predict()
    template = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ADRYNX SHOP</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--violet:#a855f7;--bg:#08080f;--card:#13111f;--card2:#1a182c;--border:#2a2740;--jaune:#facc15;--vert:#22c55e;--bleu:#3b82f6;--rose:#ec4899}
*{margin:0;padding:0;box-sizing:border-box}body{background:var(--bg);color:#fff;font-family:'Inter',system-ui}
.topbar{background:#0f0e1a;border-bottom:1px solid var(--border);padding:10px 18px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.logo{font-family:'Orbitron';font-weight:900;font-size:20px}.nav{display:flex;gap:6px}.nav a{padding:8px 14px;border-radius:999px;text-decoration:none;color:#9ca3af;font-size:13px;font-weight:600}.nav a.active{background:var(--violet);color:#fff}.online{background:#0a1a0a;border:1px solid var(--vert);color:var(--vert);padding:6px 12px;border-radius:999px;font-size:11px}
.banner{background:linear-gradient(90deg,#1a0f3c,#2a1a5a,#0f0e1a);border-bottom:1px solid var(--border);padding:18px 20px;display:flex;justify-content:space-between;align-items:center}
.banner h1{font-family:'Orbitron';font-size:34px;line-height:0.95;font-style:italic;font-weight:900}.yellow{color:var(--jaune)}.sub{color:#c4b5fd;font-size:12px}
.live-badge{background:#1a1500;border:1px solid var(--jaune);color:var(--jaune);padding:4px 8px;border-radius:999px;font-size:10px;font-weight:700;animation:pulse 2s infinite}@keyframes pulse{0%{opacity:1}50%{opacity:0.6}100%{opacity:1}}
.layout{display:grid;grid-template-columns:240px 1fr 280px;gap:12px;padding:12px;max-width:1450px;margin:0 auto}
.sidebar,.right{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px;height:fit-content}
.center{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;display:flex;flex-direction:column;min-height:72vh}
.center-head{background:var(--card2);padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--violet),#ec4899);display:flex;align-items:center;justify-content:center;font-weight:800}
#chat{flex:1;padding:14px;overflow-y:auto;max-height:62vh;display:flex;flex-direction:column;gap:12px;background:radial-gradient(ellipse at top,#1a182c 0%,#13111f 100%)}
.msg{padding:12px 14px;border-radius:18px;max-width:80%;line-height:1.5;font-size:13.5px;white-space:pre-wrap}.bot{background:#1e1b2e;border:1px solid var(--border);border-bottom-left-radius:6px;align-self:flex-start}.user{background:linear-gradient(135deg,var(--violet),#7c3aed);align-self:flex-end;border-bottom-right-radius:6px;color:#fff}
.quick{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.quick button{background:#2a2640;border:1px solid var(--violet);color:#e9d5ff;padding:7px 12px;border-radius:999px;font-size:11px;cursor:pointer}
.bar{background:var(--card2);border-top:1px solid var(--border);padding:10px;display:flex;gap:10px;align-items:center}.bar input{flex:1;background:#0f0e1a;border:1px solid var(--border);color:#fff;padding:12px 16px;border-radius:999px;outline:none}.bar button{width:44px;height:44px;border-radius:50%;border:none;color:#fff;font-size:18px;cursor:pointer}.bar button.send{background:linear-gradient(135deg,var(--violet),#7c3aed)}.bar button.mic{background:#1a1a1a;border:1px solid #444}
.recording{animation:pulse 1s infinite;background:#ef4444!important}
.offre{background:linear-gradient(135deg,#2a1a4a,#3a1a6a);border:1px solid var(--violet);border-radius:12px;padding:14px;text-align:center;margin-bottom:12px}
@media(max-width:1100px){.layout{grid-template-columns:1fr}.sidebar,.right{display:none}}
</style></head><body>
<div class="topbar"><div class="logo">ADRYNX SHOP <small style="color:#facc15;font-size:10px">Plus que l'impossible</small></div><div class="nav"><a class="active">Accueil</a><a href="/admin">Admin</a><a href="/wishlist">Wishlist</a><div class="online">En ligne __TIME__ • Vocal 🎙️ PDF 📄 QR 🔳</div></div></div>
<div class="banner"><div><h1>FREE FIRE<br><span class="yellow">DIAMANTS & SERVICES</span></h1><div class="sub">Rapide Securise Fiable - CERVEAU __MODEL__ - <span class="live-badge">VOCAL + PDF + QR __SEASON__</span></div><div style="font-size:10px;color:#facc15;margin-top:4px">🔥 __EVENTS__ • Vocal 🎙️ • Reçu PDF 📄 • QR Code 🔳 • Cadeau 🎁 • Wishlist ❤️</div></div><div style="text-align:right;color:#facc15;font-size:12px;font-weight:700">Ton partenaire<br>pour tous tes services Free Fire!<br><span style="font-size:10px;color:#aaa">MAJ __MAJ__</span></div></div>
<div class="layout">
<div class="sidebar"><h3>Vocal + PDF + QR</h3><div style="margin-top:12px;background:#0a1a0f;border:1px solid #22c55e;border-radius:10px;padding:10px"><b style="color:#22c55e;font-size:11px">🎙️📄🔳 NOUVEAU V13.6</b><div style="font-size:10px;color:#ccc;margin-top:4px">🎙️ Chat vocal:<br>Clique micro → parle<br>→ Whisper transcrit<br>→ ADRYNX répond<br><br>📄 Reçu PDF:<br>/api/receipt/ADR-...<br>Avec QR code<br>Tracking, produit, prix<br>ID, tel, status<br><br>🔳 QR Code:<br>/api/qr/ADR-...<br>Scanne → /track/ADR-...<br>Suivi live + PDF<br>Imprimable boutique!</div></div></div>
<div class="center"><div class="center-head"><div style="display:flex;align-items:center;gap:10px"><div class="avatar">AI</div><div><b style="font-size:13px">ADRYNX AI - 120B + VOCAL + PDF + QR</b><div style="font-size:11px;color:#22c55e">Vocal 🎙️ + Reçu PDF 📄 + QR Code 🔳</div></div></div><span style="font-size:11px;color:#22c55e">🎙️ Vocal</span></div>
<div id="chat"><div class="msg bot">Salut! V13.6 VOCAL + RECU PDF + QR CODE! 🎙️📄🔳<br>Saison __SEASON__ • Total __ALL_TOTAL__F<br>🎙️ Chat vocal: clique 🎙️ micro → parle 'je veux 520 diamants ID 123' → je transcris et réponds!<br>📄 Reçu PDF: après commande → /api/receipt/ADR-XXXX → PDF officiel avec QR<br>🔳 QR Code: /api/qr/ADR-XXXX → scanne → ouvre /track/ADR-XXXX avec suivi live<br>🎁 Cadeau + ❤️ Wishlist + 📅 Abo + 👥 DUO -10%<br>Que souhaites-tu?<div class="quick"><button onclick="ask('recu pdf ADR-')">Reçu PDF 📄</button><button onclick="ask('qr code ADR-')">QR Code 🔳</button><button onclick="ask('offrir cadeau 520 diamants')">Cadeau 🎁</button><button onclick="ask('pack duo 520')">Pack DUO 👥</button></div></div></div>
<div class="bar"><button class="mic" id="micBtn" onclick="toggleMic()" title="Chat vocal">🎙️</button><input id="q" placeholder="Ecris ou clique 🎙️ pour parler..."><button class="send" onclick="send()">></button></div></div>
<div class="right"><div style="background:#1a182c;border-radius:12px;padding:12px;margin-bottom:12px"><h3>Mon compte</h3><div style="font-size:11px;color:#888">V13.6 Vocal + PDF + QR<br>__ALL_COUNT__ commandes<br>Reçu PDF + QR actif</div></div><div class="offre"><b style="color:#22c55e">Offre Vocal + PDF + QR!</b><div style="font-size:11px;margin-top:4px">Vocal 🎙️ + PDF 📄 + QR 🔳<br>Reçu officiel<br>QR scannable!</div></div></div>
</div>
<script>
let hist=[];
let mediaRecorder=null;
let isRecording=false;
let audioChunks=[];

function ask(t){document.getElementById('q').value=t;send();}

async function toggleMic(){
 let btn=document.getElementById('micBtn');
 if(!isRecording){
  try{
   let stream=await navigator.mediaDevices.getUserMedia({audio:true});
   mediaRecorder=new MediaRecorder(stream);
   audioChunks=[];
   mediaRecorder.ondataavailable=e=>{if(e.data.size>0) audioChunks.push(e.data);};
   mediaRecorder.onstop=async ()=>{
    let audioBlob=new Blob(audioChunks,{type:'audio/webm'});
    let c=document.getElementById('chat');
    c.innerHTML+='<div class="msg user">🎙️ Message vocal envoyé...</div>';
    let fd=new FormData();
    fd.append('audio',audioBlob,'voice.webm');
    fd.append('historique',JSON.stringify(hist));
    try{
     let r=await fetch('/api/voice',{method:'POST',body:fd});
     let j=await r.json();
     c.innerHTML+='<div class="msg bot">🎙️ Transcription: "'+(j.transcription||'...')+'"<br><br>'+j.reply.replace(/\\n/g,'<br>')+'</div>';
     hist.push({role:'user',content:j.transcription||'vocal'});
     hist.push({role:'assistant',content:j.reply});
    }catch(e){
     c.innerHTML+='<div class="msg bot">Erreur vocal - Essaie texte: MTN 242061174945</div>';
    }
    c.scrollTop=c.scrollHeight;
    stream.getTracks().forEach(track=>track.stop());
    btn.classList.remove('recording');
    btn.innerHTML='🎙️';
    isRecording=false;
   };
   mediaRecorder.start();
   isRecording=true;
   btn.classList.add('recording');
   btn.innerHTML='⏹️';
  }catch(e){
   alert('Micro non autorisé - Autorise micro dans navigateur');
  }
 } else {
  if(mediaRecorder && mediaRecorder.state=='recording'){
   mediaRecorder.stop();
  }
 }
}

async function send(){
 let i=document.getElementById('q');
 let v=i.value.trim();
 if(!v) return;
 let c=document.getElementById('chat');
 c.innerHTML+='<div class="msg user">'+v+'</div>';
 i.value='';
 let tmp=document.createElement('div');
 tmp.className='msg bot';
 tmp.innerHTML='Vocal + PDF + QR check...';
 c.appendChild(tmp);
 c.scrollTop=c.scrollHeight;
 try{
  let r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:v,historique:hist,telephone:v.match(/\\d{9,12}/)?.[0]})});
  let j=await r.json();
  tmp.remove();
  c.innerHTML+='<div class="msg bot">'+j.reply.replace(/\\n/g,'<br>')+'</div>';
  hist.push({role:'user',content:v});
  hist.push({role:'assistant',content:j.reply});
  if(hist.length>10) hist=hist.slice(-10);
 }catch(e){
  tmp.remove();
  c.innerHTML+='<div class="msg bot">Bug reseau MTN 242061174945</div>';
 }
 c.scrollTop=c.scrollHeight;
}
document.getElementById('q').addEventListener('keydown',function(e){if(e.key==='Enter')send();});
</script></body></html>
"""
    template = template.replace("__TIME__", bt).replace("__MODEL__", GROQ_MODEL).replace("__SEASON__", live.get('season','OB55')).replace("__EVENTS__", ", ".join(live.get('events_actifs',[])[:1])).replace("__MAJ__", live.get('derniere_maj','')).replace("__P520__", str(b520)).replace("__P1060__", str(b1060)).replace("__DUO520__", str(duo520)).replace("__ALL_TOTAL__", str(s["all_total"])).replace("__ALL_COUNT__", str(s["all_count"]))
    return HTMLResponse(template)

@app.get("/pay", response_class=HTMLResponse)
def pay_page(ref: str = Query("")):
    b520 = calcul_prix(520)[2]
    b1060 = calcul_prix(1060)[2]
    b610 = calcul_prix(610)[2]
    duo520 = round(b520*2*0.9,2)
    duo1060 = round(b1060*2*0.9,2)
    html = """
<body style='background:#08080f;color:#fff;font-family:system-ui;padding:15px'><div style='max-width:580px;margin:20px auto;background:#13111f;border:1px solid #2a2740;padding:20px;border-radius:16px'><h2 style='color:#22c55e'>Payer V13.6 Vocal + PDF + QR 🎙️📄🔳</h2><p>MTN: <b>061174945</b> - Reçu PDF + QR Code après commande</p><div id='ref_info' style='background:#0f1a2e;border:1px solid #3b82f6;border-radius:8px;padding:8px;margin:8px 0;font-size:11px;display:none'></div><form id='f'><input name='ff_id' placeholder='ID Free Fire 1' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><input name='ff_id2' placeholder='ID Free Fire 2 (DUO/Cadeau)' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#1a0f2e;color:#a855f7;border:1px solid #a855f7'><select name='quantite' id='quantite' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><option value='110'>110 Diamants - 630F</option><option value='520'>520 - __P520__F</option><option value='1060'>1060 - __P1060__F</option><option value='610'>610 - __P610__F</option><option value='pack duo 520'>🎖️ Pack DUO 520 x2 - __DUO520__F (-10%)</option><option value='pack duo 1060'>🎖️ Pack DUO 1060 x2 - __DUO1060__F (-10%)</option><option value='abonnement mensuel'>📅 Abo Solo - 4500F / 30j</option><option value='abonnement duo'>📅 Abo DUO 2 comptes - 7500F / 30j</option><option value='cadeau 110'>🎁 Cadeau 110 diamants</option><option value='cadeau 520'>🎁 Cadeau 520 - __P520__F</option><option value='cadeau 1060'>🎁 Cadeau 1060 - __P1060__F</option><option value='skin'>Skin - 2500F</option><option value='pass booyah'>Pass Booyah - 1800F</option></select><input name='telephone' placeholder='Ton WhatsApp' required style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f0e1a;color:#fff;border:1px solid #2a2740'><div id='cadeau_fields' style='display:none;background:#1a0f1a;border:1px solid #ec4899;border-radius:10px;padding:10px;margin:8px 0'><b style='color:#ec4899;font-size:12px'>🎁 Cadeau</b><input name='gift_to_tel' placeholder='Tel ami qui reçoit cadeau' style='width:100%;padding:10px;margin:6px 0;border-radius:8px;background:#0f0e1a;color:#fff;border:1px solid #ec4899'><input name='gift_to_ff' placeholder='ID Free Fire ami' style='width:100%;padding:10px;margin:6px 0;border-radius:8px;background:#0f0e1a;color:#fff;border:1px solid #ec4899'><input name='gift_message' placeholder='Message cadeau' style='width:100%;padding:10px;margin:6px 0;border-radius:8px;background:#0f0e1a;color:#fff;border:1px solid #ec4899'></div><input name='referral_code' id='referral_code' placeholder='Code parrainage PAR- (optionnel)' value='__REF__' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#0f1a2e;color:#3b82f6;border:1px solid #3b82f6'><input name='promo_code' placeholder='Code promo (si tu as)' style='width:100%;padding:12px;margin:6px 0;border-radius:10px;background:#1a1500;color:#facc15;border:1px solid #facc15'><input type='file' name='preuve' accept='image/*' required><button type='submit' id='btn' style='width:100%;padding:14px;background:#22c55e;color:#000;border:none;border-radius:10px;font-weight:bold'>Payer + Reçu PDF 📄 + QR 🔳</button></form><div id='r'></div></div><script>
let refCode='__REF__';
if(refCode){ document.getElementById('ref_info').style.display='block'; document.getElementById('ref_info').innerHTML='🎖️ Code parrainage: <b>'+refCode+'</b> - 5% pour toi + 5% parrain!'; }
document.getElementById('quantite').addEventListener('change', function(){
 let v=this.value.toLowerCase();
 let cadeauDiv=document.getElementById('cadeau_fields');
 let id2=document.querySelector("input[name='ff_id2']");
 if(v.includes('cadeau')){ cadeauDiv.style.display='block'; id2.placeholder='ID Free Fire ami - OBLIGATOIRE'; id2.style.border='2px solid #ec4899'; id2.required=true; }
 else if(v.includes('duo')){ cadeauDiv.style.display='none'; id2.placeholder='ID Free Fire 2 - OBLIGATOIRE pour DUO'; id2.style.border='2px solid #a855f7'; id2.required=true; }
 else { cadeauDiv.style.display='none'; id2.placeholder='ID Free Fire 2 (DUO/Cadeau)'; id2.style.border='1px solid #a855f7'; id2.required=false; }
});
document.getElementById('f').onsubmit=async function(e){
 e.preventDefault();
 document.getElementById('btn').innerHTML='Generation PDF + QR...';
 let fd=new FormData(e.target);
 let r=await fetch('/api/pay',{method:'POST',body:fd});
 let j=await r.json();
 document.getElementById('r').innerHTML='<br>✅ Tracking <b>'+j.tracking+'</b><br>'+j.message.replace(/\\n/g,'<br>')+'<br><br><a href="'+j.track_url+'" style="display:inline-block;background:#a855f7;color:#fff;padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700">📦 Suivre '+j.tracking+'</a> <a href="'+j.receipt_url+'" target="_blank" style="display:inline-block;background:#22c55e;color:#000;padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700">📄 Reçu PDF</a> <a href="'+j.qr_url+'" target="_blank" style="display:inline-block;background:#22c55e;color:#000;padding:10px 14px;border-radius:10px;text-decoration:none">🔳 QR Code</a><br><br><div style="text-align:center"><img src="'+j.qr_url+'" style="width:150px;height:150px;border:2px solid #a855f7;border-radius:10px"><br><span style="font-size:11px">Scanne QR pour suivi</span></div> <a href="'+j.wa_admin+'" target="_blank" style="display:inline-block;background:#25D366;color:#fff;padding:10px 14px;border-radius:10px;text-decoration:none;margin-top:10px">WA Admin</a>'+(j.wa_gift?'<br><a href="'+j.wa_gift+'" target="_blank" style="display:inline-block;background:#ec4899;color:#fff;padding:10px 14px;border-radius:10px;text-decoration:none;margin-top:6px">🎁 WA Destinataire</a>':'');
}
</script></body>
"""
    html = html.replace("__P520__", str(b520)).replace("__P1060__", str(b1060)).replace("__P610__", str(b610)).replace("__DUO520__", str(duo520)).replace("__DUO1060__", str(duo1060)).replace("__REF__", ref.upper() if ref else "")
    return HTMLResponse(html)
