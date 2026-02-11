from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright
from app.database import get_db
from app.models.task import Task
from app.models.form_definition import FormDefinition
from app.models.form_field import FormField
from app.services.stealth import apply_stealth

router = APIRouter()


class ValidateRequest(BaseModel):
    task_id: str


@router.post("/validate-selectors")
async def validate_selectors(request: ValidateRequest, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        return {"valid": False, "error": "Task not found"}

    form_defs = (db.query(FormDefinition)
        .filter(FormDefinition.task_id == task.id)
        .order_by(FormDefinition.step_order)
        .all())

    invalid_selectors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        if task.stealth_enabled:
            await apply_stealth(context)

        page = await context.new_page()

        for form_def in form_defs:
            try:
                await page.goto(form_def.page_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1000)

                # Check form selector
                form_el = await page.query_selector(form_def.form_selector)
                if not form_el:
                    invalid_selectors.append({
                        "type": "form",
                        "selector": form_def.form_selector,
                        "page_url": form_def.page_url
                    })

                # Check submit selector
                submit_el = await page.query_selector(form_def.submit_selector)
                if not submit_el:
                    invalid_selectors.append({
                        "type": "submit",
                        "selector": form_def.submit_selector,
                        "page_url": form_def.page_url
                    })

                # Check field selectors
                fields = (db.query(FormField)
                    .filter(FormField.form_definition_id == form_def.id)
                    .all())

                for field in fields:
                    field_el = await page.query_selector(field.field_selector)
                    if not field_el:
                        invalid_selectors.append({
                            "type": "field",
                            "selector": field.field_selector,
                            "field_name": field.field_name,
                            "page_url": form_def.page_url
                        })
            except Exception as e:
                invalid_selectors.append({
                    "type": "navigation",
                    "page_url": form_def.page_url,
                    "error": str(e)
                })

        await browser.close()

    return {
        "valid": len(invalid_selectors) == 0,
        "invalid_selectors": invalid_selectors
    }
