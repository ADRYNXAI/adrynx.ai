@app.post("/api/admin/login")
async def admin_login(req: Request):
    try:
        data = await req.json()
        pwd = (data.get("password") or "").strip()
        # accepte ADRYNX2026 même si ENV est vide
        if pwd == ADMIN_PASSWORD or pwd == "ADRYNX2026":
            return {"token": ADMIN_TOKEN}
        return JSONResponse({"error": "wrong password"}, status_code=401)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/admin/user")
async def admin_user_action(req: Request):
    if req.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return JSONResponse({"error": "unauth"}, status_code=401)
    data = await req.json()
    db = load_db()
    uid = data.get("id")
    act = data.get("action")
    for u in db["users"]:
        if u["id"] == uid:
            if act == "premium":
                u["premium"] = True
                u["unlimited"] = False
            elif act == "unlimited":
                u["unlimited"] = True
                u["premium"] = True
            elif act == "ban":
                u["premium"] = False
                u["unlimited"] = False
                u["banned"] = True
            elif act == "delete":
                db["users"] = [x for x in db["users"] if x["id"] != uid]
                break
    save_db(db)
    return {"ok": True}
