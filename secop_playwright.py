"""
Scraper de documentos SECOP 2 con Playwright.
Abre la página del proceso en community.secop.gov.co,
descarga los PDFs adjuntos y extrae su texto.
"""
import os
import re
import time
import logging
import tempfile
import requests
from pathlib import Path

import pdfplumber
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger(__name__)

_playwright_ok = None


def check_playwright_available() -> tuple[bool, str]:
    global _playwright_ok
    if _playwright_ok is not None:
        return _playwright_ok
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto("about:blank", timeout=5000)
            page.close()
            ctx.close()
            browser.close()
        _playwright_ok = (True, "Playwright + Chromium listos")
        log.info("Playwright validado correctamente")
    except Exception as e:
        _playwright_ok = (False, str(e))
        log.warning("Playwright NO disponible: %s", e)
    return _playwright_ok


def _extract_pdf_text(pdf_path: str, max_pages: int = 20) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            texts = []
            for page in pdf.pages[:max_pages]:
                t = page.extract_text()
                if t:
                    texts.append(t.strip())
            return "\n\n".join(texts)
    except Exception as e:
        log.error("Error leyendo PDF %s: %s", pdf_path, e)
        return ""


def _clean_text(text: str, max_chars: int = 8000) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {3,}', ' ', text)
    return text[:max_chars].strip()


def scrape_proceso_docs(url_proceso: str, headless: bool = True) -> dict:
    """
    Abre la página del proceso en SECOP 2, extrae texto de los documentos adjuntos.
    Funciona con URLs de community.secop.gov.co y contratos.gov.co
    """
    result = {"url": url_proceso, "documentos": [], "texto_completo": "", "error": None}

    if not url_proceso or url_proceso in ("#", ""):
        result["error"] = "URL no disponible"
        return result

    ok, msg = check_playwright_available()
    if not ok:
        result["error"] = f"Playwright no disponible: {msg}"
        return result

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            accept_downloads=True,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            log.info("Abriendo proceso SECOP 2: %s", url_proceso)
            page.goto(url_proceso, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(3000)

            # Intenta hacer clic en la pestaña de Documentos si existe
            for selector in [
                "a:has-text('Documentos')",
                "a:has-text('Documents')",
                "li:has-text('Documentos') a",
                "[data-tab='documents']",
                "#tab-documents",
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        page.wait_for_timeout(2000)
                        log.info("Pestaña Documentos abierta con selector: %s", selector)
                        break
                except Exception:
                    continue

            # Extrae texto visible de la página (información del proceso)
            texto_pagina = _extract_page_text(page)

            # Busca links a PDFs o documentos descargables
            doc_links = _find_doc_links(page, url_proceso)
            log.info("Links de documentos encontrados: %d", len(doc_links))

            with tempfile.TemporaryDirectory() as tmpdir:
                for doc in doc_links[:8]:
                    nombre = doc.get("nombre", "documento")
                    href = doc.get("href", "")
                    if not href:
                        continue
                    texto = _try_download_pdf(href, tmpdir, nombre)
                    if texto:
                        result["documentos"].append({
                            "nombre": nombre,
                            "texto": _clean_text(texto, 6000),
                        })
                        log.info("PDF leído: %s (%d chars)", nombre, len(texto))

            # Si no bajó PDFs, usa el texto de la página
            if not result["documentos"] and texto_pagina:
                result["documentos"].append({
                    "nombre": "Información del proceso (página web)",
                    "texto": _clean_text(texto_pagina, 6000),
                })

            partes = [f"=== {d['nombre']} ===\n{d['texto']}" for d in result["documentos"]]
            result["texto_completo"] = "\n\n".join(partes)

            if result["texto_completo"]:
                log.info("Total texto extraído: %d chars de %d fuente(s)",
                         len(result["texto_completo"]), len(result["documentos"]))
            else:
                result["error"] = "No se encontraron documentos legibles en el proceso"

        except PWTimeout:
            result["error"] = "Timeout — la página de SECOP tardó demasiado"
            log.error("Timeout en %s", url_proceso)
        except Exception as e:
            result["error"] = str(e)
            log.error("Error scraping %s: %s", url_proceso, e, exc_info=True)
        finally:
            try:
                page.close()
                context.close()
                browser.close()
            except Exception:
                pass

    return result


def _find_doc_links(page, base_url: str) -> list:
    links = []
    seen = set()

    # Selectores específicos para SECOP 2 (community.secop.gov.co)
    selectors = [
        "a[href*='.pdf']",
        "a[href*='Download']",
        "a[href*='download']",
        "a[href*='GetFile']",
        "a[href*='getfile']",
        "a[href*='Attachment']",
        "a[href*='attachment']",
        "a[href*='Documento']",
        "a[href*='documento']",
        "a[href*='File']",
        "a[href*='.docx']",
        "a[href*='.doc']",
        "a[href*='.xlsx']",
        # Selectores de tabla de documentos en SECOP 2
        ".document-list a",
        ".attachments a",
        "table a[href]",
        ".file-download a",
    ]

    for sel in selectors:
        try:
            elements = page.query_selector_all(sel)
            for el in elements:
                href = (el.get_attribute("href") or "").strip()
                text = (el.inner_text() or "").strip()[:100]
                if not href or href in seen or href.startswith("#"):
                    continue
                # URL absoluta
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(base_url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif not href.startswith("http"):
                    href = base_url.rsplit("/", 1)[0] + "/" + href
                seen.add(href)
                links.append({"nombre": text or Path(href).stem, "href": href})
        except Exception:
            continue

    return links


def _try_download_pdf(href: str, tmpdir: str, nombre: str) -> str:
    """Intenta descargar y leer un documento."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    }
    try:
        resp = requests.get(href, headers=headers, timeout=20, stream=True)
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("content-type", "")
        ext = ".pdf" if "pdf" in content_type else ".docx" if "word" in content_type else ".pdf"
        safe = re.sub(r'[^\w\-]', '_', nombre)[:40]
        path = os.path.join(tmpdir, f"{safe}{ext}")
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        if ext == ".pdf":
            return _extract_pdf_text(path)
        return ""
    except Exception as e:
        log.warning("No se pudo descargar '%s': %s", nombre, e)
        return ""


def _extract_page_text(page) -> str:
    """Extrae texto relevante de la página del proceso."""
    try:
        # Selectores específicos de SECOP 2
        for sel in [
            ".opportunity-detail",
            "#opportunity-detail",
            ".process-info",
            ".tender-detail",
            "main",
            "#main-content",
            ".container",
        ]:
            el = page.query_selector(sel)
            if el:
                texto = el.inner_text()
                if texto and len(texto) > 300:
                    return texto[:8000]
        return page.inner_text("body")[:6000]
    except Exception:
        return ""
