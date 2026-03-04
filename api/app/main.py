"""Application FastAPI — point d'entrée du backend API."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compta_ecom.config.loader import load_config

from .routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Charge la configuration YAML au démarrage."""
    config_dir = Path(os.getenv("CONFIG_DIR", "./config"))
    application.state.config = load_config(config_dir)
    logger.info("Configuration chargée depuis %s", config_dir)
    yield


app = FastAPI(
    title="MAPP E-COMMERCE API",
    description="API REST pour le traitement comptable e-commerce multi-canal.",
    lifespan=lifespan,
)

# CORS
raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
logger.info("CORS origins configurées : %s", cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
