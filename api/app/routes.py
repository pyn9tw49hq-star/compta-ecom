"""Endpoints de l'API : /api/process, /api/download/excel, /api/health."""

from __future__ import annotations

import datetime
import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from compta_ecom.exporters.excel import export_to_bytes
from compta_ecom.models import BalanceError, ConfigError, NoResultError, ParseError
from compta_ecom.pipeline import PipelineOrchestrator

from .serializers import serialize_response

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 20


async def _validate_and_read_files(
    files: list[UploadFile],
) -> dict[str, bytes]:
    """Valide les uploads et retourne un dict {filename: bytes}."""
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"Trop de fichiers : {len(files)} (maximum {MAX_FILES}).",
        )

    files_dict: dict[str, bytes] = {}
    for f in files:
        filename = f.filename or "unknown"
        if not filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=422,
                detail=f"Extension invalide pour '{filename}' : seuls les fichiers .csv sont acceptés.",
            )
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Fichier '{filename}' trop volumineux : {len(content)} octets (maximum {MAX_FILE_SIZE}).",
            )
        files_dict[filename] = content

    return files_dict


@router.post("/api/process")
async def process(request: Request, files: list[UploadFile]) -> JSONResponse:
    """Upload CSV → JSON (entries, anomalies, summary)."""
    files_dict = await _validate_and_read_files(files)

    config = request.app.state.config
    pipeline = PipelineOrchestrator()

    try:
        entries, anomalies, summary, transactions = pipeline.run_from_buffers(files_dict, config)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NoResultError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BalanceError as e:
        logger.error("Erreur de balance : %s", e)
        raise HTTPException(status_code=500, detail="Erreur interne de calcul comptable")
    except ConfigError as e:
        logger.error("Erreur de configuration : %s", e)
        raise HTTPException(status_code=500, detail="Erreur de configuration interne")

    # Build country_code→name mapping from vat_table for frontend geo display
    country_names = {
        code: str(entry["name"])
        for code, entry in config.vat_table.items()
    }

    return JSONResponse(content=serialize_response(
        entries, anomalies, summary, transactions, country_names,
    ))


@router.post("/api/download/excel")
async def download_excel(request: Request, files: list[UploadFile]) -> StreamingResponse:
    """Upload CSV → fichier .xlsx en téléchargement."""
    files_dict = await _validate_and_read_files(files)

    config = request.app.state.config
    pipeline = PipelineOrchestrator()

    try:
        entries, anomalies, _summary, _transactions = pipeline.run_from_buffers(files_dict, config)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NoResultError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BalanceError as e:
        logger.error("Erreur de balance : %s", e)
        raise HTTPException(status_code=500, detail="Erreur interne de calcul comptable")
    except ConfigError as e:
        logger.error("Erreur de configuration : %s", e)
        raise HTTPException(status_code=500, detail="Erreur de configuration interne")

    buffer = export_to_bytes(entries, anomalies, config)
    today = datetime.date.today().isoformat()
    filename = f"ecritures-{today}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Health check pour Render."""
    return {"status": "ok"}
