"""
annotations.py
In-memory collaborative plot markup.
Stores annotations per session (keyed by session_id).
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

router = APIRouter()

# In-memory store: session_id → list of annotations
_store: dict = {}


class Annotation(BaseModel):
    session_id: str
    plot_id:    int
    text:       str
    author:     Optional[str] = "Reviewer"
    lat:        Optional[float] = None
    lng:        Optional[float] = None


class DeleteRequest(BaseModel):
    session_id:     str
    annotation_id:  str


@router.post("/annotations/add")
def add_annotation(ann: Annotation):
    sid = ann.session_id
    if sid not in _store:
        _store[sid] = []
    entry = {
        "id":         str(uuid.uuid4())[:8],
        "plot_id":    ann.plot_id,
        "text":       ann.text,
        "author":     ann.author,
        "lat":        ann.lat,
        "lng":        ann.lng,
        "created_at": datetime.now().strftime("%d %b %Y %H:%M"),
    }
    _store[sid].append(entry)
    print(f"  📝 Annotation added: plot {ann.plot_id} — '{ann.text[:40]}'")
    return {"status": "ok", "annotation": entry}


@router.get("/annotations/{session_id}")
def get_annotations(session_id: str):
    return {"annotations": _store.get(session_id, [])}


@router.post("/annotations/delete")
def delete_annotation(req: DeleteRequest):
    sid  = req.session_id
    anns = _store.get(sid, [])
    _store[sid] = [a for a in anns if a["id"] != req.annotation_id]
    return {"status": "ok", "remaining": len(_store[sid])}


@router.delete("/annotations/{session_id}")
def clear_annotations(session_id: str):
    _store.pop(session_id, None)
    return {"status": "cleared"}
