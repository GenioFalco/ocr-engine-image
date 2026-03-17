import os
import uuid
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.models import ProcessingJob, Document, PageClassification, ExtractedResult, Log, DocumentType, Contract, Model
from app.services.pdf_service import PDFService
from app.providers.gigachat_provider import GigaChatProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.qwen_provider import QwenProvider
from app.config.settings import settings
from app.utils.classification import classify_page_text, TYPE_UNKNOWN, extract_text_from_raw_samples_with_osd, detect_orientation, extract_text_from_raw_samples

logger = logging.getLogger(__name__)

class OCREngine:
    def __init__(self, job_id: uuid.UUID, db: Session):
        self.job_id = job_id
        self.db = db
        self.llm_provider = self._get_llm_provider()
        self.log_buffer = []

    def _get_llm_provider(self):
        active_model = self.db.query(Model).filter(Model.is_active == True).first()
        if not active_model:
            return GigaChatProvider(
                api_key=settings.GIGACHAT_CREDENTIALS,
                model=settings.GIGACHAT_MODEL
            )
        if active_model.provider == "gigachat":
            return GigaChatProvider(
                api_key=active_model.api_key,
                model=active_model.model_name,
                temperature=active_model.temperature
            )
        elif active_model.provider == "openrouter":
            return OpenRouterProvider(
                api_key=active_model.api_key,
                model=active_model.model_name,
                temperature=active_model.temperature,
                max_tokens=active_model.max_tokens or 8000
            )
        elif active_model.provider == "qwen":
            return QwenProvider(
                api_key=active_model.api_key,
                model=active_model.model_name,
                temperature=active_model.temperature,
                max_tokens=active_model.max_tokens or 8000
            )
        else:
            raise ValueError(f"Unsupported provider: {active_model.provider}")

    def log(self, stage: str, message: str):
        logger.info(f"[{self.job_id}] {stage}: {message}")
        log_entry = Log(job_id=self.job_id, stage=stage, message=message)
        self.db.add(log_entry)
        self.db.commit()

    def detail_log(self, stage: str, details: str):
        upload_dir = os.path.join(settings.UPLOAD_DIR, str(self.job_id))
        os.makedirs(upload_dir, exist_ok=True)
        log_path = os.path.join(upload_dir, "detailed_processing.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.utcnow().isoformat()}] --- {stage} ---\n{details}\n")

    def _calculate_hash(self, data: dict) -> str:
        import hashlib
        dump = json.dumps(data, sort_keys=True)
        return hashlib.sha256(dump.encode('utf-8')).hexdigest()

    def run(self, pdf_path: str):
        try:
            job = self.db.query(ProcessingJob).filter(ProcessingJob.id == self.job_id).first()
            job.status = "processing"
            job.started_at = datetime.utcnow()
            self.db.commit()

            self.log("INIT", f"Starting processing for file: {pdf_path}")
            self.detail_log("INIT", f"File path: {pdf_path}")

            # 1. Load PDF into memory to avoid disk IO and unlock parallel rendering
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            self.log("PDF_LOAD", f"Loaded PDF into memory ({len(pdf_bytes)} bytes)")

            # 2. Page Classification & Rendering (Parallel Tesserocr + Fitz)
            pages_info = []
            
            import fitz
            import concurrent.futures
            import os

            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                num_pages = len(doc)
            except Exception as e:
                logger.error(f"Failed to open PDF with fitz: {e}")
                doc = None
                num_pages = 0
            
            # Extract native text sequentially (instant, avoids thread crashes in fitz)
            native_texts = []
            for i in range(num_pages):
                page_text = ""
                if doc:
                    page_text = doc[i].get_text("text").strip()
                native_texts.append(page_text)
            
            if doc:
                doc.close()

            def process_page(i, pdf_bytes, native_text):
                logs = []
                import time
                t0 = time.time()
                # 1. Thread-safe PyMuPDF native extraction in RAM (Lazy, No JPEGs)
                doc_thread = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = doc_thread[i]
                
                # 1.5 Fast Native Blank Page Check (No Pillow, C-optimized)
                # Render a highly downscaled 20% resolution image purely to check pixel thresholds
                clip_blank = page.rect
                w, h = clip_blank.width, clip_blank.height
                # Crop 5% from edges to ignore scanner dark shadows
                rect_blank = fitz.Rect(w*0.05, h*0.05, w*0.95, h*0.95)
                mat_low = fitz.Matrix(0.2, 0.2)
                pix_low = page.get_pixmap(matrix=mat_low, clip=rect_blank, colorspace=fitz.csGRAY, alpha=False)
                
                is_blank = False
                if pix_low.samples:
                    # Anything lighter than 210 is background (0), anything darker is content (1)
                    trans_table = bytes([1 if x < 210 else 0 for x in range(256)])
                    dark_pixels = sum(pix_low.samples.translate(trans_table))
                    ratio = dark_pixels / len(pix_low.samples)
                    if ratio < 0.002: # Less than 0.2% text/content
                        is_blank = True
                        
                if is_blank:
                    doc_thread.close()
                    t_render = time.time() - t0
                    logs.append(("OCR_TIME", f"Page {i+1} processed in {t_render:.2f}s (Detected as BLANK)"))
                    return {
                        "page_num": i+1,
                        "type": TYPE_UNKNOWN,
                        "header_hit": False,
                        "reasons": ["blank_page"],
                        "confidence": 1.0,
                        "is_blank": True,
                        "logs": logs
                    }

                # 2. OCR Classification
                page_text = native_text
                if len(page_text) < 160:
                    # 2.1 Orientation Detection on full page (so we don't accidentally crop off the inverted header)
                    mat_osd = fitz.Matrix(1.5, 1.5)
                    pix_osd = page.get_pixmap(matrix=mat_osd, alpha=False)
                    rotation = detect_orientation(pix_osd.samples, pix_osd.width, pix_osd.height, pix_osd.n, pix_osd.stride)
                    
                    if rotation != 0:
                        logs.append(("ORIENTATION", f"OSD detected incorrect orientation. Auto-rotating page {i+1} by {rotation} degrees."))
                        page.set_rotation(rotation)
                        
                    # 2.2 Header Extraction on the now-correctly oriented page
                    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.35)
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
                    
                    logs.append(("OCR_START", f"Running Tesserocr on Page {i+1} (in memory, 35% crop)"))
                    page_text += "\n" + extract_text_from_raw_samples(
                        pix.samples, pix.width, pix.height, pix.n, pix.stride
                    )
                else:
                    logs.append(("OCR_START", f"Skipping OCR. Extracted text natively for Page {i+1}"))
                
                doc_thread.close()
                t_render = time.time() - t0
                logs.append(("OCR_TIME", f"Page {i+1} processed in {t_render:.2f}s"))

                doc_type, header_hit, reasons = classify_page_text(page_text)
                
                short_text = page_text[:100].replace("\n", " ") + "..."
                logs.append(("OCR_RESULT", f"Type: {doc_type} | Header {header_hit} | {reasons}\nPreview: {short_text}"))
                
                confidence = 1.0 if header_hit else 0.5
                return {
                    "page_num": i+1,
                    "type": doc_type,
                    "header_hit": header_hit,
                    "reasons": reasons,
                    "confidence": confidence,
                    "logs": logs
                }

            # Tesserocr releases the GIL when running C++ code, making threads highly effective.
            # We process pages in parallel to achieve the 1-2s total time requirement.
            workers = min(os.cpu_count() or 4, 8)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(process_page, i, pdf_bytes, native_texts[i])
                    for i in range(num_pages)
                ]
                
                for future in futures:
                    res = future.result()
                    
                    # Log sequentially to avoid file collision
                    for stage, msg in res.pop("logs"):
                        self.detail_log(stage, msg)
                        
                    pages_info.append(res)
                    
                    # Save classification to DB
                    pc = PageClassification(
                        job_id=self.job_id,
                        page_number=res["page_num"],
                        predicted_type=res["type"],
                        confidence=res["confidence"]
                    )
                    self.db.add(pc)
            
            self.db.commit()
            self.log("CLASSIFICATION", "OCR Page classification complete")

            # 3. Grouping Logic (Contiguous Grouping)
            groups = []
            current_group = []
            current_type = None
            
            for p in pages_info:
                # Absorb "unknown" into the current document's type if we are inside one
                eff_type = p["type"]
                if eff_type == TYPE_UNKNOWN and current_type is not None:
                    eff_type = current_type
                
                if not current_group:
                    current_type = eff_type
                    current_group = [p]
                else:
                    if eff_type == current_type or eff_type == TYPE_UNKNOWN:
                        current_group.append(p)
                        if current_type == TYPE_UNKNOWN and eff_type != TYPE_UNKNOWN:
                            current_type = eff_type
                    else:
                        groups.append({"type": current_type, "pages": current_group})
                        current_type = eff_type
                        current_group = [p]
            
            if current_group:
                groups.append({"type": current_type, "pages": current_group})
                
            # 4. Extraction Phase (Parallel LLM processing)
            import time
            
            # Step 4a: Prepare tasks and fetch DB schemas synchronously
            extraction_tasks = []
            for g_idx, group_data in enumerate(groups):
                doc_type_name = group_data["type"]
                valid_pages = [p for p in group_data["pages"] if not p.get("is_blank")]
                if not valid_pages:
                    continue
                pages_to_render = valid_pages[:10]
                
                contract = self.db.query(Contract).join(DocumentType, Contract.document_type_id == DocumentType.id).filter(DocumentType.name == doc_type_name).order_by(Contract.id.desc()).first()
                json_schema = contract.json_schema if contract else {}
                self.log("SCHEMA_SELECTION", f"Selected schema for '{doc_type_name}': {'Found' if contract else 'Not found'}")
                self.detail_log("SCHEMA_SELECTION", f"Selected schema for '{doc_type_name}': {'Found' if contract else 'Not found'}")
                
                extraction_tasks.append({
                    "g_idx": g_idx,
                    "doc_type_name": doc_type_name,
                    "pages_to_render": pages_to_render,
                    "json_schema": json_schema,
                    "group_data": group_data
                })

            # Step 4b: Execute Rendering and LLM Extraction in Parallel
            def process_extraction_task(task):
                g_idx = task["g_idx"]
                doc_type_name = task["doc_type_name"]
                pages_to_render = task["pages_to_render"]
                json_schema = task["json_schema"]
                
                # Lazily render FULL pages to JPEG
                group_images_data = []
                self.detail_log("RENDER_START", f"[{doc_type_name}] Lazily rendering {len(pages_to_render)} full pages for LLM (Matrix 2.0)")
                
                for p_idx, p in enumerate(pages_to_render):
                    page_idx = p["page_num"] - 1
                    t0 = time.time()
                    dt = fitz.open(stream=pdf_bytes, filetype="pdf")
                    mat = fitz.Matrix(2.0, 2.0) # Adjusted DPI for better quality with Gemini
                    pix = dt[page_idx].get_pixmap(matrix=mat, alpha=False)
                    jpeg_bytes = pix.tobytes("jpeg")
                    dt.close()
                    new_name = f"{doc_type_name}_{g_idx+1}_page_{p_idx+1}.jpg".replace(" ", "_")
                    t_render = time.time() - t0
                    self.detail_log("RENDER_TIME", f"Rendered {new_name} in {t_render:.2f}s")
                    group_images_data.append({"bytes": jpeg_bytes, "name": new_name})
                    
                filenames = [img["name"] for img in group_images_data]
                provider_name = self.llm_provider.__class__.__name__.replace('Provider', '')
                self.detail_log("EXTRACTION_START", f"[{doc_type_name}] Sending to {provider_name} LLM: {filenames}")
                
                # LLM Call
                extraction_result = self.llm_provider.extract_document(group_images_data, json_schema)
                self.detail_log("EXTRACTION_RESULT", f"Doc {doc_type_name} Raw LLM Response:\n{extraction_result.raw_response}")
                
                # Validation
                is_valid = self.llm_provider.validate_extraction(extraction_result, group_images_data)
                
                return {
                    "task": task,
                    "extraction_result": extraction_result,
                    "is_valid": is_valid,
                    "group_images_data": group_images_data
                }

            llm_results = []
            if extraction_tasks:
                workers = min(len(extraction_tasks), 5)
                provider_name = self.llm_provider.__class__.__name__.replace('Provider', '')
                self.detail_log("PARALLEL_LLM", f"Starting {workers} parallel {provider_name} extractions (with staggered 1s starts)...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = []
                    for i, t in enumerate(extraction_tasks):
                        if i > 0:
                            time.sleep(1.0) # Artificial stagger to prevent strict concurrent API limit bans
                        futures.append(executor.submit(process_extraction_task, t))
                        
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            llm_results.append(future.result())
                        except Exception as e:
                            logger.error(f"Parallel Extraction failed for one group: {e}")
                            self.detail_log("ERROR", f"LLM Extraction Thread Failed: {e}")

            # Step 4c: Synchronously Save to DB
            for res in llm_results:
                task = res["task"]
                extraction_result = res["extraction_result"]
                is_valid = res["is_valid"]
                doc_type_name = task["doc_type_name"]
                group_data = task["group_data"]
                
                doc_hash = self._calculate_hash(extraction_result.fields)
                existing_doc = self.db.query(Document).filter(Document.hash == doc_hash).first()
                is_duplicate = existing_doc is not None

                confidence = sum(p["confidence"] for p in group_data["pages"]) / len(group_data["pages"])
                document = Document(
                    job_id=self.job_id,
                    document_type=doc_type_name,
                    confidence=confidence,
                    hash=doc_hash,
                    is_duplicate=is_duplicate
                )
                self.db.add(document)
                self.db.commit()

                validation_status = "valid" if is_valid else "invalid"
                er = ExtractedResult(
                    document_id=document.id,
                    fields_json=extraction_result.fields,
                    stamps_json=extraction_result.stamps,
                    signatures_json=extraction_result.signatures,
                    raw_llm_response=extraction_result.raw_response,
                    validation_status=validation_status 
                )
                self.db.add(er)
                self.db.commit()

            job.status = "done"
            job.finished_at = datetime.utcnow()
            job.total_processing_time = (job.finished_at - job.started_at).total_seconds()
            self.db.commit()
            
            self.log("COMPLETE", "Processing finished successfully")
            self.detail_log("COMPLETE", f"Processing for job {self.job_id} finished successfully.")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Processing failed: {e}")
            self.detail_log("ERROR", f"Exception:\n{error_details}")
            job = self.db.query(ProcessingJob).filter(ProcessingJob.id == self.job_id).first()
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            self.db.commit()
            self.log("ERROR", str(e))
