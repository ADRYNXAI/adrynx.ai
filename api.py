from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def root():
    return {"ok": True, "test": "minimal absolu"}
@app.get("/api/health")
def health():
    return {"ok": True}
