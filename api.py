import os
from typing import Optional
from fastapi import FastAPI,HTTPException,Header,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse,FileResponse
from pydantic import BaseModel,Field
import adrynx
app=FastAPI(title='ADRYNX API',version='5.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
class Ask(BaseModel):
 message:Optional[str]=None; q:Optional[str]=None; telephone:Optional[str]='anon'; anon:Optional[str]=None; conversation_id:Optional[str]=None
class Feedback(BaseModel):
 telephone:Optional[str]='anon'; question:str; reponse:str; satisfait:bool=False; motif:Optional[str]=''; commentaire:Optional[str]=''; correction:Optional[str]=''
class Project(BaseModel): telephone:Optional[str]='anon'; nom:str=Field(min_length=1,max_length=200); objectif:Optional[str]=''
class Task(BaseModel): telephone:Optional[str]='anon'; titre:str=Field(min_length=1,max_length=300); project_id:Optional[str]=None
class Conversation(BaseModel): telephone:Optional[str]='anon'; titre:Optional[str]='Nouvelle conversation'
def owner(x):return (x or 'anon').strip()[:120] or 'anon'
@app.get('/',response_class=HTMLResponse)
def root():
 for p in ['index.html','frontend/index.html','static/index.html']:
  if os.path.isfile(p):return FileResponse(p)
 return '<h1>ADRYNX</h1><p>API cognitive en ligne. Utilise /api/health.</p>'
@app.get('/health')
@app.get('/api/health')
def health():return {'ok':True,'service':'ADRYNX','version':'5.0','groq_configured':bool(adrynx.GROQ_API_KEY),'model':adrynx.GROQ_MODEL,'learning':'memory_examples_not_local_fine_tuning'}
@app.post('/ask')
@app.post('/api/ask')
def ask(req:Ask):
 msg=(req.message or req.q or '').strip()
 if not msg:raise HTTPException(400,'message/q requis')
 return adrynx.traiter_question(msg,owner(req.telephone or req.anon),req.conversation_id)
@app.post('/api/conversations')
def create_conv(req:Conversation):return {'ok':True,'conversation_id':adrynx.new_conversation(owner(req.telephone),req.titre or 'Nouvelle conversation')}
@app.get('/api/conversations')
def list_conv(telephone='anon'):
 c=adrynx.db();r=c.execute('SELECT id,owner,titre,created_at,updated_at FROM conversations WHERE owner=? ORDER BY updated_at DESC LIMIT 50',(owner(telephone),)).fetchall();c.close();return {'ok':True,'conversations':[dict(x) for x in r]}
@app.get('/api/conversations/{cid}')
def get_conv(cid,telephone='anon'):
 c=adrynx.db();r=c.execute('SELECT id,owner,titre,created_at,updated_at FROM conversations WHERE id=? AND owner=?',(cid,owner(telephone))).fetchone();c.close()
 if not r:raise HTTPException(404,'Conversation introuvable')
 return {'ok':True,'conversation':dict(r),'state':adrynx.state(cid),'messages':adrynx.messages(cid,100)}
@app.get('/api/dashboard')
def dash(telephone='anon'):return {'ok':True,'dashboard':adrynx.dashboard(owner(telephone))}
@app.get('/api/projects')
def get_projects(telephone='anon'):return {'ok':True,'projects':adrynx.projects(owner(telephone))}
@app.post('/api/projects')
def post_project(req:Project):return {'ok':True,'project':adrynx.project(owner(req.telephone),req.nom,req.objectif or '')}
@app.post('/api/tasks')
def post_task(req:Task):return {'ok':True,'task':adrynx.task(owner(req.telephone),req.titre,req.project_id)}
@app.post('/api/feedback')
def feedback(req:Feedback):return adrynx.enregistrer_feedback(owner(req.telephone),req.question,req.reponse,req.satisfait,req.motif or '',req.commentaire or '',req.correction or '')
@app.get('/api/learning/stats')
def learning_stats():return {'ok':True,'stats':adrynx.stats_apprentissage()}
@app.get('/api/admin/learning/export')
def export(x_adrynx_admin_secret:Optional[str]=Header(None)):
 if not adrynx.verifier_admin(x_adrynx_admin_secret):raise HTTPException(403,'Accès administrateur refusé')
 return {'ok':True,'format':'jsonl','data':adrynx.exporter_apprentissage()}
@app.websocket('/ws/{owner_id}')
async def ws(websocket:WebSocket,owner_id:str):
 await websocket.accept()
 try:
  while True:
   d=await websocket.receive_json();q=str(d.get('message') or d.get('q') or '').strip()
   if q:await websocket.send_json({'type':'answer','data':adrynx.traiter_question(q,owner_id,d.get('conversation_id'))})
 except WebSocketDisconnect:pass
if __name__=='__main__':
 import uvicorn;uvicorn.run('api:app',host='0.0.0.0',port=int(os.environ.get('PORT','8000')),reload=False)
