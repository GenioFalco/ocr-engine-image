from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.base import get_db, SessionLocal
from app.models.models import ProcessingJob, Document, ExtractedResult, JobFeedback
from app.engine.pipeline import OCREngine
from app.config.settings import settings
import uuid
import os
import shutil
from datetime import datetime
from app.services.auth_service import get_current_user, get_current_admin_user
from app.models.models import User
from pydantic import BaseModel
from sqlalchemy import func

class FeedbackCreate(BaseModel):
    job_id: uuid.UUID
    rating: int          # 5 = хорошо, 1 = плохо
    comment: str = ""

router = APIRouter()

def save_upload_file(upload_file: UploadFile, job_id: uuid.UUID) -> str:
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(job_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, upload_file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path

def process_job_background(job_id: uuid.UUID, file_path: str, module: str = "standard"):
    db: Session = SessionLocal()
    try:
        engine = OCREngine(job_id=job_id, db=db)
        if module == "text-extract":
            engine.run_text_extract(file_path)
        else:
            engine.run(file_path)
    finally:
        db.close()

@router.post("/process")
async def process_sync(
    file: UploadFile = File(...),
    module: str = Form("standard"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="sync", module=module, status="processing", user_id=current_user.id)
    db.add(job)
    db.commit()

    try:
        file_path = save_upload_file(file, job_id)
        engine = OCREngine(job_id=job_id, db=db)
        if module == "text-extract":
            engine.run_text_extract(file_path)
        else:
            engine.run(file_path)
        
        # Reload job to get status
        db.refresh(job)
        
        if job.status == "failed":
            raise HTTPException(status_code=500, detail=job.error_message)

        # Fetch results
        documents = db.query(Document).filter(Document.job_id == job_id).all()
        results = []
        for doc in documents:
            extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
            results.append({
                "document_type": doc.document_type,
                "confidence": doc.confidence,
                "fields": extraction.fields_json if extraction else {},
                "stamps": extraction.stamps_json if extraction else [],
                "signatures": extraction.signatures_json if extraction else []
            })
            
        return {"status": "success", "job_id": str(job_id), "module": module, "documents": results}

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_async")
async def process_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    module: str = Form("standard"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="async", module=module, status="pending", user_id=current_user.id)
    db.add(job)
    db.commit()
    
    file_path = save_upload_file(file, job_id)

    # Background task
    background_tasks.add_task(process_job_background, job_id, file_path, module)
    
    return {"job_id": str(job_id), "status": "pending"}

@router.get("/result/{job_id}")
async def get_result(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
        
    if job.status == "done":
         # Fetch results similar to sync
        documents = db.query(Document).filter(Document.job_id == job_id).all()
        results = []
        for doc in documents:
            extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
            results.append({
                "document_type": doc.document_type,
                "confidence": doc.confidence,
                "fields": extraction.fields_json if extraction else {},
            })
        # Fetch feedback logic
        feedback = db.query(JobFeedback).filter(JobFeedback.job_id == job_id).first()
        rating = feedback.rating if feedback else None
        comment = feedback.comment if feedback else None

        return {"status": job.status, "module": job.module, "documents": results, "rating": rating, "comment": comment}

    return {"status": job.status, "module": job.module, "error": job.error_message}

@router.get("/debug/result/{job_id}")
async def debug_result(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Debug endpoint — shows raw fields_json and raw_llm_response for a job."""
    documents = db.query(Document).filter(Document.job_id == job_id).all()
    out = []
    for doc in documents:
        extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
        out.append({
            "document_type": doc.document_type,
            "fields_json": extraction.fields_json if extraction else None,
            "raw_llm_response": extraction.raw_llm_response[:2000] if extraction and extraction.raw_llm_response else None,
        })
    return out

from fastapi.responses import FileResponse
from typing import Optional
import jwt

@router.get("/preview/{job_id}")
async def get_preview(
    job_id: uuid.UUID, 
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    current_user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            if username:
                current_user = db.query(User).filter(User.username == username).first()
        except Exception:
            pass
            
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
        
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this file")
        
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(job_id))
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="File directory not found")
        
    all_files = os.listdir(upload_dir)
    if not all_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Prefer PDF files; fall back to first file if no PDF found
    pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
    chosen_file = pdf_files[0] if pdf_files else all_files[0]
        
    file_path = os.path.join(upload_dir, chosen_file)
    return FileResponse(file_path, media_type="application/pdf")

@router.get("/jobs")
async def get_user_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
    per_page: int = 50,
    module: str = None,
    date: str = None,  # YYYY-MM-DD
):
    """Fetch jobs for the current user with optional pagination and filters."""
    query = db.query(ProcessingJob).filter(ProcessingJob.user_id == current_user.id)
    if module:
        query = query.filter(ProcessingJob.module == module)
    if date:
        try:
            from datetime import date as date_type
            d = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(ProcessingJob.created_at) == d)
        except ValueError:
            pass
    total = query.count()
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    jobs = query.order_by(ProcessingJob.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [{"id": str(j.id), "mode": j.mode, "module": j.module, "status": j.status, "created_at": j.created_at, "error_message": j.error_message} for j in jobs],
        "total": total,
        "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "per_page": per_page,
    }

@router.get("/admin/jobs")
async def get_all_jobs(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
    page: int = 1,
    per_page: int = 50,
    module: str = None,
    date: str = None,       # YYYY-MM-DD
    user_id: int = None,
    errors_only: bool = False,
    min_rating: int = None,
):
    """Fetch all jobs across all users with filters and pagination (Admin only)."""
    query = db.query(ProcessingJob)
    if module:
        query = query.filter(ProcessingJob.module == module)
    if date:
        try:
            from datetime import date as _date_t
            d = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(ProcessingJob.created_at) == d)
        except ValueError:
            pass
    if user_id:
        query = query.filter(ProcessingJob.user_id == user_id)
    if errors_only:
        query = query.filter(ProcessingJob.status == "failed")
    if min_rating is not None:
        query = query.join(JobFeedback, ProcessingJob.id == JobFeedback.job_id).filter(JobFeedback.rating >= min_rating)

    total = query.count()
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    jobs = query.order_by(ProcessingJob.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Build username map
    uid_set = list({j.user_id for j in jobs})
    users_map = {}
    if uid_set:
        users_map = {u.id: u.username for u in db.query(User).filter(User.id.in_(uid_set)).all()}

    # Build rating map
    job_ids = [j.id for j in jobs]
    ratings_map = {}
    if job_ids:
        ratings_map = {f.job_id: f.rating for f in db.query(JobFeedback).filter(JobFeedback.job_id.in_(job_ids)).all()}

    return {
        "items": [{
            "id": str(j.id),
            "user_id": j.user_id,
            "username": users_map.get(j.user_id, "?"),
            "mode": j.mode,
            "module": j.module or "—",
            "status": j.status,
            "created_at": j.created_at,
            "error_message": j.error_message,
            "rating": ratings_map.get(j.id),
        } for j in jobs],
        "total": total,
        "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "per_page": per_page,
    }


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Delete a user account (Admin only). Cannot delete admin accounts."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin accounts")
    try:
        db.delete(target)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Cannot delete user: {str(e)}")
    return {"status": "deleted", "id": user_id}

@router.post("/feedback")
def submit_feedback(data: FeedbackCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == data.job_id).first()
    if not job: raise HTTPException(404, "Job not found")
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not authorized")
        
    feedback = db.query(JobFeedback).filter(JobFeedback.job_id == data.job_id).first()
    if feedback:
        feedback.rating = data.rating
        feedback.comment = data.comment or feedback.comment
    else:
        feedback = JobFeedback(job_id=data.job_id, user_id=current_user.id, rating=data.rating, comment=data.comment or None)
        db.add(feedback)
    db.commit()
    return {"status": "success"}

@router.get("/admin/analytics")
def get_analytics(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    total_jobs = db.query(ProcessingJob).count()
    failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "failed").count()
    
    avg = db.query(func.avg(JobFeedback.rating)).scalar()
    overall_rating = round(avg, 1) if avg else 0.0
    
    m_stats = db.query(ProcessingJob.module, func.count(ProcessingJob.id), func.avg(JobFeedback.rating))\
        .outerjoin(JobFeedback, ProcessingJob.id == JobFeedback.job_id)\
        .group_by(ProcessingJob.module).all()
        
    module_stats = [{"name": m[0] or "unknown", "count": m[1], "avg_rating": round(m[2], 1) if m[2] else 0.0} for m in m_stats]
    
    dist = db.query(JobFeedback.rating, func.count(JobFeedback.id)).group_by(JobFeedback.rating).all()
    rating_dist = {str(r[0]): r[1] for r in dist}
    
    return {
        "total_jobs": total_jobs,
        "failed_jobs": failed_jobs,
        "overall_rating": overall_rating,
        "module_stats": module_stats,
        "rating_distribution": rating_dist
    }

@router.get("/admin/quota")
def get_quota(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Статистика использования токенов LLM по дням."""
    from app.models.models import Log, Model
    from datetime import date, timedelta

    active_model = db.query(Model).filter(Model.is_active == True).first()
    model_name = active_model.model_name if active_model else "unknown"
    provider = active_model.provider if active_model else "unknown"

    def _parse_token_log(msg: str):
        """Разбирает запись TOKENS_USED — новый формат JSON или старый int."""
        if not msg:
            return 0, 0, 0
        import json as _json
        try:
            d = _json.loads(msg)
            if isinstance(d, dict):
                return d.get("total", 0), d.get("input", 0), d.get("output", 0)
        except Exception:
            pass
        try:
            t = int(msg)
            return t, 0, 0  # старый формат: total известен, input/output нет
        except Exception:
            return 0, 0, 0

    # За последние 7 дней по дням
    days_stats = []
    for i in range(6, -1, -1):
        day_start = (datetime.utcnow() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        rows = db.query(Log.message).filter(
            Log.stage == "TOKENS_USED",
            Log.created_at >= day_start,
            Log.created_at < day_end
        ).all()
        total = sum(_parse_token_log(r.message)[0] for r in rows)
        days_stats.append({
            "date": day_start.strftime("%d.%m"),
            "tokens": total,
            "requests": len(rows)
        })

    # Всего за всё время
    all_rows = db.query(Log.message).filter(Log.stage == "TOKENS_USED").all()
    total_all_time = 0
    total_input_all = 0
    total_output_all = 0
    for r in all_rows:
        t, inp, out = _parse_token_log(r.message)
        total_all_time += t
        total_input_all += inp
        total_output_all += out

    # Тест подключения к LLM
    llm_status = "unknown"
    try:
        from app.engine.pipeline import OCREngine
        engine = OCREngine.__new__(OCREngine)
        engine.job_id = None
        engine.db = db
        provider_obj = engine._get_llm_provider()
        provider_name = provider_obj.__class__.__name__.replace("Provider", "")
        llm_status = "ok"
    except Exception as e:
        provider_name = provider
        llm_status = f"error: {str(e)[:100]}"

    today_total = days_stats[-1]["tokens"] if days_stats else 0

    from app.services.settings_service import get_int_setting, get_setting
    daily_limit        = get_int_setting(db, "daily_token_limit")
    max_pages          = get_int_setting(db, "max_pages_per_job")
    max_jobs           = get_int_setting(db, "max_jobs_per_user_per_day")
    daily_cost_limit   = float(get_setting(db, "daily_cost_limit_usd") or 0)
    price_input_1m     = float(get_setting(db, "price_input_per_1m") or 0.21)
    price_output_1m    = float(get_setting(db, "price_output_per_1m") or 0.63)

    # Стоимость (если input/output не разбиты — считаем по blended rate)
    def calc_cost(inp, out, total):
        if inp or out:
            return round((inp * price_input_1m + out * price_output_1m) / 1_000_000, 6)
        # Старые записи: только total, используем blended ~75% input / 25% output
        blended = (0.75 * price_input_1m + 0.25 * price_output_1m)
        return round(total * blended / 1_000_000, 6)

    cost_all_time = calc_cost(total_input_all, total_output_all, total_all_time)

    # Считаем сегодняшние затраты отдельно
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_rows = db.query(Log.message).filter(
        Log.stage == "TOKENS_USED",
        Log.created_at >= today_start,
    ).all()
    today_inp = today_out = today_t = 0
    for r in today_rows:
        t, inp, out = _parse_token_log(r.message)
        today_t += t; today_inp += inp; today_out += out
    cost_today = calc_cost(today_inp, today_out, today_t)

    daily_remaining     = max(0, daily_limit - today_total) if daily_limit > 0 else None
    daily_pct           = min(100, round(today_total / daily_limit * 100, 1)) if daily_limit > 0 else 0
    daily_cost_pct      = min(100, round(cost_today / daily_cost_limit * 100, 1)) if daily_cost_limit > 0 else 0
    daily_cost_remaining = max(0.0, round(daily_cost_limit - cost_today, 4)) if daily_cost_limit > 0 else None

    return {
        "model": model_name,
        "provider": provider_name,
        "llm_status": llm_status,
        "today": {
            "tokens": today_total,
            "requests": days_stats[-1]["requests"] if days_stats else 0,
            "cost_usd": cost_today,
        },
        "total_all_time": total_all_time,
        "cost_all_time_usd": cost_all_time,
        "days": days_stats,
        "free_tier_limit": 1_000_000,
        "free_tier_remaining": max(0, 1_000_000 - total_all_time),
        "pricing": {
            "input_per_1m": price_input_1m,
            "output_per_1m": price_output_1m,
        },
        "limits": {
            "daily_token_limit": daily_limit,
            "daily_token_used": today_total,
            "daily_token_remaining": daily_remaining,
            "daily_token_pct": daily_pct,
            "max_pages_per_job": max_pages,
            "max_jobs_per_user_per_day": max_jobs,
            "daily_cost_limit_usd": daily_cost_limit,
            "daily_cost_used_usd": cost_today,
            "daily_cost_remaining_usd": daily_cost_remaining,
            "daily_cost_pct": daily_cost_pct,
        }
    }


@router.get("/admin/settings")
def get_system_settings(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Получить все системные настройки."""
    from app.services.settings_service import get_all_settings
    return get_all_settings(db)


@router.put("/admin/settings")
def update_system_settings(body: dict, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Обновить системные настройки. Передать dict {key: value}."""
    from app.services.settings_service import set_setting, DEFAULTS
    updated = {}
    for key, value in body.items():
        if key not in DEFAULTS:
            continue
        set_setting(db, key, str(value))
        updated[key] = str(value)
    return {"status": "ok", "updated": updated}


@router.get("/admin/report/daily")
def download_daily_report(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Скачать ежедневный Excel-отчёт за вчера."""
    from app.services.report_service import build_daily_report
    from datetime import timezone, timedelta
    report_date = datetime.now(timezone.utc) - timedelta(days=1)
    xlsx_bytes  = build_daily_report(db, report_date)
    filename    = f"OCR_Report_{report_date.strftime('%Y-%m-%d')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/admin/report/send")
def send_daily_report_now(admin: User = Depends(get_current_admin_user)):
    """Немедленно отправить ежедневный отчёт на email."""
    from app.services.report_service import send_daily_report
    send_daily_report()
    return {"status": "ok", "message": "Отчёт отправлен (проверьте логи если SMTP не настроен)"}


@router.get("/admin/report/recipients")
def get_report_recipients(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Получить список получателей ежедневного отчёта."""
    from app.services.settings_service import get_setting
    raw = get_setting(db, "report_recipients")
    emails = [e.strip() for e in raw.split(",") if e.strip()] if raw else []
    return {"recipients": emails}


@router.put("/admin/report/recipients")
def set_report_recipients(body: dict, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Сохранить список получателей (передать {recipients: ['a@b.com', ...]})."""
    from app.services.settings_service import set_setting
    emails = [e.strip() for e in body.get("recipients", []) if e.strip()]
    set_setting(db, "report_recipients", ",".join(emails))
    return {"status": "ok", "recipients": emails}


# --- Management API ---
from app.schemas.admin import DocumentTypeCreate, ContractCreate, ModelCreate
from app.models.models import DocumentType, Contract, Model

@router.get("/admin/users")
def get_all_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Fetch all registered users (Admin only)."""
    users = db.query(User).order_by(User.id.desc()).all()
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]

@router.post("/admin/models")
def add_model(model_data: ModelCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    existing = db.query(Model).filter(Model.name == model_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Model name already exists")
    
    provider_lower = model_data.provider.lower()
    if provider_lower not in ["gigachat", "openrouter", "qwen"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'gigachat', 'openrouter', or 'qwen'.")
    
    new_model = Model(
        name=model_data.name,
        provider=provider_lower,
        model_name=model_data.model_name,
        api_key=model_data.api_key,
        temperature=model_data.temperature,
        max_tokens=model_data.max_tokens,
        is_active=False # default to inactive
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return {"status": "created", "id": new_model.id, "name": new_model.name}

@router.get("/admin/models")
def list_models(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    models = db.query(Model).all()
    return [{
        "id": m.id,
        "name": m.name,
        "provider": m.provider,
        "model_name": m.model_name,
        "api_key": "***" + m.api_key[-4:] if m.api_key else None,
        "is_active": m.is_active
    } for m in models]

@router.delete("/admin/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(model)
    db.commit()
    return {"status": "deleted", "id": model_id}

@router.post("/admin/models/{model_id}/activate")
def activate_model(model_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Deactivate all others
    db.query(Model).update({Model.is_active: False})
    
    # Activate target
    model.is_active = True
    db.commit()
    return {"status": "success", "active_model": model.name}

@router.post("/admin/document_types")
def create_document_type(doc_type: DocumentTypeCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    existing = db.query(DocumentType).filter(DocumentType.name == doc_type.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    new_type = DocumentType(name=doc_type.name, description=doc_type.description)
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    return new_type

@router.delete("/admin/document_types/{doc_type_id}")
def delete_document_type(doc_type_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    doc_type = db.query(DocumentType).filter(DocumentType.id == doc_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")
    
    try:
        db.delete(doc_type)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete document type because it has associated contracts. Delete the contracts first.")
    
    return {"status": "deleted", "id": doc_type_id}

@router.get("/admin/document_types")
def list_document_types(db: Session = Depends(get_db)):
    doc_types = db.query(DocumentType).all()
    return [{"id": dt.id, "name": dt.name, "description": dt.description, "is_active": dt.is_active} for dt in doc_types]

@router.post("/admin/contracts")
def create_contract(contract: ContractCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    doc_type = db.query(DocumentType).filter(DocumentType.name == contract.document_type_name).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")
        
    new_contract = Contract(
        document_type_id=doc_type.id,
        json_schema=contract.json_schema,
        is_default=contract.is_default
    )
    db.add(new_contract)
    db.commit()
    return {"status": "created", "id": new_contract.id}

@router.get("/admin/contracts")
def list_contracts(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    contracts = db.query(Contract).all()
    result = []
    for c in contracts:
        doc_type = db.query(DocumentType).filter(DocumentType.id == c.document_type_id).first()
        result.append({
            "id": c.id,
            "document_type": doc_type.name if doc_type else "unknown",
            "schema": c.json_schema
        })
    return result

@router.delete("/admin/contracts/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    db.delete(contract)
    db.commit()
    return {"status": "deleted", "id": contract_id}

@router.post("/extract-text", summary="Извлечь весь текст из документа без структуры")
async def extract_text(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Извлекает весь текст из PDF или изображения без классификации и LLM.
    Для цифровых PDF — мгновенно через PyMuPDF.
    Для сканов и рукописного текста — через Tesseract OCR.
    Возвращает текст постранично и единой строкой.
    """
    import fitz
    from app.utils.classification import extract_text_from_raw_samples, detect_orientation

    job_id = uuid.uuid4()
    file_path = save_upload_file(file, job_id)

    try:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_result = []

        for i in range(len(doc)):
            page = doc[i]

            # 1. Сначала пробуем нативное извлечение (мгновенно для цифровых PDF)
            native_text = page.get_text("text").strip()

            if len(native_text) >= 50:
                # Цифровой PDF — текст извлечён нативно
                pages_result.append({
                    "page": i + 1,
                    "method": "native",
                    "text": native_text
                })
            else:
                # Скан или рукопись — запускаем Tesseract на всей странице
                mat = fitz.Matrix(2.0, 2.0)

                # Определяем ориентацию
                pix_osd = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                rotation = detect_orientation(
                    pix_osd.samples, pix_osd.width, pix_osd.height,
                    pix_osd.n, pix_osd.stride
                )
                if rotation != 0:
                    page.set_rotation(rotation)

                pix = page.get_pixmap(matrix=mat, alpha=False)
                ocr_text = extract_text_from_raw_samples(
                    pix.samples, pix.width, pix.height, pix.n, pix.stride
                ).strip()

                pages_result.append({
                    "page": i + 1,
                    "method": "ocr",
                    "text": ocr_text or native_text
                })

        doc.close()

        full_text = "\n\n".join(
            f"=== Страница {p['page']} ===\n{p['text']}"
            for p in pages_result if p["text"]
        )

        return {
            "job_id": str(job_id),
            "filename": file.filename,
            "total_pages": len(pages_result),
            "pages": pages_result,
            "full_text": full_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения текста: {str(e)}")


@router.post("/admin/init")
def init_defaults(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    defaults = ["Invoice", "Act", "UPD", "Contract"]
    created = []
    for name in defaults:
        existing = db.query(DocumentType).filter(DocumentType.name == name).first()
        if not existing:
            dt = DocumentType(name=name, description=f"Default type for {name}")
            db.add(dt)
            created.append(name)
    db.commit()
    return {"status": "initialized", "created": created}
